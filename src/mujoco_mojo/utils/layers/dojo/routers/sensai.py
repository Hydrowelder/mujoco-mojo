"""SensAI API router for the Dojo dashboard."""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from collections.abc import AsyncIterable, AsyncIterator, Sequence
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from pydantic_ai import RunContext, RunUsage
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import (
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
    MAX_MODEL_REQUESTS,
    PlotEditFailed,
    SensAIDeps,
    build_fallback_model,
    chat_agent,
    usage_limits,
)
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.signal_metadata import ColumnMetadata

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


# the plot agent reads the config itself, so the chat agent only needs to know roughly what is plotted
_SIGNALS_IN_CONTEXT = 10


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
        signals = list(config.y_axes)
        shown = ", ".join(signals[:_SIGNALS_IN_CONTEXT])
        if len(signals) > _SIGNALS_IN_CONTEXT:
            shown += f", and {len(signals) - _SIGNALS_IN_CONTEXT} more"
        lines.append(
            f"Plot: x-axis {config.x_axis.col}, {len(signals)} signal(s) plotted"
            + (f": {shown}" if signals else "")
        )

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

    column_metadata: dict[str, ColumnMetadata] = Field(default_factory=dict)

    @field_validator("column_metadata", mode="before")
    @classmethod
    def _lenient_column_metadata(cls, v: Any) -> Any:
        # this payload echoes what the manifest endpoint sent, so load it without failing the request on an odd entry
        if isinstance(v, dict):
            return {k: ColumnMetadata.lenient(m) for k, m in v.items()}
        return v

    current_plot_config_json: str | None = None
    """JSON-serialized PlotConfig currently active in the trial viewer, or None."""


# ---------------------------------------------------------------------------
# undo - cheap, deterministic, client-side history pop; no LLM involved
# ---------------------------------------------------------------------------

_UNDO_RE = re.compile(r"\bundo\b|\brevert\b|\bgo\s+back\b", re.IGNORECASE)


def _is_undo_intent(message: str) -> bool:
    return bool(_UNDO_RE.search(message))


# ---------------------------------------------------------------------------
# which specialist answered, and whether the plot changed
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


# what to tell the user when a message hits the request limit: which specialist was at
# work when it did, and what they can do about it. a message that stopped while the plot
# agent was working says the plot was left alone; one that stopped on a job question
# must not
_STOPPED_WHILE: dict[str, tuple[str, str]] = {
    "ask_plot_config_agent": (
        " while changing the plot",
        " The plot was left as it was. Try asking for one change at a time, with the exact signal name if you know it.",
    ),
    "ask_job_status_agent": (
        " while looking at the job",
        " Try asking a narrower question, such as one about a single trial.",
    ),
    "ask_column_manifest_agent": (
        " while looking up signals",
        " Try asking about one kind of signal at a time.",
    ),
}


def _stopped_message(delegate: str | None) -> str:
    """The error for a message that ran into the request limit, worded for the specialist that was working on it (none known: the chat agent itself)."""
    while_, advice = _STOPPED_WHILE.get(
        delegate or "", ("", " Try rephrasing your request.")
    )
    return f"SensAI stopped after {MAX_MODEL_REQUESTS} model requests without finishing{while_}.{advice}"


def _changed_plot_config(
    before: PlotConfig | None, after: PlotConfig | None
) -> PlotConfig | None:
    """
    The plot config to send the browser: `after` when SensAI changed the plot (or loaded one), else None.

    The plot agent edits `SensAIDeps.current_plot_config` through its tools, so a question about the plot, or an edit that was refused, leaves it as it was and nothing is sent.
    """
    return after if after != before else None


def _answering_model(messages: Sequence[ModelMessage]) -> str | None:
    """
    The name of the model that wrote the reply, for the chat to show, or None if the messages hold no model response.

    That is the model behind the chat agent's last response, which a `FallbackModel` reports as the one of its chain that actually answered, not as the fallback itself, so a reply from the second model says so.
    """
    for message in reversed(messages):
        if isinstance(message, ModelResponse):
            return message.model_name
    return None


