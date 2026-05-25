"""SensAI - Pydantic AI agent for the MuJoCo Mojo Dojo dashboard."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from mujoco_mojo.settings import SensAISettings
from mujoco_mojo.utils.layers.dojo.plot_config import PlotConfig
from mujoco_mojo.utils.statusing import JobStatus

if TYPE_CHECKING:
    from mujoco_mojo.utils.statusing import StepStatus, TrialStatus

# ---------------------------------------------------------------------------
# deps - runtime context injected into the agent and its tools
# ---------------------------------------------------------------------------


@dataclass
class SensAIDeps:
    """Runtime context available to the SensAI agent and all its tools."""

    job_status: JobStatus | None
    """The current job, or None if no job is loaded."""

    available_columns: list[str]
    """Signal column names available in the current trial's telemetry data."""

    current_plot_config: PlotConfig | None
    """The plot config currently active in the trial viewer, or None if not set."""


# ---------------------------------------------------------------------------
# result - structured output returned by every agent run
# ---------------------------------------------------------------------------


class SensAIResult(BaseModel):
    """Structured response from the SensAI agent."""

    message: str
    """The conversational reply to display in the chat panel."""

    plot_config_update: PlotConfig | None = None
    """A proposed replacement plot configuration. `None` if no change is suggested."""


# ---------------------------------------------------------------------------
# agent
# ---------------------------------------------------------------------------

_PLOT_CONFIG_SCHEMA = json.dumps(PlotConfig.model_json_schema(), indent=2)

_BASE_SYSTEM_PROMPT = f"""\
You are SensAI, an AI assistant embedded in the MuJoCo Mojo Dojo dashboard.
You help users understand their simulation job status and configure trial viewer plots.

When the user asks about job or trial status, use the available tools to fetch \
the current data rather than relying on prior context.

When the user asks you to modify a plot (e.g. add a signal, change colors, apply a \
filter, adjust the axis range), respond with a `plot_config_update` containing the \
complete updated PlotConfig. Always base it on the current config fetched via the \
`get_current_plot_config` tool - never invent fields.

The PlotConfig JSON schema is:
```json
{_PLOT_CONFIG_SCHEMA}
```

Keep replies concise. When proposing a config change, briefly explain what you changed \
and why, then include the updated config in `plot_config_update`.
"""

sensai_agent: Agent[SensAIDeps, SensAIResult] = Agent(
    deps_type=SensAIDeps,
    output_type=SensAIResult,
    system_prompt=_BASE_SYSTEM_PROMPT,
)


# ---------------------------------------------------------------------------
# tools
# ---------------------------------------------------------------------------


@sensai_agent.tool
async def get_job_summary(ctx: RunContext[SensAIDeps]) -> str:
    """Returns a high-level summary of the current job's status and progress."""
    job = ctx.deps.job_status
    if job is None:
        return "No job is currently loaded."

    lines = [
        f"Job type: {job.job_type}",
        f"Started by: {job.started_by}",
        f"Execution mode: {job.execution_mode}",
        f"Total trials: {job.n_trial}",
        f"Completed: {job.n_done} ({job.n_success} succeeded, {job.n_failed} failed)",
        f"Remaining: {job.n_remaining}",
        f"Progress: {job.progress:.1%}",
        f"Progress bar: {job.progress_bar}",
        f"Elapsed: {job.elapsed}",
        f"Average trial duration: {job.average_trial_duration}",
        f"Estimated time remaining: {job.time_remaining_average_success}",
        f"Complete: {job.is_done}",
    ]
    if job.n_done > 0:
        lines.append(f"Success rate: {job.success_rate:.1%}")
        lines.append(f"Failure rate: {job.failure_rate:.1%}")

    return "\n".join(lines)


@sensai_agent.tool
async def get_trial_breakdown(ctx: RunContext[SensAIDeps]) -> str:
    """Returns per-trial completion status. Use this when the user asks about specific trials."""
    job = ctx.deps.job_status
    if job is None:
        return "No job is currently loaded."

    success = job.success_trial_nums
    failed = job.failed_trial_nums
    pending = job.pending_trial_nums

    lines = [
        f"Succeeded ({len(success)}): {success[:50]}{'...' if len(success) > 50 else ''}",
        f"Failed ({len(failed)}): {failed[:50]}{'...' if len(failed) > 50 else ''}",
        f"Pending ({len(pending)}): {pending[:50]}{'...' if len(pending) > 50 else ''}",
    ]
    return "\n".join(lines)


@sensai_agent.tool
async def get_trial_details(ctx: RunContext[SensAIDeps], trial_num: int) -> str:
    """Returns step-level timing details for a specific trial number. Use this when the user asks about a particular trial."""
    job = ctx.deps.job_status
    if job is None:
        return "No job is currently loaded."

    status: TrialStatus | None = job.get_trial_status(trial_num)
    if status is None:
        return f"Trial {trial_num} not found in cache (may still be pending)."

    def _fmt(step_name: str, step: StepStatus) -> str:
        if step.elapsed is not None:
            return f"  {step_name}: {step.elapsed:.3f}s"
        if step.started is not None:
            return f"  {step_name}: in progress"
        return f"  {step_name}: not started"

    lines = [
        f"Trial {trial_num}:",
        f"  Completion: {status.completion}",
        f"  Current step: {status.step}",
        _fmt("pending", status.pending),
        _fmt("generating", status.generating),
        _fmt("solving", status.solving),
        f"  Total elapsed: {status.td}",
    ]
    return "\n".join(lines)


@sensai_agent.tool
async def get_available_signals(ctx: RunContext[SensAIDeps]) -> list[str]:
    """Returns the list of signal column names available in the current trial's telemetry data."""
    return ctx.deps.available_columns


@sensai_agent.tool
async def get_current_plot_config(ctx: RunContext[SensAIDeps]) -> str:
    """Returns the current trial viewer plot configuration as JSON. Always call this before proposing a config update."""
    if ctx.deps.current_plot_config is None:
        return "No plot config is currently loaded."
    return ctx.deps.current_plot_config.model_dump_json(indent=2)


# ---------------------------------------------------------------------------
# model factory
# ---------------------------------------------------------------------------


def build_model(config: SensAISettings) -> OpenAIModel:
    """Construct an OpenAIModel pointed at the configured endpoint."""
    return OpenAIModel(
        config.model_name,
        provider=OpenAIProvider(
            base_url=config.base_url,
            api_key=config.api_key.get_secret_value(),
        ),
    )
