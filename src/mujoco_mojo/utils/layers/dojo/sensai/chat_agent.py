"""SensAI top-level chat agent - delegates to the domain agents and replies in plain text."""

from __future__ import annotations

from pydantic_ai import (
    Agent,
    RunContext,
    UnexpectedModelBehavior,
    UsageLimits,
)
from pydantic_ai.agent import EventStreamHandler
from pydantic_ai.models import Model

from mujoco_mojo.utils.dataframe import ColumnManifest
from mujoco_mojo.utils.log import get_logger

from .column_manifest_agent import column_manifest_agent
from .deps import SensAIDeps
from .docs_agent import docs_agent
from .job_status_agent import job_status_agent
from .plot_config_agent import plot_config_agent

_SYSTEM_PROMPT = """\
You are SensAI, an AI assistant inside the MuJoCo Mojo Dojo dashboard. You don't answer job, \
signal, plot, or how-to-use-Mojo questions yourself - you route every such request to the \
matching specialist tool and then reply to the user in a few words describing what was \
found or changed.

Always call the matching tool rather than guessing from conversation history - dashboard \
state changes between turns. Execute plot edits and profile CRUD immediately; never ask for \
confirmation. Keep your reply to 1-3 sentences, markdown allowed (bold, lists), no JSON or \
code blocks. If a specialist reports nothing is loaded (e.g. no job or plot config), say so \
plainly instead of inventing details. When a specialist gives numbers or trial numbers, repeat \
them exactly.

Questions about how to use MuJoCo Mojo itself (installing it, writing the generate or \
runtime scripts, running jobs, SLURM, the Dojo, Reloaded, requirements, optimization, the \
examples) and what changed in a release go to ask_docs_agent. Its answer comes from the Mojo \
docs and is already short, so pass it on as it is: keep its steps, its code blocks and its \
"See" link, and do not add anything the docs did not say.
"""

logger = get_logger(__name__)


class PlotEditFailed(Exception):
    """The plot agent could not make the change. The message is what to tell the user, and the chat agent is not asked to put it in its own words: a model that was told the change failed would keep sending the same request to the plot agent again."""


def usage_limits(max_requests: int) -> UsageLimits:
    """
    The cap on model requests for one chat message, to pass to the chat agent's run and to each specialist's run so that the specialists count against the same total (they share the run's `usage`).

    `max_requests` is `dojo.sensai.max_requests`. A request takes one to three (route it, edit, answer) and a refused edit adds one to three more, so the default of 12 leaves room to correct a mistake or two. When a model loops, or rate limits make every request cost several attempts, it is what stops the message from sending dozens.
    """
    return UsageLimits(request_limit=max_requests)


chat_agent: Agent[SensAIDeps, str] = Agent(
    deps_type=SensAIDeps,
    output_type=str,
    system_prompt=_SYSTEM_PROMPT,
)


def _delegate_model(ctx: RunContext[SensAIDeps]) -> Model | None:
    """
    The `Model` this run is actually using, to pass through explicitly to a delegated domain-agent `.run()` call.

    `RunContext.model` is typed as the broader `AbstractModel`, not the narrower `Model` `Agent.run(model=...)` accepts - every model `chat_agent` is ever actually run with (see `build_fallback_model`) is a real `Model`, but this narrows it properly with `isinstance` rather than asserting it, so a delegated call still fails loudly (its own "model must be set" `UserError`) instead of silently passing something invalid on the rare `AbstractModel` that isn't one.

    """
    return ctx.model if isinstance(ctx.model, Model) else None


def _watch(
    ctx: RunContext[SensAIDeps], route: str
) -> EventStreamHandler[SensAIDeps] | None:
    """The handler that records the tool calls of the specialist at `route` for the chat to show, or None when this message is not being traced (a run made outside the Dojo's chat route)."""
    trace = ctx.deps.trace
    return trace.handler(route) if trace is not None else None


@chat_agent.tool
async def ask_job_status_agent(ctx: RunContext[SensAIDeps], request: str) -> str:
    """
    Forward a job-status request to the job-status agent and return its answer.

    Args:
        ctx: The calling agent's run context - `ctx.model` (the same `FallbackModel` this run was given) has to be passed through explicitly, since `job_status_agent` has no `model=` of its own to fall back on; `ctx.deps`/`ctx.usage` share dashboard state and token accounting with the nested run the same way.
        request: The request to hand off, in natural language (e.g. "how far along is the job?", "which trials are running?" or "which trial took the longest?").

    Returns:
        The answer, in words, with the numbers and trial numbers from the job's status. Say it as it is: do not round or change them.

    """
    result = await job_status_agent.run(
        request,
        model=_delegate_model(ctx),
        deps=ctx.deps,
        usage=ctx.usage,
        usage_limits=usage_limits(ctx.deps.max_requests),
        event_stream_handler=_watch(ctx, "job_status"),
    )
    return result.output


