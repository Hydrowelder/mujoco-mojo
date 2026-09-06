"""SensAI API router for the Dojo dashboard."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from pydantic_ai.messages import (  # pyright: ignore[reportMissingImports]
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from sse_starlette.sse import EventSourceResponse

from mujoco_mojo.settings import MujocoMojoSettings, SensAISettings
from mujoco_mojo.utils.dataframe import ColumnManifest
from mujoco_mojo.utils.layers.dojo.plot_config import PlotConfig
from mujoco_mojo.utils.layers.dojo.sensai.agent import (
    SensAIDeps,
    build_model,
    build_plot_model,
    plot_agent,
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
    return MujocoMojoSettings().dojo.sensai


@router.post("/config")
async def post_config(body: SensAISettings) -> SensAISettings:
    """Persists updated SensAI settings to disk."""
    settings = MujocoMojoSettings()
    updated = settings.model_copy(
        update={"dojo": settings.dojo.model_copy(update={"sensai": body})}
    )
    updated.save()
    return updated.dojo.sensai


# ---------------------------------------------------------------------------
# chat endpoint
# ---------------------------------------------------------------------------


class HistoryEntry(BaseModel):
    """A single prior turn in the conversation."""

    role: Literal["user", "assistant"]
    content: str


def _build_context_block(deps: SensAIDeps) -> str:
    """Build a context block containing live dashboard state to inject into the prompt."""
    lines: list[str] = ["[Current dashboard state]"]

    job = deps.job_status
    if job is None:
        lines.append("Job: none loaded")
    else:
        lines.append(
            f"Job: {job.n_done}/{job.n_trial} trials done"
            f" ({job.progress:.0%}, {job.n_success} succeeded, {job.n_failed} failed requirements, {job.n_error} errored)"
        )

    config = deps.current_plot_config
    if config is None:
        lines.append("Plot config: none loaded")
    else:
        lines.append(
            "Full plot config (reference field names from this when describing changes):"
        )
        lines.append(config.model_dump_json(indent=2))

    lines.append("[End state]")
    return "\n".join(lines)


def _to_model_messages(history: list[HistoryEntry]) -> list[ModelMessage]:
    """Convert simple role/content pairs to pydantic-ai ModelMessage objects."""
    messages: list[ModelMessage] = []
    for entry in history:
        if entry.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=entry.content)]))
        else:
            wrapped = json.dumps(
                {"message": entry.content, "plot_change_request": None}
            )
            messages.append(ModelResponse(parts=[TextPart(content=wrapped)]))
    return messages


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    message: str
    """The user's message."""

    message_history: list[HistoryEntry] = []
    """Prior conversation turns, oldest first, used to maintain context across requests."""

    all_columns: list[str] = []
    """All signal column names currently loaded in the trial viewer."""

    rotatable_vectors: list[str] = []
    """Signal columns that can be rotated using a quaternion."""

    available_quats: list[str] = []
    """Quaternion column names available for rotating rotatable_vectors."""

    current_plot_config_json: str | None = None
    """JSON-serialized PlotConfig currently active in the trial viewer, or None."""


# ---------------------------------------------------------------------------
# keyword router
# ---------------------------------------------------------------------------

_UNDO_RE = re.compile(r"\bundo\b|\brevert\b|\bgo\s+back\b", re.IGNORECASE)

_PLOT_RE = re.compile(
    r"\bcolou?r\b"  # color / colour
    r"|#[0-9a-fA-F]{3,6}\b"  # hex value
    r"|[xy][- ]?axis\b"  # x-axis, y-axis, x axis, etc.
    r"|\bgrid\b"  # grid on/off
    r"|\b(add|remov).{0,40}\bsignal\b",  # "add/remove ... signal"
    re.IGNORECASE,
)


def _is_undo_intent(message: str) -> bool:
    return bool(_UNDO_RE.search(message))


def _is_plot_intent(message: str) -> bool:
    return bool(_PLOT_RE.search(message))


# ---------------------------------------------------------------------------
# streaming helpers
# ---------------------------------------------------------------------------

_MSG_VALUE_RE = re.compile(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)', re.DOTALL)


def _extract_partial_message(text: str) -> str | None:
    """Extract the `message` field value from a still-streaming JSON blob, or None if not yet present."""
    stripped = re.sub(r"^```[a-zA-Z]*\s*\n?", "", text.strip())
    m = _MSG_VALUE_RE.search(stripped)
    if m is None:
        return None
    raw = m.group(1)
    try:
        return json.loads(f'"{raw}"')
    except (json.JSONDecodeError, ValueError):
        if raw.endswith("\\"):
            try:
                return json.loads(f'"{raw[:-1]}"')
            except (json.JSONDecodeError, ValueError):
                pass
        return raw


