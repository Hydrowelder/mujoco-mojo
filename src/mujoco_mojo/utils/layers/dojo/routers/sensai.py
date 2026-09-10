"""SensAI API router for the Dojo dashboard."""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from collections.abc import AsyncIterable, AsyncIterator
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from pydantic_ai import RunContext  # pyright: ignore[reportMissingImports]
from pydantic_ai.messages import (  # pyright: ignore[reportMissingImports]
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolReturnPart,
    UserPromptPart,
)
from sse_starlette.sse import EventSourceResponse

from mujoco_mojo.settings import MujocoMojoSettings, SensAISettings
from mujoco_mojo.utils.dataframe import ColumnManifest
from mujoco_mojo.utils.layers.dojo.plot_config import PlotConfig
from mujoco_mojo.utils.layers.dojo.sensai import (
    SensAIDeps,
    build_fallback_model,
    chat_agent,
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
            messages.append(ModelResponse(parts=[TextPart(content=entry.content)]))
    return messages


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    message: str
    """The user's message."""

    message_history: list[HistoryEntry] = Field(default_factory=list)
    """Prior conversation turns, oldest first, used to maintain context across requests."""

    all_columns: list[str] = Field(default_factory=list)
    """All signal column names currently loaded in the trial viewer."""

    rotatable_vectors: list[str] = Field(default_factory=list)
    """Signal columns that can be rotated using a quaternion."""

    available_quats: list[str] = Field(default_factory=list)
    """Quaternion column names available for rotating rotatable_vectors."""

    column_metadata: dict[str, dict[str, str]] = Field(default_factory=dict)

    current_plot_config_json: str | None = None
    """JSON-serialized PlotConfig currently active in the trial viewer, or None."""


# ---------------------------------------------------------------------------
# undo - cheap, deterministic, client-side history pop; no LLM involved
# ---------------------------------------------------------------------------

_UNDO_RE = re.compile(r"\bundo\b|\brevert\b|\bgo\s+back\b", re.IGNORECASE)


def _is_undo_intent(message: str) -> bool:
    return bool(_UNDO_RE.search(message))


# ---------------------------------------------------------------------------
# tool-result capture - lets the router see a delegation tool's structured
# return value (e.g. a PlotConfig from ask_plot_config_agent) without asking
# the chat agent to echo it back through its own plain-text output
# ---------------------------------------------------------------------------

_DELEGATION_TOOL_ROUTES = {
    "ask_job_status_agent": "job_status",
    "ask_column_manifest_agent": "column_manifest",
    "ask_plot_config_agent": "plot_config",
}

_DELEGATION_TOOL_LABELS = {
    "ask_job_status_agent": "Checking job status...",
    "ask_column_manifest_agent": "Looking up available signals...",
    "ask_plot_config_agent": "Reading the plot configuration...",
}


class _ToolResultCapture:
    """
    Watches every event from a `chat_agent.run_stream` call as it happens.

    A delegation tool call (`ask_job_status_agent` and friends) takes a while - it's a whole nested agent run - so as soon as one starts, its label is pushed onto `queue` as a `tool_call` SSE event for the frontend to show as a "thinking" indicator; `routed_to`/`plot_config_update` are still recorded from the matching result event, same as before.

    """

    def __init__(self, queue: asyncio.Queue[dict[str, str] | None]) -> None:
        self._queue = queue
        self.routed_to: str = "general"
        self.plot_config_update: PlotConfig | None = None

    async def __call__(
        self, ctx: RunContext[SensAIDeps], events: AsyncIterable[AgentStreamEvent]
    ) -> None:
        async for event in events:
            if isinstance(event, FunctionToolCallEvent):
                label = _DELEGATION_TOOL_LABELS.get(event.part.tool_name)
                if label is not None:
                    await self._queue.put(
                        {"event": "tool_call", "data": json.dumps({"label": label})}
                    )
                continue
            if not isinstance(event, FunctionToolResultEvent) or not isinstance(
                event.part, ToolReturnPart
            ):
                continue
            route = _DELEGATION_TOOL_ROUTES.get(event.part.tool_name)
            if route is None:
                continue
            self.routed_to = route
            if isinstance(event.part.content, PlotConfig):
                self.plot_config_update = event.part.content


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
        "column_metadata": body.column_metadata,
    }  # pyright: ignore[reportAssignmentType]

    deps = SensAIDeps(
        job_status=shared.CURRENT_JOB,
        column_manifest=column_manifest,
        current_plot_config=current_plot_config,
    )

    model = build_fallback_model()

    message_history = _to_model_messages(body.message_history)
    context_block = _build_context_block(deps)
    augmented_message = f"{context_block}\n\n{body.message}"

    async def event_stream() -> AsyncIterator[dict]:
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

        # tool_call events (fired the moment a delegation tool starts, well before
        # its result/the reply text) and text_delta events (from the plain text
        # loop below) both need to reach the client in the order they actually
        # happen - a shared queue lets _ToolResultCapture push the former in
        # concurrently with the latter, rather than only being able to report
        # tool calls after the fact once the whole run finishes.
        queue: asyncio.Queue[dict[str, str] | None] = asyncio.Queue()
        capture = _ToolResultCapture(queue)
        accumulated = ""
        stream_exc: Exception | None = None

        async def _produce_text() -> None:
            nonlocal accumulated, stream_exc
            try:
                async with chat_agent.run_stream(
                    augmented_message,
                    model=model,
                    deps=deps,
                    message_history=message_history,
                    event_stream_handler=capture,
                ) as streamed:
                    async for delta in streamed.stream_text(
                        delta=True, debounce_by=None
                    ):
                        accumulated += delta
                        await queue.put(
                            {
                                "event": "text_delta",
                                "data": json.dumps({"delta": delta}),
                            }
                        )
            except Exception as exc:
                stream_exc = exc
                logger.warning("SensAI chat run_stream failed", exc_info=True)
            finally:
                await queue.put(None)

        producer = asyncio.create_task(_produce_text())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not producer.done():
                producer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await producer

        if not accumulated:
            detail = (
                f"No response from model: {stream_exc}"
                if stream_exc
                else "No response from model."
            )
            yield {"event": "error", "data": json.dumps({"detail": detail})}
            return

        yield {
            "event": "result",
            "data": json.dumps(
                {
                    "message": accumulated,
                    "plot_config_update": (
                        capture.plot_config_update.model_dump()
                        if capture.plot_config_update is not None
                        else None
                    ),
                    "routed_to": capture.routed_to,
                }
            ),
        }

    return EventSourceResponse(event_stream())
