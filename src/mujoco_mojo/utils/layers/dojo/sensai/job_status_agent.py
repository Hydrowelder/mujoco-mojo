"""SensAI domain agent for job status: read-only, and it answers in words from what its tools worked out."""

from __future__ import annotations

import asyncio

from pydantic_ai import Agent, RunContext

from mujoco_mojo.utils.log import get_logger

from . import job_report
from .deps import SensAIDeps
from .job_report import LogLevel, Outcome

logger = get_logger(__name__)

NO_JOB = "No job is currently loaded."

_SYSTEM_PROMPT = """\
You are the job-status agent inside the MuJoCo Mojo Dojo dashboard. You answer questions \
about the current simulation job (its progress, its trials, how long they took, which are \
running, which failed and why) using your tools, and you only report: nothing here changes \
the job.

Your tools, each with an example call:
- get_job_summary: progress, counts, timing and the estimate of what is left. get_job_summary()
- get_running_trials: which trials are running now, in which step, for how long. \
get_running_trials()
- get_recent_trials: the trials that finished last, newest first, with what failed or why \
they errored. get_recent_trials(count=5, outcome="error")
- get_trials_by_duration: the slowest or fastest trials. \
get_trials_by_duration(count=5, longest=True, outcome="completed")
- get_duration_statistics: the typical, median and spread of trial times, the time in each \
step, and how fast trials are finishing. get_duration_statistics()
- get_completion_timeline: when trials finished, in slices of the job's life, to see a \
slowdown, a stall or when errors began. get_completion_timeline()
- get_requirement_results: how each requirement did; with a name, the trials that missed it \
and why. get_requirement_results(requirement="")
- get_errored_trials: the trials that errored, grouped by what their logs say went wrong. \
get_errored_trials()
- get_trial_log: the end of one trial's log. get_trial_log(trial_num=12, count=20, level="error")
- get_trial_breakdown: the trial numbers that succeeded, failed, errored, are running or \
are waiting to start. get_trial_breakdown()
- get_trial_details: one trial's steps, time and requirement results. get_trial_details(trial_num=12)
- compare_trials: trials side by side. compare_trials(trial_nums=[3, 7])
- get_job_configuration: what the job was started with (seed, processes, arguments, the \
generator and runtime). get_job_configuration()

Rules:
- Get every number from a tool. Never estimate or guess, and never describe something no \
tool told you.
- Use one tool for a question that spans the whole job. To compare trials by time call \
get_trials_by_duration once; do not look at trials one at a time with get_trial_details, \
since a job can have hundreds and you will run out of requests. To compare chosen trials \
call compare_trials once with all their numbers.
- Answer in a few short sentences or a short list, with the exact numbers and trial numbers \
the tools gave, in the units they gave. If a tool says there is no job, or nothing yet, say \
that plainly.
- To say why a trial errored use get_errored_trials, which reads each trial's log, or \
get_trial_log for the log of one trial. Say what the log says. If there is no log, or no \
error in it, say that and do not invent a cause.
"""

job_status_agent: Agent[SensAIDeps, str] = Agent(
    deps_type=SensAIDeps,
    output_type=str,
    system_prompt=_SYSTEM_PROMPT,
)


@job_status_agent.tool
async def get_job_summary(ctx: RunContext[SensAIDeps]) -> str:
    """Returns a high-level summary of the current job's status and progress: counts, how many trials are running and waiting, timing and the estimate of what is left."""
    logger.info("SensAI get_job_summary")
    job = ctx.deps.job_status
    return NO_JOB if job is None else job_report.describe_summary(job, job_report.now())


@job_status_agent.tool
async def get_running_trials(ctx: RunContext[SensAIDeps]) -> str:
    """Returns the trials running right now, each with the step it is in, how long it has been in that step and how long it has been running in all, the longest running first."""
    logger.info("SensAI get_running_trials")
    job = ctx.deps.job_status
    return NO_JOB if job is None else job_report.describe_running(job, job_report.now())


@job_status_agent.tool
async def get_trials_by_duration(
    ctx: RunContext[SensAIDeps],
    count: int = 5,
    longest: bool = True,
    outcome: Outcome = "completed",
) -> str:
    """
    Ranks the finished trials by how long each took, so one call answers which trial was slowest or fastest. Use this instead of looking at trials one at a time.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        count: How many trials to list, such as 5 (at most 20).
        longest: True to list the trials that took the longest first, False for the ones that took the shortest first.
        outcome: Which trials to rank. "completed" (the default) is the successes and the ones that missed a requirement, as the job's own average is taken over. "success", "failure" (missed a requirement) or "error" (crashed) ranks only those, such as outcome="failure" for the slowest trial that failed. "any" ranks every finished trial, errored ones too.

    Returns:
        The trials in order, each with its total time and how it ended, and how many finished trials were ranked.

    """
    logger.info(
        "SensAI get_trials_by_duration: count=%s longest=%s outcome=%s",
        count,
        longest,
        outcome,
    )
    job = ctx.deps.job_status
    if job is None:
        return NO_JOB
    return job_report.describe_ranking(job, count, longest, outcome)


@job_status_agent.tool
async def get_duration_statistics(ctx: RunContext[SensAIDeps]) -> str:
    """Returns how long the completed trials took as a spread (fastest, median, mean, 90th percentile, slowest), by how they ended, the time in each step (generating and solving) and how many trials finish per minute."""
    logger.info("SensAI get_duration_statistics")
    job = ctx.deps.job_status
    return NO_JOB if job is None else job_report.describe_duration_statistics(job)


