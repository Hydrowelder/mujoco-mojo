"""SensAI domain agent for job status - read-only, forced to answer with the current JobStatus."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent, RunContext  # pyright: ignore[reportMissingImports]

from mujoco_mojo.utils.statusing import JobStatus

from .deps import SensAIDeps

if TYPE_CHECKING:
    from mujoco_mojo.utils.statusing import StepStatus, TrialStatus

_SYSTEM_PROMPT = """\
You are the job-status agent inside the MuJoCo Mojo Dojo dashboard.

Answer questions about the current simulation job's progress and per-trial status using \
your tools, then finish with the current job status.

You never mutate the job - there is nothing to create, update, or delete here, only report \
on what's already running.
"""


def return_job_status(ctx: RunContext[SensAIDeps]) -> JobStatus | None:
    """
    Call this once you've gathered whatever you need to answer the request, to finish with the current job's status.

    Returns the live JobStatus directly (or None if no job is loaded) rather than asking you to reconstruct it, since re-typing every field yourself risks getting one wrong.

    """
    return ctx.deps.job_status


job_status_agent: Agent[SensAIDeps, JobStatus | None] = Agent(
    deps_type=SensAIDeps,
    output_type=return_job_status,
    system_prompt=_SYSTEM_PROMPT,
)


@job_status_agent.tool
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
        f"Completed: {job.n_done} ({job.n_success} succeeded, {job.n_failed} failed requirements, {job.n_error} errored)",
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
        lines.append(f"Requirement failure rate: {job.failure_rate:.1%}")
        lines.append(f"Error rate: {job.error_rate:.1%}")

    return "\n".join(lines)


@job_status_agent.tool
async def get_trial_breakdown(ctx: RunContext[SensAIDeps]) -> str:
    """Returns per-trial completion status. Use this when the user asks about specific trials."""
    job = ctx.deps.job_status
    if job is None:
        return "No job is currently loaded."

    success = job.success_trial_nums
    failed = job.failed_trial_nums
    errored = job.error_trial_nums
    pending = job.pending_trial_nums

    lines = [
        f"Succeeded ({len(success)}): {success[:50]}{'...' if len(success) > 50 else ''}",
        f"Failed requirements ({len(failed)}): {failed[:50]}{'...' if len(failed) > 50 else ''}",
        f"Errored ({len(errored)}): {errored[:50]}{'...' if len(errored) > 50 else ''}",
        f"Pending ({len(pending)}): {pending[:50]}{'...' if len(pending) > 50 else ''}",
    ]
    return "\n".join(lines)


@job_status_agent.tool
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
