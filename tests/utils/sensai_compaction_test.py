"""Tests for what a SensAI conversation carries on with, and how a summary of it is told apart from a conversation that only grew."""

from pydantic_ai.messages import (
    CompactionPart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import RequestUsage
from pydantic_ai_harness.compaction import (
    SummarizingCompaction,
    estimate_context_tokens,
)

from mujoco_mojo.utils.sensai.compaction import (
    KEEP_MESSAGES,
    anchored,
    context_gauge,
    overhead_tokens,
    reanchored,
    conversation_compaction,
    conversation_only,
    message_texts,
    summarized,
)


def asked(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(text)])


def said(text: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(text)])


def test_the_tool_calls_behind_an_answer_are_left_out() -> None:
    run: list[ModelMessage] = [
        asked("how do I pause?"),
        ModelResponse(
            parts=[ToolCallPart("read_docs", {"path": "reloaded.md"}, tool_call_id="1")]
        ),
        ModelRequest(
            parts=[ToolReturnPart("read_docs", "a whole page " * 500, tool_call_id="1")]
        ),
        said("Type pause."),
    ]

    kept = conversation_only(run)

    assert message_texts(kept) == ["how do I pause?", "Type pause."]


def test_a_summary_is_kept_wherever_it_is() -> None:
    run: list[ModelMessage] = [
        asked("first"),
        ModelRequest(parts=[CompactionPart(content="what was said before")]),
        ModelResponse(parts=[CompactionPart(content="a provider's own summary")]),
        said("latest"),
    ]

    assert message_texts(conversation_only(run)) == [
        "first",
        "what was said before",
        "a provider's own summary",
        "latest",
    ]


def test_a_conversation_that_only_grew_was_not_summarized() -> None:
    before = [asked("q1"), said("a1")]

    assert not summarized(before, [*before, asked("q2"), said("a2")])
    assert not summarized([], before)


def test_a_conversation_whose_start_changed_was_summarized() -> None:
    before = [asked("q1"), said("a1"), asked("q2"), said("a2")]
    after = [
        asked("q1"),
        ModelRequest(parts=[CompactionPart(content="sum")]),
        said("a2"),
    ]

    assert summarized(before, after)


def test_the_capability_summarizes_at_the_share_of_the_window_it_is_given() -> None:
    capability = conversation_compaction(0.8)

    assert isinstance(capability, SummarizingCompaction)
    assert capability.max_fraction == 0.8
    assert capability.keep_messages == KEEP_MESSAGES


def counted(text: str, input_tokens: int, output_tokens: int) -> ModelResponse:
    return ModelResponse(
        parts=[TextPart(text)],
        usage=RequestUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def test_the_last_answer_takes_the_first_requests_input_and_the_last_responses_output() -> (
    None
):
    """The first request had all the conversation that comes before the answer, and the instructions and tools; the later ones also had the tool calls, which the conversation does not keep."""
    run: list[ModelMessage] = [
        asked("how do I pause?"),
        ModelResponse(
            parts=[
                ToolCallPart("read_docs", {"path": "reloaded.md"}, tool_call_id="1")
            ],
            usage=RequestUsage(input_tokens=500, output_tokens=20),
        ),
        ModelRequest(
            parts=[ToolReturnPart("read_docs", "page " * 500, tool_call_id="1")]
        ),
        counted("Type pause.", 1100, 30),
    ]

    kept = anchored(conversation_only(run), run)

    last = kept[-1]
    assert isinstance(last, ModelResponse)
    assert (last.usage.input_tokens, last.usage.output_tokens) == (500, 30)


def test_a_model_that_reports_no_usage_leaves_the_conversation_alone() -> None:
    run: list[ModelMessage] = [asked("q"), said("a")]

    assert message_texts(anchored(conversation_only(run), run)) == ["q", "a"]
    last = anchored(conversation_only(run), run)[-1]
    assert isinstance(last, ModelResponse)
    assert last.usage.input_tokens == 0


def test_the_gauge_counts_from_the_providers_count() -> None:
    conversation: list[ModelMessage] = [
        asked("how do I pause?"),
        counted("Type pause.", 500, 30),
    ]

    gauge = context_gauge(conversation, 10_000)

    assert gauge.used_tokens == 530
    assert gauge.fraction == 0.053


def test_what_goes_with_every_request_is_the_count_less_the_conversation_before_it() -> (
    None
):
    before: list[ModelMessage] = [asked("how do I pause?")]
    conversation = [*before, counted("Type pause.", 500, 30)]

    assert overhead_tokens(conversation) == 500 - estimate_context_tokens(before)
    assert overhead_tokens([asked("q"), said("a")]) == 0


def test_a_summarized_conversation_carries_over_what_goes_with_every_request() -> None:
    summary: list[ModelMessage] = [
        asked("first"),
        ModelRequest(parts=[CompactionPart(content="what was said before")]),
        said("latest"),
    ]

    kept = reanchored(summary, 400)

    last = kept[-1]
    assert isinstance(last, ModelResponse)
    assert last.usage.input_tokens == 400 + estimate_context_tokens(summary[:-1])
    assert reanchored(summary, 0) == summary


def test_the_next_request_counts_its_instructions_once() -> None:
    """The provider's count on the answer includes the instructions it was sent with. The question keeps them, so Harness's estimate of the next request (which carries them again) swaps one set for the other rather than adding them to the count."""
    instructions = "You are the docs agent. " * 160
    run: list[ModelMessage] = [
        ModelRequest(
            parts=[UserPromptPart("how do I pause?")], instructions=instructions
        ),
        counted("Type pause.", 1500, 30),
    ]
    kept = anchored(conversation_only(run), run)
    pending = ModelRequest(
        parts=[UserPromptPart("and step?")], instructions=instructions
    )

    estimate = estimate_context_tokens([*kept, pending])
    without = [
        ModelRequest(parts=list(m.parts)) if isinstance(m, ModelRequest) else m
        for m in kept
    ]

    assert 1530 <= estimate < 1600
    # with the instructions dropped from the question, they would be counted a second time
    assert estimate_context_tokens([*without, pending]) > estimate + 500
