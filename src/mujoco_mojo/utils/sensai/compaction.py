"""How SensAI keeps a long conversation going: the older part is summarized, by the model that answers, once the conversation fills most of the context window or when the user asks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic_ai.messages import (
    CompactionPart,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.usage import RequestUsage
from pydantic_ai_harness.compaction import (
    DEFAULT_CONTEXT_WINDOW,
    SummarizingCompaction,
    estimate_context_tokens,
)

KEEP_MESSAGES = 10
"""How many messages at the end of a conversation an automatic summary leaves as they are: the latest five questions and their answers."""

KEEP_ON_REQUEST = 2
"""How many a summary the user asks for leaves as they are: the latest question and its answer."""


def conversation_compaction(
    compact_at: float,
    keep_messages: int = KEEP_MESSAGES,
    context_window: int | None = None,
) -> SummarizingCompaction[Any]:
    """The capability that summarizes the older part of a conversation once it fills `compact_at` of the context window, with the model that answers, keeping the first question and the latest `keep_messages` messages as they are. `context_window` is the window in tokens (`smallest_context_window`); None leaves it to the model, or to Harness's default when the model does not know."""
    return SummarizingCompaction(
        max_fraction=compact_at,
        keep_messages=keep_messages,
        context_window=context_window,
    )


def conversation_only(messages: Sequence[ModelMessage]) -> list[ModelMessage]:
    """
    The messages a conversation is carried on with: the questions, the answers and any summary of earlier ones, without the tool calls behind each answer.

    A page the docs agent read can run to thousands of characters, and sent along with every later question it would fill the context with what the answer already says.
    """
    kept: list[ModelMessage] = []
    for message in messages:
        if isinstance(message, ModelRequest):
            parts = [
                part
                for part in message.parts
                if isinstance(part, (UserPromptPart, CompactionPart))
            ]
            if parts:
                # the instructions stay: the provider count on the answer after them includes
                # them, and Harness's estimate adds a request's instructions to a count that
                # was made without them, so without them here they would be counted twice
                kept.append(
                    ModelRequest(parts=parts, instructions=message.instructions)
                )
        elif not message.tool_calls:
            parts = [
                part
                for part in message.parts
                if isinstance(part, (TextPart, CompactionPart))
            ]
            if parts:
                kept.append(ModelResponse(parts=parts, model_name=message.model_name))
    return kept


def anchored(
    conversation: list[ModelMessage], run: Sequence[ModelMessage]
) -> list[ModelMessage]:
    """
    `conversation` (from `conversation_only`) with its last answer carrying the provider's own count of the context up to it: the input tokens of the run's first request and the answer's output tokens.

    That first request was everything before the answer in `conversation` (the conversation so far and the question) together with what goes with every request (the instructions and the tool definitions), which no estimate of the conversation's text sees. Harness's `estimate_context_tokens` counts from the latest answer with provider usage, so the gauge and the summary's trigger both count all of it. `run` is the run's own messages (`new_messages()`), whose tool calls the conversation no longer has; a model that reports no usage leaves `conversation` as it is.
    """
    responses = [message for message in run if isinstance(message, ModelResponse)]
    if not responses or not conversation:
        return conversation
    last = conversation[-1]
    sent = responses[0].usage.input_tokens
    if not isinstance(last, ModelResponse) or not sent:
        return conversation
    usage = RequestUsage(
        input_tokens=sent, output_tokens=responses[-1].usage.output_tokens
    )
    return [*conversation[:-1], replace(last, usage=usage)]


def _latest_anchor(
    conversation: Sequence[ModelMessage],
) -> tuple[int, ModelResponse] | None:
    """The latest answer in `conversation` with a provider count, and where it is."""
    for index in range(len(conversation) - 1, -1, -1):
        message = conversation[index]
        if isinstance(message, ModelResponse) and message.usage.input_tokens:
            return index, message
    return None


def overhead_tokens(conversation: Sequence[ModelMessage]) -> int:
    """What goes with every request besides the conversation (the instructions and the tool definitions): the latest provider count in `conversation` less the estimate of the messages it counted, or 0 when there is no provider count."""
    anchor = _latest_anchor(conversation)
    if anchor is None:
        return 0
    index, message = anchor
    return max(
        message.usage.input_tokens - estimate_context_tokens(conversation[:index]), 0
    )


def reanchored(conversation: list[ModelMessage], overhead: int) -> list[ModelMessage]:
    """`conversation`, freshly summarized and so with no provider count that still fits it, with its last answer given one: `overhead` and the estimate of what comes before the answer, so the summarized conversation is counted with what goes with every request too."""
    if (
        not overhead
        or not conversation
        or not isinstance(conversation[-1], ModelResponse)
    ):
        return conversation
    *before, last = conversation
    usage = RequestUsage(
        input_tokens=overhead + estimate_context_tokens(before),
        output_tokens=estimate_context_tokens([last]),
    )
    return [*before, replace(last, usage=usage)]


def message_texts(messages: Sequence[ModelMessage]) -> list[str]:
    """The text of each part of `messages`, in order, which is what tells one conversation from another."""
    return [
        str(part.content)
        for message in messages
        for part in message.parts
        if isinstance(part, (UserPromptPart, TextPart, CompactionPart))
    ]


def summarized(before: Sequence[ModelMessage], after: Sequence[ModelMessage]) -> bool:
    """Whether `after` is `before` with part of it summarized, and not only `before` with more added to its end."""
    old = message_texts(before)
    return message_texts(after)[: len(old)] != old


class ContextGauge(BaseModel):
    """How much of the context window the conversation so far takes up, with what goes with every request (the instructions and the tool definitions, from the provider's own count on the latest answer): what the next question starts from, counted the way the summary's trigger counts it, so a summary comes when this reaches `sensai.compact_at`. What one answer reads on its way (a page of the docs) is not in it, since the conversation does not keep it."""

    model_config = ConfigDict(frozen=True)

    used_tokens: int
    """The conversation's estimated tokens."""

    window_tokens: int
    """The context window it is measured against."""

    known_window: bool
    """Whether `window_tokens` is the models' real window, and not Harness's 200K guess for a model whose window is not known."""

    @property
    def fraction(self) -> float:
        """`used_tokens` as a share of the window."""
        return self.used_tokens / self.window_tokens


def context_gauge(
    conversation: Sequence[ModelMessage], window: int | None
) -> ContextGauge:
    """How full the context is with `conversation`, against `window` tokens (`smallest_context_window`), or Harness's default when that is None."""
    return ContextGauge(
        used_tokens=estimate_context_tokens(conversation),
        window_tokens=window or DEFAULT_CONTEXT_WINDOW,
        known_window=window is not None,
    )
