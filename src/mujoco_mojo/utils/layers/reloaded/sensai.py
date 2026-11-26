"""Reloaded's `sensai` command, which answers a question about how to use Mojo from the docs. Importing this needs the `sensai` extra (pydantic-ai)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic_ai.exceptions import UsageLimitExceeded

from mujoco_mojo.settings import MujocoMojoSettings
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.sensai import build_fallback_model, usage_limits
from mujoco_mojo.utils.sensai.agents.docs import docs_agent

logger = get_logger(__name__)


@dataclass(frozen=True)
class Answer:
    """What SensAI said, and which model said it."""

    text: str
    """The answer, as markdown."""

    model: str | None
    """The model that wrote it, which a fallback chain reports as the one of its models that answered, or None when that is not known."""


class NoAnswer(Exception):
    """SensAI gave no answer. The message says why, for the log."""


def ask(question: str) -> Answer:
    """
    Puts `question` to SensAI's docs agent and waits for the answer, so call it from a thread of its own.

    Reloaded has no job, trial or plot for SensAI's other specialists to read, so the docs agent is the only one it has. It is asked directly and not through the Dojo's chat agent, which would spend a model request routing the question and another passing the answer on.

    Raises:
        NoAnswer: SensAI or its docs feature is off, no model is set, the question ran out of model requests, or the model failed.

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
        model = build_fallback_model()
    except ValueError as exc:
        raise NoAnswer(str(exc)) from exc
    try:
        result = asyncio.run(
            docs_agent.run(
                question,
                model=model,
                usage_limits=usage_limits(settings.max_requests),
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
    return Answer(text=result.output, model=result.response.model_name)
