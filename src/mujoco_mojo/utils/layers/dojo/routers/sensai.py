"""SensAI API router for the Dojo dashboard."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from mujoco_mojo.settings import MujocoMojoSettings, SensAISettings
from mujoco_mojo.utils.layers.dojo.sensai.agent import (
    SensAIDeps,
    SensAIResult,
    build_model,
    sensai_agent,
)
from mujoco_mojo.utils.log import get_logger

from .. import shared

logger = get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# config endpoints
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_config() -> SensAISettings:
    """Returns the current SensAI settings."""
    return MujocoMojoSettings().sensai


@router.post("/config")
async def post_config(body: SensAISettings) -> SensAISettings:
    """Persists updated SensAI settings to disk."""
    settings = MujocoMojoSettings()
    updated = settings.model_copy(update={"sensai": body})
    updated.save()
    return updated.sensai


# ---------------------------------------------------------------------------
# chat endpoint
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    message: str
    """The user's message."""

    available_columns: list[str] = []
    """Signal column names currently loaded in the trial viewer."""

    current_plot_config_json: str | None = None
    """JSON-serialized PlotConfig currently active in the trial viewer, or None."""


@router.post("/chat")
async def post_chat(body: ChatRequest):
    """Runs the SensAI agent and streams the response as SSE."""
    settings = MujocoMojoSettings()

    if not settings.sensai.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SensAI is not enabled. Set sensai.enabled = true in settings.",
        )

    from mujoco_mojo.utils.layers.dojo.plot_config import PlotConfig

    current_plot_config: PlotConfig | None = None
    if body.current_plot_config_json:
        try:
            current_plot_config = PlotConfig.model_validate_json(
                body.current_plot_config_json
            )
        except Exception:
            logger.warning(
                "Failed to parse current_plot_config_json; proceeding without it."
            )

    deps = SensAIDeps(
        job_status=shared.CURRENT_JOB,
        available_columns=body.available_columns,
        current_plot_config=current_plot_config,
    )

    model = build_model(settings.sensai)

    async def event_stream() -> AsyncIterator[dict]:
        try:
            result = await sensai_agent.run(body.message, model=model, deps=deps)
            output: SensAIResult = result.output
            payload = {
                "message": output.message,
                "plot_config_update": output.plot_config_update.model_dump()
                if output.plot_config_update
                else None,
            }
            yield {"event": "result", "data": json.dumps(payload)}
        except Exception as exc:
            logger.exception("SensAI agent error")
            yield {"event": "error", "data": json.dumps({"detail": str(exc)})}

    return EventSourceResponse(event_stream())