@chat_agent.tool
async def ask_column_manifest_agent(
    ctx: RunContext[SensAIDeps], request: str
) -> ColumnManifest:
    """
    Forward a signal-column request to the column-manifest agent and return its answer.

    Args:
        ctx: The calling agent's run context - `ctx.model` (the same `FallbackModel` this run was given) has to be passed through explicitly, since `column_manifest_agent` has no `model=` of its own to fall back on; `ctx.deps`/`ctx.usage` share dashboard state and token accounting with the nested run the same way.
        request: The request to hand off, in natural language (e.g. "what signals can I plot?").

    Returns:
        The current column manifest.

    """
    result = await column_manifest_agent.run(
        request,
        model=_delegate_model(ctx),
        deps=ctx.deps,
        usage=ctx.usage,
        usage_limits=usage_limits(ctx.deps.max_requests),
        event_stream_handler=_watch(ctx, "column_manifest"),
    )
    return result.output


@chat_agent.tool
async def ask_docs_agent(ctx: RunContext[SensAIDeps], request: str) -> str:
    """
    Forward a question about how to use MuJoCo Mojo, or what changed in a release, to the docs agent and return its answer.

    Use this for "how do I..." and "what is..." questions about Mojo itself: installing it, starting a project, the generate and runtime scripts, running Monte Carlo jobs, SLURM, the Dojo, Reloaded, requirements, optimization, the examples, and what changed in a release. It answers from the Mojo docs (the user guides, the command line reference and the changelog) and links the page.

    Args:
        ctx: The calling agent's run context - `ctx.model` (the same `FallbackModel` this run was given) has to be passed through explicitly, since `docs_agent` has no `model=` of its own to fall back on; `ctx.deps`/`ctx.usage` share dashboard state and token accounting with the nested run the same way.
        request: The question, in natural language, such as "how do I submit a job to SLURM?".

    Returns:
        The answer, with the steps or code it found and a link to the page. Pass it on to the user as it is.

    """
    result = await docs_agent.run(
        request,
        model=_delegate_model(ctx),
        deps=ctx.deps,
        usage=ctx.usage,
        usage_limits=usage_limits(ctx.deps.max_requests),
        event_stream_handler=_watch(ctx, "docs"),
    )
    return result.output


@chat_agent.tool
async def ask_plot_config_agent(ctx: RunContext[SensAIDeps], request: str) -> str:
    """
    Forward a plot request to the plot-config agent and return what it did or found.

    Use this for any request about the trial viewer plot: reading its current state, changing \
    it (colors, axes, grid, signals, filters, ...), loading a saved plot profile, or versus mode \
    (showing other trials, such as the ones that failed a requirement, behind this one). The plot \
    itself is updated by the agent; you only report what it says.

    Args:
        ctx: The calling agent's run context - `ctx.model` (the same `FallbackModel` this run was given) has to be passed through explicitly, since `plot_config_agent` has no `model=` of its own to fall back on; `ctx.deps`/`ctx.usage` share dashboard state and token accounting with the nested run the same way.
        request: The request to hand off, in natural language (e.g. "make the box_acc:y line red" or "save this as robotics/baseline").

    Returns:
        A short description of what was changed or found.

    """
    ctx.deps.plot_edit_refusal = None
    try:
        result = await plot_config_agent.run(
            request,
            model=_delegate_model(ctx),
            deps=ctx.deps,
            usage=ctx.usage,
            usage_limits=usage_limits(ctx.deps.max_requests),
            event_stream_handler=_watch(ctx, "plot_config"),
        )
    except UnexpectedModelBehavior as exc:
        # the model kept repeating a refused call until it ran out of tries; its reason
        # is the reply, so it does not fail the message and the chat agent cannot retry
        reason = ctx.deps.plot_edit_refusal or "the plot-config agent could not finish."
        logger.info("SensAI plot agent gave up: %s", reason)
        raise PlotEditFailed(f"The last change could not be applied: {reason}") from exc
    return result.output
