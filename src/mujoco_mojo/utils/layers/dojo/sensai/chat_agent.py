"""SensAI top-level chat agent - delegates to the domain agents and replies in plain text."""

from __future__ import annotations

from pydantic_ai import Agent, RunContext  # pyright: ignore[reportMissingImports]
from pydantic_ai.models import Model  # pyright: ignore[reportMissingImports]

from mujoco_mojo.utils.dataframe import ColumnManifest
from mujoco_mojo.utils.layers.dojo.plot_config import PlotConfig
from mujoco_mojo.utils.statusing import JobStatus

from .column_manifest_agent import column_manifest_agent
from .deps import SensAIDeps
from .job_status_agent import job_status_agent
from .plot_config_agent import plot_config_agent

_SYSTEM_PROMPT = """\
You are SensAI, an AI assistant inside the MuJoCo Mojo Dojo dashboard. You don't answer job, \
signal, or plot questions yourself - you route every such request to the matching specialist \
tool and then reply to the user in a few words describing what was found or changed.

Always call the matching tool rather than guessing from conversation history - dashboard \
state changes between turns. Execute plot edits and profile CRUD immediately; never ask for \
confirmation. Keep your reply to 1-3 sentences, markdown allowed (bold, lists), no JSON or \
code blocks. If a specialist reports nothing is loaded (e.g. no job or plot config), say so \
plainly instead of inventing details.
"""

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


@chat_agent.tool
async def ask_job_status_agent(
    ctx: RunContext[SensAIDeps], request: str
) -> JobStatus | None:
    """
    Forward a job-status request to the job-status agent and return its answer.

    Args:
        ctx: The calling agent's run context - `ctx.model` (the same `FallbackModel` this run was given) has to be passed through explicitly, since `job_status_agent` has no `model=` of its own to fall back on; `ctx.deps`/`ctx.usage` share dashboard state and token accounting with the nested run the same way.
        request: The request to hand off, in natural language (e.g. "how far along is the job?" or "what happened on trial 12?").

    Returns:
        The current job status, or None if no job is loaded.

    """
    result = await job_status_agent.run(
        request, model=_delegate_model(ctx), deps=ctx.deps, usage=ctx.usage
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
        request, model=_delegate_model(ctx), deps=ctx.deps, usage=ctx.usage
    )
    return result.output


@chat_agent.tool
async def ask_plot_config_agent(
    ctx: RunContext[SensAIDeps], request: str
) -> PlotConfig | None:
    """
    Forward a plot request to the plot-config agent and return its answer.

    Use this for any request about the trial viewer plot: reading its current state, editing \
    it (colors, axes, grid, signals, ...), or saving/loading/deleting it as a named profile.

    Args:
        ctx: The calling agent's run context - `ctx.model` (the same `FallbackModel` this run was given) has to be passed through explicitly, since `plot_config_agent` has no `model=` of its own to fall back on; `ctx.deps`/`ctx.usage` share dashboard state and token accounting with the nested run the same way.
        request: The request to hand off, in natural language (e.g. "make the box_acc:y line red" or "save this as robotics/baseline").

    Returns:
        The resulting plot config (current, edited, saved, or loaded).

    """
    result = await plot_config_agent.run(
        request, model=_delegate_model(ctx), deps=ctx.deps, usage=ctx.usage
    )
    return result.output
