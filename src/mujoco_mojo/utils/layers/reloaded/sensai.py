"""Reloaded's `sensai` command, which answers a question about how to use Mojo from the docs. Importing this needs the `sensai` extra (pydantic-ai)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai_harness.compaction import compact_now

from mujoco_mojo.settings import MujocoMojoSettings, SensAISettings
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.sensai import build_fallback_model, usage_limits
from mujoco_mojo.utils.sensai.agents.docs import docs_agent
from mujoco_mojo.utils.sensai.model import smallest_context_window
from mujoco_mojo.utils.sensai.compaction import (
    KEEP_ON_REQUEST,
    ContextGauge,
    anchored,
    context_gauge,
    conversation_compaction,
    conversation_only,
    overhead_tokens,
    reanchored,
    summarized,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class Answer:
    """What SensAI said, which model said it, and the conversation to go on from."""

    text: str
    """The answer, as markdown."""

    model: str | None
    """The model that wrote it, which a fallback chain reports as the one of its models that answered, or None when that is not known."""

    history: list[ModelMessage]
    """The conversation with this question and answer added, without the tool calls behind them, to send with the next question."""

    context: ContextGauge
    """How full the context is with `history`."""

    compacted: bool = False
    """Whether the conversation filled `sensai.compact_at` of the context window, so its earlier part was summarized before the answer."""


@dataclass(frozen=True)
class Compacted:
    """A conversation summarized on request, and how full the context is with it."""

    history: list[ModelMessage]
    context: ContextGauge


class NoAnswer(Exception):
    """SensAI gave no answer. The message says why, for the log."""


def _ready() -> tuple[SensAISettings, FallbackModel]:
    """
    SensAI's settings and the models to ask, once it is sure there is something to ask.

    Raises:
        NoAnswer: SensAI or its docs feature is off, or no model is set.

    """
    settings = MujocoMojoSettings().sensai
    if not settings.enabled:
        raise NoAnswer(
            "SensAI is off. Turn it on with `mujoco-mojo settings set sensai.enabled true`, and add a model to `sensai.models`."
        )
    if not settings.features.docs:
        raise NoAnswer(
            "SensAI's Docs feature is off, and it is the only one Reloaded has. Turn it on with `mujoco-mojo settings set sensai.features.docs true`."
        )
    try:
        return settings, build_fallback_model()
    except ValueError as exc:
        raise NoAnswer(str(exc)) from exc


def ask(question: str, history: Sequence[ModelMessage] = ()) -> Answer:
    """
    Puts `question` to SensAI's docs agent and waits for the answer, so call it from a thread of its own. `history` is the conversation so far (an earlier `Answer.history`), which is sent along so a question can refer back to it, and summarized first when it fills `sensai.compact_at` of the context window.

    Reloaded has no job, trial or plot for SensAI's other specialists to read, so the docs agent is the only one it has. It is asked directly and not through the Dojo's chat agent, which would spend a model request routing the question and another passing the answer on.

    Raises:
        NoAnswer: SensAI or its docs feature is off, no model is set, the question ran out of model requests, or the model failed.

    """
    settings, model = _ready()
    window = smallest_context_window(settings.models, model)
    try:
        result = asyncio.run(
            docs_agent.run(
                question,
                model=model,
                message_history=list(history),
                usage_limits=usage_limits(settings.max_requests),
                capabilities=[
                    conversation_compaction(settings.compact_at, context_window=window)
                ],
            )
        )
    except UsageLimitExceeded as exc:
        raise NoAnswer(
            f"SensAI stopped after {settings.max_requests} model requests without finishing. Try asking about one thing at a time. The limit is sensai.max_requests in settings."
        ) from exc
    except Exception as exc:
        # the traceback is for mojo.log: the pane already gets the reason, in one line
        logger.warning(
            "SensAI could not answer", exc_info=True, extra={"file_only": True}
        )
        raise NoAnswer(f"No answer from the model: {exc}") from exc
    conversation = anchored(
        conversation_only(result.all_messages()), result.new_messages()
    )
    return Answer(
        text=result.output,
        model=result.response.model_name,
        history=conversation,
        context=context_gauge(conversation, window),
        compacted=summarized(history, conversation),
    )


def compact(history: Sequence[ModelMessage]) -> Compacted:
    """
    Summarizes the conversation so far, all but its first question and its latest question and answer, and gives back what it goes on from. Call it from a thread of its own.

    Raises:
        NoAnswer: SensAI or its docs feature is off, no model is set, or the model failed.

    """
    settings, model = _ready()
    try:
        compacted = asyncio.run(
            compact_now(
                conversation_compaction(settings.compact_at, KEEP_ON_REQUEST),
                list(history),
                model=model,
            )
        )
    except Exception as exc:
        logger.warning(
            "SensAI could not summarize", exc_info=True, extra={"file_only": True}
        )
        raise NoAnswer(f"Could not summarize the conversation: {exc}") from exc
    # the summary leaves no provider count that fits, so what goes with every request is carried over
    conversation = reanchored(conversation_only(compacted), overhead_tokens(history))
    window = smallest_context_window(settings.models, model)
    return Compacted(history=conversation, context=context_gauge(conversation, window))
