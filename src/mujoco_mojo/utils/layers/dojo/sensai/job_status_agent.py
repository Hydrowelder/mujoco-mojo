"""SensAI domain agent for job status - read-only, forced to answer with the current JobStatus."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent, RunContext

from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.statusing import Completion, JobStatus

from .deps import SensAIDeps

if TYPE_CHECKING:
    from mujoco_mojo.utils.statusing import StepStatus, TrialStatus

logger = get_logger(__name__)

_MAX_RANKED = 20

_SYSTEM_PROMPT = """\
You are the job-status agent inside the MuJoCo Mojo Dojo dashboard.

Answer questions about the current simulation job's progress and per-trial status using \
your tools, then finish with the current job status.

To find which trials took the longest or the shortest time, call get_trials_by_duration \
once. Do not look at trials one at a time with get_trial_details to compare them: a job \
can have hundreds, and you will run out of requests.

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
    logger.info("SensAI get_job_summary")
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
    logger.info("SensAI get_trial_breakdown")
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
    logger.info("SensAI get_trial_details: trial %s", trial_num)
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


@job_status_agent.tool
async def get_trials_by_duration(
    ctx: RunContext[SensAIDeps], count: int = 5, longest: bool = True
) -> str:
    """
    Ranks the finished trials by how long each took, so one call answers which trial was slowest or fastest. Use this instead of looking at trials one at a time.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        count: How many trials to list, such as 5 (at most 20).
        longest: True to list the trials that took the longest first, False for the ones that took the shortest first.

    Returns:
        The trials in order, each with its total time and how it ended, and how many finished trials were ranked.

    """
    logger.info("SensAI get_trials_by_duration: count=%s longest=%s", count, longest)
    job = ctx.deps.job_status
    if job is None:
        return "No job is currently loaded."

    durations: list[tuple[float, int, Completion]] = []
    for trial_num in job.trial_nums:
        status = job.get_trial_status(trial_num)
        if status is None or status.completion == Completion.INCOMPLETE:
            continue
        durations.append((status.td.total_seconds(), trial_num, status.completion))
    if not durations:
        return "No trial has finished yet, so there are no durations to rank."

    durations.sort(key=lambda item: (item[0], item[1]), reverse=longest)
    shown = durations[: max(1, min(count, _MAX_RANKED))]
    lines = [
        f"{'Longest' if longest else 'Shortest'} {len(shown)} of {len(durations)} finished trials:"
    ]
    lines += [
        f"  Trial {trial_num}: {seconds:.2f}s ({completion})"
        for seconds, trial_num, completion in shown
    ]
    return "\n".join(lines)
