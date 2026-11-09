"""A record of the tool calls made while SensAI answers one message, so the chat can show how it got to its reply."""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_ai import RunContext
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RetryPromptPart,
    ToolReturnPart,
)

ARGS_LENGTH = 200
"""The most characters of a call's arguments kept for the chat, which shows them on one line."""

RESULT_LENGTH = 300
"""The most characters of a call's result kept for the chat. A job report or the column list can be thousands, and the chat only previews it."""

CHAT_AGENT = "chat"
"""The `agent` of a call the chat agent made itself, which is a hand-off to a specialist. A specialist's own calls carry the specialist's route (`job_status`, `plot_config`, ...)."""

ToolStatus = Literal["running", "ok", "rejected", "failed"]
"""How a call went: still running, returned a result, turned away by the tool with a reason the model was told (a refused plot edit, bad arguments), or never returned (the specialist gave up or the message hit its request limit)."""


class ToolCallRecord(BaseModel):
    """One tool call, as the chat shows it."""

    id: int
    """Its place in the message, from 1, in the order the calls started."""

    name: str
    """The tool's name, such as `edit_plot_config`."""

    agent: str
    """Who called it: `chat` for a hand-off, else the specialist's route."""

    args: str
    """The arguments the model sent, as one line of JSON, cut to `ARGS_LENGTH`."""

    status: ToolStatus = "running"

    result: str | None = None
    """What the tool returned, or why it was refused, as one line cut to `RESULT_LENGTH`. None while it runs and when it never returned."""


Emit = Callable[[str, dict[str, Any]], Awaitable[None]]
"""Sends one event to the chat as it happens, by name and payload."""


def _one_line(text: str, limit: int) -> str:
    """The text with its whitespace collapsed to single spaces, cut to `limit` characters with `...` when it is longer."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else f"{flat[: limit - 3].rstrip()}..."


@dataclass
class ToolTrace:
    """
    The tool calls one chat message made, from the chat agent and from every specialist it handed the request to.

    Each agent's run gets a handler from `handler` (the chat agent's own goes through `tap`), which records a call when it starts and its outcome when it ends, and tells `emit` so the chat can show each one live. `calls` is the whole list once the message is done.
    """

    emit: Emit | None = None
    """Called with `tool_start` as a call begins and `tool_end` as it finishes, or None to only record."""

    calls: list[ToolCallRecord] = field(default_factory=list)
    """Every call so far, in the order it started."""

    _running: dict[tuple[str, str], ToolCallRecord] = field(
        default_factory=dict, init=False, repr=False
    )

    async def tap(
        self, agent: str, events: AsyncIterable[AgentStreamEvent]
    ) -> AsyncIterator[AgentStreamEvent]:
        """Records the tool calls in `events` as they pass and gives every event on, unchanged, so a caller that reads the events for something else can use it in place of `events`."""
        async for event in events:
            await self._record(agent, event)
            yield event

    def handler(
        self, agent: str
    ) -> Callable[[RunContext[Any], AsyncIterable[AgentStreamEvent]], Awaitable[None]]:
        """An `event_stream_handler` for the run of `agent` that records its tool calls and does nothing else."""

        async def record(
            _: RunContext[Any], events: AsyncIterable[AgentStreamEvent]
        ) -> None:
            async for _event in self.tap(agent, events):
                pass

        return record

    def finish(self) -> None:
        """Marks every call that never returned as failed. Call it when the message is over, since a specialist that gave up or a message that ran out of requests leaves its call open."""
        for record in self._running.values():
            record.status = "failed"
        self._running.clear()

    async def _record(self, agent: str, event: AgentStreamEvent) -> None:
        if isinstance(event, FunctionToolCallEvent):
            record = ToolCallRecord(
                id=len(self.calls) + 1,
                name=event.part.tool_name,
                agent=agent,
                args=_one_line(event.part.args_as_json_str(), ARGS_LENGTH),
            )
            self.calls.append(record)
            self._running[(agent, event.part.tool_call_id)] = record
            await self._send("tool_start", record.model_dump())
        elif isinstance(event, FunctionToolResultEvent):
            record = self._running.pop((agent, event.tool_call_id), None)
            if record is None:
                return
            part = event.part
            if isinstance(part, ToolReturnPart):
                record.status = "ok"
                text = part.model_response_str()
            else:
                record.status = "rejected"
                text = _retry_reason(part)
            record.result = _one_line(text, RESULT_LENGTH)
            await self._send(
                "tool_end",
                {"id": record.id, "status": record.status, "result": record.result},
            )

    async def _send(self, event: str, payload: dict[str, Any]) -> None:
        if self.emit is not None:
            await self.emit(event, payload)


def _retry_reason(part: RetryPromptPart) -> str:
    """Why the model was asked to try again: the tool's own message when it wrote one, else the library's description of the errors (bad arguments)."""
    return part.content if isinstance(part.content, str) else part.model_response()