async def _run_plot_agent(
    current_config: PlotConfig,
    change_request: str,
    sensai_settings: SensAISettings,
) -> PlotConfig | None:
    """Run the plot agent to apply a change; returns the updated PlotConfig or None on failure."""
    plot_model = build_plot_model(sensai_settings)
    config_json = current_config.model_dump_json(indent=2)
    prompt = (
        f"Current plot config:\n{config_json}\n\n"
        f"Change to apply: {change_request}\n\n"
        f"Output the complete modified config JSON and nothing else."
    )
    try:
        result = await plot_agent.run(prompt, output_type=str, model=plot_model)
        return PlotConfig.model_validate_json(result.output)
    except Exception:
        logger.warning("Plot agent failed to produce a valid config", exc_info=True)
        return None


@router.post("/chat")
async def post_chat(body: ChatRequest):
    """Runs the SensAI agents and streams the response as SSE."""
    settings = MujocoMojoSettings()

    if not settings.dojo.sensai.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SensAI is not enabled. Set dojo.sensai.enabled = true in settings.",
        )

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
    column_manifest: ColumnManifest = {
        "all": body.all_columns,
        "rotatable_vectors": body.rotatable_vectors,
        "available_quats": body.available_quats,
    }  # pyright: ignore[reportAssignmentType]

    deps = SensAIDeps(
        job_status=shared.CURRENT_JOB,
        column_manifest=column_manifest,
        current_plot_config=current_plot_config,
    )

    model = build_model(settings.dojo.sensai)

    message_history = _to_model_messages(body.message_history)
    context_block = _build_context_block(deps)
    augmented_message = f"{context_block}\n\n{body.message}"

    async def event_stream() -> AsyncIterator[dict]:
        from mujoco_mojo.utils.layers.dojo.sensai.agent import _normalize_text_output

        # undo path: restore previous plot config via client-side history
        if _is_undo_intent(body.message):
            yield {
                "event": "result",
                "data": json.dumps(
                    {
                        "message": "Undid the last plot change.",
                        "plot_config_update": None,
                        "routed_to": "undo",
                    }
                ),
            }
            return

        # plot path: router detected a plot change intent, skip the chat agent
        if _is_plot_intent(body.message) and deps.current_plot_config is not None:
            updated = await _run_plot_agent(
                deps.current_plot_config, body.message, settings.dojo.sensai
            )
            if updated is not None:
                reply = f"Applied: {body.message.rstrip('.')}."
                pcu: dict | None = updated.model_dump()
            else:
                reply = "I wasn't able to apply that change."
                pcu = None
                logger.warning(
                    "Plot agent returned no valid config for: %s", body.message
                )
            yield {
                "event": "result",
                "data": json.dumps(
                    {"message": reply, "plot_config_update": pcu, "routed_to": "plot"}
                ),
            }
            return

        # general path: stream the chat agent response
        accumulated = ""
        streamed_len = 0
        stream_exc: Exception | None = None
        try:
            async with sensai_agent.run_stream(
                augmented_message,
                output_type=str,
                model=model,
                deps=deps,
                message_history=message_history,
            ) as streamed:
                async for delta in streamed.stream_text(delta=True, debounce_by=None):
                    accumulated += delta
                    partial = _extract_partial_message(accumulated)
                    if partial is not None and len(partial) > streamed_len:
                        chunk = partial[streamed_len:]
                        streamed_len = len(partial)
                        yield {
                            "event": "text_delta",
                            "data": json.dumps({"delta": chunk}),
                        }
        except Exception as exc:
            stream_exc = exc
            logger.debug(
                "SensAI chat run_stream exited with exception; normalizing accumulated text"
            )

        if not accumulated:
            detail = (
                f"No response from model: {stream_exc}"
                if stream_exc
                else "No response from model."
            )
            yield {"event": "error", "data": json.dumps({"detail": detail})}
            return

        try:
            data = json.loads(_normalize_text_output(accumulated))
        except (json.JSONDecodeError, ValueError):
            data = {}

        full_message = data.get("message", "")
        if len(full_message) > streamed_len:
            yield {
                "event": "text_delta",
                "data": json.dumps({"delta": full_message[streamed_len:]}),
            }

        yield {
            "event": "result",
            "data": json.dumps(
                {
                    "message": full_message or "(no response)",
                    "plot_config_update": None,
                    "routed_to": "general",
                }
            ),
        }

    return EventSourceResponse(event_stream())