@job_status_agent.tool
async def get_requirement_results(
    ctx: RunContext[SensAIDeps], requirement: str = ""
) -> str:
    """
    Returns how each requirement did across the trials, most failures first. With a requirement named, also the trials that missed it and the reasons they gave.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        requirement: Leave it out for every requirement. To look into one, its name or part of it, such as "touchdown_speed".

    Returns:
        Pass and fail counts and rates, and for a named requirement the failing trial numbers and the messages.

    """
    logger.info("SensAI get_requirement_results: %r", requirement)
    job = ctx.deps.job_status
    return NO_JOB if job is None else job_report.describe_requirements(job, requirement)


@job_status_agent.tool
async def get_errored_trials(ctx: RunContext[SensAIDeps]) -> str:
    """Returns the trials that errored (crashed with an exception, as opposed to missing a requirement), grouped by what each trial's log says went wrong (the exception), with the step each was in when it broke."""
    logger.info("SensAI get_errored_trials")
    job = ctx.deps.job_status
    if job is None:
        return NO_JOB
    return await asyncio.to_thread(job_report.describe_errored, job)


@job_status_agent.tool
async def get_trial_breakdown(ctx: RunContext[SensAIDeps]) -> str:
    """Returns the trial numbers in each state: succeeded, failed requirements, errored, running and waiting to start."""
    logger.info("SensAI get_trial_breakdown")
    job = ctx.deps.job_status
    return (
        NO_JOB if job is None else job_report.describe_breakdown(job, job_report.now())
    )


@job_status_agent.tool
async def get_trial_details(ctx: RunContext[SensAIDeps], trial_num: int) -> str:
    """
    Returns one trial's details: how it ended, the time of each step, how long it has run so far if it is running, and the result of each requirement with its message.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        trial_num: The number of the trial, such as 12.

    Returns:
        The trial's steps, total time and requirement results, and for an errored one what its log says went wrong.

    """
    logger.info("SensAI get_trial_details: trial %s", trial_num)
    job = ctx.deps.job_status
    if job is None:
        return NO_JOB
    return await asyncio.to_thread(
        job_report.describe_trial, job, trial_num, job_report.now()
    )


@job_status_agent.tool
async def get_job_configuration(ctx: RunContext[SensAIDeps]) -> str:
    """Returns how the job was started: its type, who started it and when, the execution mode, the number of processes, the seed, the working folder, the generator and runtime, and the --arg and --kwarg values it ran with."""
    logger.info("SensAI get_job_configuration")
    job = ctx.deps.job_status
    return NO_JOB if job is None else job_report.describe_configuration(job)


@job_status_agent.tool
async def get_recent_trials(
    ctx: RunContext[SensAIDeps], count: int = 5, outcome: Outcome = "any"
) -> str:
    """
    Lists the trials that finished most recently, newest first, each with how long ago it finished and how long it took, and for a failure the requirements it missed or for an error what its log says.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        count: How many trials to list, such as 5 (at most 20).
        outcome: Which trials to list. "any" (the default) is every finished trial. "success", "failure" (missed a requirement) or "error" (crashed) lists only those, such as outcome="error" for the latest errors. "completed" is the successes and the failures together.

    Returns:
        The trials, newest first, and how many finished in all.

    """
    logger.info("SensAI get_recent_trials: count=%s outcome=%s", count, outcome)
    job = ctx.deps.job_status
    if job is None:
        return NO_JOB
    return await asyncio.to_thread(
        job_report.describe_recent, job, job_report.now(), count, outcome
    )


@job_status_agent.tool
async def get_completion_timeline(ctx: RunContext[SensAIDeps]) -> str:
    """Returns when trials finished: the job's life so far in equal time slices, each with how many trials finished, how they ended and their mean time, so a slowdown, a stall, or the time errors began can be seen."""
    logger.info("SensAI get_completion_timeline")
    job = ctx.deps.job_status
    if job is None:
        return NO_JOB
    return job_report.describe_timeline(job, job_report.now())


@job_status_agent.tool
async def get_trial_log(
    ctx: RunContext[SensAIDeps],
    trial_num: int,
    count: int = 20,
    level: LogLevel = "any",
) -> str:
    """
    Returns the end of one trial's log: each entry's time, level and message, with a long traceback cut to its first and last lines.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        trial_num: The number of the trial, such as 12.
        count: How many of the last entries to show, such as 20 (at most 30).
        level: Which entries to show. "any" (the default) is all of them, "warning" is warnings and worse, "error" is errors only, such as level="error" to find what went wrong.

    Returns:
        The last entries of the trial's log, oldest first, or that the trial has no log.

    """
    logger.info(
        "SensAI get_trial_log: trial %s count=%s level=%s", trial_num, count, level
    )
    job = ctx.deps.job_status
    if job is None:
        return NO_JOB
    return await asyncio.to_thread(
        job_report.describe_trial_log, job, trial_num, count, level
    )


@job_status_agent.tool
async def compare_trials(ctx: RunContext[SensAIDeps], trial_nums: list[int]) -> str:
    """
    Compares trials side by side: how each ended, its time in each step, which requirements differ between them, and for an errored one what its log says.

    Args:
        ctx: The run context holding the dashboard state; it is not something you send.
        trial_nums: The numbers of the trials to compare, two to six, such as [3, 7].

    Returns:
        The trials compared line by line, with how much longer the slowest took than the fastest.

    """
    logger.info("SensAI compare_trials: %s", trial_nums)
    job = ctx.deps.job_status
    if job is None:
        return NO_JOB
    return await asyncio.to_thread(
        job_report.describe_comparison, job, trial_nums, job_report.now()
    )