class _ToolResultCapture:
    """
    Watches every event from a `chat_agent.run_stream` call as it happens.

    A delegation tool call (`ask_job_status_agent` and friends) takes a while - it's a whole nested agent run - so as soon as one starts, its label is pushed onto `queue` as a `tool_call` SSE event for the frontend to show as a "thinking" indicator; `routed_to` is recorded from the matching result event.

    """

    def __init__(self, queue: asyncio.Queue[dict[str, str] | None]) -> None:
        self._queue = queue
        self.routed_to: str = "general"
        # the specialist the chat agent last handed a request to, which is the one
        # at work if the message then runs out of model requests
        self.delegate: str | None = None

    async def __call__(
        self, ctx: RunContext[SensAIDeps], events: AsyncIterable[AgentStreamEvent]
    ) -> None:
        async for event in events:
            if isinstance(event, FunctionToolCallEvent):
                logger.info(
                    "SensAI %s: %s", event.part.tool_name, str(event.part.args)[:300]
                )
                label = _DELEGATION_TOOL_LABELS.get(event.part.tool_name)
                if label is not None:
                    self.delegate = event.part.tool_name
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


@router.post("/chat")
async def post_chat(body: ChatRequest) -> EventSourceResponse:
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
    }

    deps = SensAIDeps(
        job_status=shared.CURRENT_JOB,
        column_manifest=column_manifest,
        current_plot_config=current_plot_config,
    )

    model = build_fallback_model()

    message_history = _to_model_messages(body.message_history)
    context_block = _build_context_block(deps)
    augmented_message = f"{context_block}\n\n{body.message}"

    async def event_stream() -> AsyncIterator[dict[str, Any]]:
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
        answering_model: str | None = None
        stream_exc: Exception | None = None
        # one count for the whole message: the specialists' runs add to it, and it is
        # what the request limit is checked against
        usage = RunUsage()

        async def _produce_text() -> None:
            nonlocal accumulated, answering_model, stream_exc
            try:
                async with chat_agent.run_stream(
                    augmented_message,
                    model=model,
                    deps=deps,
                    message_history=message_history,
                    event_stream_handler=capture,
                    usage=usage,
                    usage_limits=usage_limits(),
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
                    answering_model = _answering_model(streamed.all_messages())
            except PlotEditFailed as exc:
                # the plot agent gave up: its reason is the reply, as it is, with no
                # model asked to rephrase it (that is what kept re-asking the plot agent)
                accumulated = str(exc)
                capture.routed_to = _DELEGATION_TOOL_ROUTES["ask_plot_config_agent"]
                await queue.put(
                    {"event": "text_delta", "data": json.dumps({"delta": accumulated})}
                )
            except UsageLimitExceeded as exc:
                stream_exc = exc
                logger.warning(
                    "SensAI chat stopped at the limit of %d model requests: %s",
                    MAX_MODEL_REQUESTS,
                    exc,
                )
            except Exception as exc:
                stream_exc = exc
                logger.warning("SensAI chat run_stream failed", exc_info=True)
            finally:
                logger.info("SensAI chat made %d model request(s).", usage.requests)
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
            if isinstance(stream_exc, UsageLimitExceeded):
                detail = _stopped_message(capture.delegate)
            elif stream_exc:
                detail = f"No response from model: {stream_exc}"
            else:
                detail = "No response from model."
            yield {"event": "error", "data": json.dumps({"detail": detail})}
            return

        plot_config_update = _changed_plot_config(
            current_plot_config, deps.current_plot_config
        )
        yield {
            "event": "result",
            "data": json.dumps(
                {
                    "message": accumulated,
                    "plot_config_update": (
                        plot_config_update.model_dump()
                        if plot_config_update is not None
                        else None
                    ),
                    "routed_to": capture.routed_to,
                    "model": answering_model,
                }
            ),
        }

    return EventSourceResponse(event_stream())
