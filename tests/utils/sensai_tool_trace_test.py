"""Tests for the record SensAI keeps of the tool calls a message made, which the chat shows under the reply."""

import asyncio
from collections.abc import AsyncIterator, Iterable
from typing import Any

from pydantic_ai import RunContext, RunUsage
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)

from pydantic_ai.models.test import TestModel

from mujoco_mojo.utils.layers.dojo.sensai.tool_trace import (
    ARGS_LENGTH,
    RESULT_LENGTH,
    ToolTrace,
)


def started(name: str, call_id: str, **args: Any) -> FunctionToolCallEvent:
    return FunctionToolCallEvent(part=ToolCallPart(name, args, tool_call_id=call_id))


def returned(name: str, call_id: str, content: Any) -> FunctionToolResultEvent:
    return FunctionToolResultEvent(
        part=ToolReturnPart(name, content, tool_call_id=call_id)
    )


def retried(name: str, call_id: str, content: Any) -> FunctionToolResultEvent:
    return FunctionToolResultEvent(
        part=RetryPromptPart(content, tool_name=name, tool_call_id=call_id)
    )


async def stream(events: Iterable[AgentStreamEvent]) -> AsyncIterator[AgentStreamEvent]:
    for event in events:
        yield event


def watch(
    events: Iterable[AgentStreamEvent], agent: str = "chat"
) -> tuple[ToolTrace, list[tuple[str, dict[str, Any]]]]:
    """Run the events through a trace and return it with what it sent, in order."""
    sent: list[tuple[str, dict[str, Any]]] = []

    async def emit(event: str, payload: dict[str, Any]) -> None:
        sent.append((event, payload))

    trace = ToolTrace(emit=emit)

    async def run() -> None:
        async for _ in trace.tap(agent, stream(events)):
            pass

    asyncio.run(run())
    return trace, sent


class TestRecording:
    def test_a_call_and_its_result_are_one_record(self) -> None:
        trace, _ = watch(
            [
                started("add_signals", "a", names=["x"]),
                returned("add_signals", "a", "Added x."),
            ],
            agent="plot_config",
        )

        [call] = trace.calls
        assert (call.id, call.name, call.agent, call.status, call.result) == (
            1,
            "add_signals",
            "plot_config",
            "ok",
            "Added x.",
        )
        assert call.args == '{"names":["x"]}'

    def test_calls_are_numbered_in_the_order_they_start(self) -> None:
        trace, _ = watch(
            [
                started("a", "1"),
                started("b", "2"),
                returned("b", "2", "B"),
                returned("a", "1", "A"),
            ]
        )

        assert [(c.id, c.name, c.result) for c in trace.calls] == [
            (1, "a", "A"),
            (2, "b", "B"),
        ]

    def test_it_sends_a_start_when_a_call_begins_and_an_end_when_it_returns(
        self,
    ) -> None:
        _, sent = watch([started("a", "1"), returned("a", "1", "done")])

        assert [name for name, _ in sent] == ["tool_start", "tool_end"]
        assert sent[0][1]["status"] == "running"
        assert sent[1][1] == {"id": 1, "status": "ok", "result": "done"}

    def test_a_call_the_tool_turned_away_is_rejected_with_its_reason(self) -> None:
        trace, _ = watch(
            [
                started("edit_plot_config", "1"),
                retried("edit_plot_config", "1", "no field `bogus`"),
            ]
        )

        assert trace.calls[0].status == "rejected"
        assert trace.calls[0].result == "no field `bogus`"

    def test_bad_arguments_are_rejected_with_the_errors_described(self) -> None:
        errors = [
            {"type": "missing", "loc": ("names",), "msg": "Field required", "input": {}}
        ]
        trace, _ = watch(
            [started("add_signals", "1"), retried("add_signals", "1", errors)]
        )

        assert trace.calls[0].status == "rejected"
        assert "Field required" in (trace.calls[0].result or "")

    def test_a_call_that_never_returned_is_failed_once_the_message_is_over(
        self,
    ) -> None:
        trace, _ = watch(
            [started("a", "1"), started("b", "2"), returned("b", "2", "B")]
        )
        assert trace.calls[0].status == "running"

        trace.finish()

        assert [c.status for c in trace.calls] == ["failed", "ok"]
        assert trace.calls[0].result is None

    def test_the_same_call_id_in_two_agents_is_two_calls(self) -> None:
        """A model that numbers its calls from 1 in every run must not have a specialist's result land on the chat agent's call."""
        trace = ToolTrace()

        async def run() -> None:
            async for _ in trace.tap("chat", stream([started("ask", "1")])):
                pass
            async for _ in trace.tap(
                "plot_config",
                stream([started("edit", "1"), returned("edit", "1", "ok")]),
            ):
                pass
            async for _ in trace.tap("chat", stream([returned("ask", "1", "done")])):
                pass

        asyncio.run(run())

        assert [(c.agent, c.name, c.result) for c in trace.calls] == [
            ("chat", "ask", "done"),
            ("plot_config", "edit", "ok"),
        ]

    def test_a_result_with_no_call_is_ignored(self) -> None:
        trace, sent = watch([returned("a", "never-started", "x")])

        assert trace.calls == []
        assert sent == []

    def test_events_pass_through_unchanged_for_whoever_reads_them_next(self) -> None:
        events = [started("a", "1"), returned("a", "1", "x")]
        trace = ToolTrace()
        seen: list[AgentStreamEvent] = []

        async def run() -> None:
            async for event in trace.tap("chat", stream(events)):
                seen.append(event)

        asyncio.run(run())

        assert seen == events

    def test_a_trace_with_nothing_to_send_to_only_records(self) -> None:
        trace = ToolTrace()

        async def run() -> None:
            handler = trace.handler("guide")
            # a handler is given the run's context, which it does not use
            ctx = RunContext(deps=None, model=TestModel(), usage=RunUsage())
            await handler(ctx, stream([started("a", "1")]))

        asyncio.run(run())

        assert [c.name for c in trace.calls] == ["a"]


class TestWhatIsKept:
    def test_whitespace_is_collapsed_so_a_report_is_one_line(self) -> None:
        trace, _ = watch(
            [
                started("a", "1"),
                returned("a", "1", "Trial 3:\n  12.5 s\n\nTrial 4:\t9 s"),
            ]
        )

        assert trace.calls[0].result == "Trial 3: 12.5 s Trial 4: 9 s"

    def test_a_long_result_is_cut_with_an_ellipsis(self) -> None:
        trace, _ = watch([started("a", "1"), returned("a", "1", "word " * 500)])

        result = trace.calls[0].result or ""
        assert len(result) <= RESULT_LENGTH
        assert result.endswith("...")

    def test_a_result_that_fits_is_kept_whole(self) -> None:
        text = "x" * RESULT_LENGTH
        trace, _ = watch([started("a", "1"), returned("a", "1", text)])

        assert trace.calls[0].result == text

    def test_long_arguments_are_cut_with_an_ellipsis(self) -> None:
        trace, _ = watch([started("a", "1", names=["Bodies/box1/xpos:x"] * 50)])

        args = trace.calls[0].args
        assert len(args) <= ARGS_LENGTH
        assert args.endswith("...")

    def test_a_structured_result_is_kept_as_text(self) -> None:
        trace, _ = watch(
            [started("a", "1"), returned("a", "1", {"all": ["time", "x"]})]
        )

        assert "time" in (trace.calls[0].result or "")
