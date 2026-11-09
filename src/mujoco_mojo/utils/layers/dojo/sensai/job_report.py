"""
What SensAI's job agent can say about a job: which trials are running, how long they took, what failed, how it was started.

Each `describe_*` function works one thing out from a `JobStatus` and returns it as text for a model to read. They are the answers that are hard to put together by hand from the Dojo (the ranking of two hundred trials by time, the failures grouped by requirement, how long the trials running now have been at it), and none of them changes the job.

The clock is `now()` so a test can set it. A trial's time comes from the status files, which record when each step started and, once it ends, how long it took, so a step that is still running has a start and no length.
"""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Any, Literal

from pydantic import BaseModel

from mujoco_mojo.utils.statusing import (
    FAILED_COMPLETIONS,
    TIMED_COMPLETIONS,
    Completion,
    JobStatus,
    JobType,
    TrialStatus,
)

from ..trial_log import find_log_file, parse_log_file

__all__ = [
    "LogLevel",
    "Outcome",
    "RunningTrial",
    "describe_breakdown",
    "describe_comparison",
    "describe_configuration",
    "describe_duration_statistics",
    "describe_errored",
    "describe_ranking",
    "describe_recent",
    "describe_requirements",
    "describe_running",
    "describe_summary",
    "describe_timeline",
    "describe_trial",
    "describe_trial_log",
    "error_line",
    "fmt_duration",
    "now",
    "running_trials",
    "trial_log",
]

Outcome = Literal["any", "completed", "success", "failure", "error"]
"""Which finished trials to look at: any that finished, those that completed (a success or a missed requirement, the ones the job's own times are averaged over), only the successes, only those that missed a requirement, or only those that errored."""

LogLevel = Literal["any", "warning", "error"]
"""Which log entries to show: all of them, warnings and worse, or errors only."""

_OUTCOMES: dict[Outcome, tuple[set[Completion], str]] = {
    "any": ({c for c in Completion if c != Completion.INCOMPLETE}, ""),
    "completed": (TIMED_COMPLETIONS, "completed"),
    "success": ({Completion.SUCCESS}, "successful"),
    "failure": (FAILED_COMPLETIONS, "requirement-failing"),
    "error": ({Completion.ERROR}, "errored"),
}

_MAX_LISTED = 20
_MAX_NUMBERS = 50
_MAX_REASONS = 5
_REASON_LENGTH = 160
_MAX_LOGS_READ = 50
_MAX_COMPARED = 6
_MAX_LOG_ENTRIES = 30
_LOG_ENTRY_LINES = 6
_LOG_LINE_LENGTH = 300
_MAX_LOG_CHARS = 6000
_TIMELINE_SLICES = 8
_STEPS = ("pending", "generating", "solving")

_LOG_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
_MIN_LOG_LEVEL: dict[LogLevel, int] = {"any": 0, "warning": 30, "error": 40}
_TRACEBACK = "Traceback (most recent call last):"


def now() -> datetime:
    """The current time, which tests replace."""
    return datetime.now(UTC)


def fmt_duration(seconds: float) -> str:
    """A time as `9.50s`, and a minute or more also as minutes and hours, as `75.30s (1m 15s)`."""
    text = f"{seconds:.2f}s"
    if seconds < 60:
        return text
    hours, rest = divmod(round(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    parts = [f"{hours}h"] if hours else []
    if hours or minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return f"{text} ({' '.join(parts)})"


def trial_numbers(trial_nums: Iterable[int], limit: int = _MAX_NUMBERS) -> str:
    """Trial numbers as `0-9, 11, 14-15`, cut after `limit` of them with how many more there are."""
    nums = sorted(trial_nums)
    shown, more = nums[:limit], len(nums) - limit
    runs: list[list[int]] = []
    for n in shown:
        if runs and n == runs[-1][-1] + 1:
            runs[-1].append(n)
        else:
            runs.append([n])
    text = (
        ", ".join(str(r[0]) if len(r) == 1 else f"{r[0]}-{r[-1]}" for r in runs)
        or "none"
    )
    return f"{text} and {more} more" if more > 0 else text


def _statuses(job: JobStatus) -> list[tuple[int, TrialStatus]]:
    """Each trial the job has a status for, in trial order."""
    found = ((n, job.get_trial_status(n)) for n in job.trial_nums)
    return [(n, s) for n, s in found if s is not None]


def _stage(status: TrialStatus) -> str:
    """The step a trial reached: the last of generating and solving that started, else pending."""
    if status.solving.started is not None:
        return "solving"
    if status.generating.started is not None:
        return "generating"
    return "pending"


def _no_such_trial(job: JobStatus, trial_num: int) -> str | None:
    """The sentence that says the job has no such trial, or `None` if it has."""
    if trial_num in job.trial_nums:
        return None
    first, last = min(job.trial_nums, default=0), max(job.trial_nums, default=0)
    return (
        f"This job has no trial {trial_num}; its trials are numbered {first} to {last}."
    )


def _find_trial(job: JobStatus, trial_num: int) -> TrialStatus | str:
    """A trial's status, or the sentence that says why there is none."""
    if (missing := _no_such_trial(job, trial_num)) is not None:
        return missing
    status = job.get_trial_status(trial_num)
    if status is None:
        return f"Trial {trial_num} has no status yet: it has not been picked up."
    return status


def _step_text(status: TrialStatus, name: str) -> str:
    """How long one step of a trial took, or that it is in progress or has not started."""
    item = getattr(status, name)
    if item.elapsed is not None:
        return fmt_duration(item.elapsed)
    return "in progress" if item.started is not None else "not started"


def _short(seconds: float) -> str:
    """A time as `45s`, `3m 20s` or `1h 5m`, for the headings of a table, where `fmt_duration` would be long."""
    hours, rest = divmod(round(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {secs}s" if minutes else f"{secs}s"


def _kind(outcome: Outcome) -> str:
    """The word for the trials an outcome picks with a space after it, or nothing for any."""
    label = _OUTCOMES[outcome][1]
    return f"{label} " if label else ""


def _plural(nums: list[int]) -> str:
    return "trials" if len(nums) > 1 else "trial"


def _one_line(text: str, limit: int = _REASON_LENGTH) -> str:
    return " ".join(text.split())[:limit]


def trial_log(job: JobStatus, trial_num: int) -> list[dict[str, Any]] | None:
    """The entries of a trial's log, or `None` if it has no log file or the file cannot be read."""
    path = find_log_file(job.trial_num_to_path(trial_num))
    if path is None:
        return None
    try:
        return parse_log_file(path)
    except OSError:
        return None


def error_line(entries: list[dict[str, Any]]) -> str | None:
    """What a trial's log says went wrong: the last line of its last traceback (`ValueError: ...`), else the first line of its last error entry, else `None`."""
    for item in reversed(entries):
        message = str(item["message"])
        if _TRACEBACK in message:
            return _one_line(
                [line for line in message.splitlines() if line.strip()][-1]
            )
    for item in reversed(entries):
        message = str(item["message"]).strip()
        if message and _LOG_LEVELS.get(str(item["level"]), 0) >= _LOG_LEVELS["ERROR"]:
            return _one_line(message.splitlines()[0])
    return None


def _cause(job: JobStatus, trial_num: int) -> str | None:
    entries = trial_log(job, trial_num)
    return None if entries is None else error_line(entries)


class RunningTrial(BaseModel):
    """A trial that has started working and has not finished."""

    trial_num: int
    step: str
    """`generating`, `solving`, or `starting to solve` between the two."""
    step_seconds: float
    """How long it has been in that step."""
    running_seconds: float
    """How long since it began generating."""


def running_trials(job: JobStatus, at: datetime) -> list[RunningTrial]:
    """The trials running at `at`, the longest running first. One that is only waiting for a worker (claimed, nothing started) is not running."""
    rows: list[RunningTrial] = []
    for trial_num, status in _statuses(job):
        if status.completion != Completion.INCOMPLETE:
            continue
        begun = status.generating.started or status.solving.started
        if begun is None:
            continue
        if status.solving.started is not None:
            step, since = "solving", status.solving.started
        elif status.generating.elapsed is not None and status.generating.started:
            step = "starting to solve"
            since = status.generating.started + timedelta(
                seconds=status.generating.elapsed
            )
        else:
            step, since = "generating", begun
        rows.append(
            RunningTrial(
                trial_num=trial_num,
                step=step,
                step_seconds=max(0.0, (at - since).total_seconds()),
                running_seconds=max(0.0, (at - begun).total_seconds()),
            )
        )
    return sorted(rows, key=lambda r: (-r.running_seconds, r.trial_num))


def _waiting(job: JobStatus, running: list[RunningTrial]) -> int:
    """Trials not finished and not running: the ones nothing has picked up yet, counting any with no status file."""
    return job.n_remaining - len(running)


def describe_summary(job: JobStatus, at: datetime) -> str:
    """The job's progress and timing in a few lines."""
    running = running_trials(job, at)
    lines = [
        f"Job type: {job.job_type}",
        f"Started by: {job.started_by}",
        f"Execution mode: {job.execution_mode}",
        f"Total trials: {job.n_trial}",
        f"Completed: {job.n_done} ({job.n_success} succeeded, {job.n_failed} failed requirements, {job.n_error} errored)",
        f"Running now: {len(running)}",
        f"Waiting to start: {_waiting(job, running)}",
        f"Progress: {job.progress:.1%}",
        f"Progress bar: {job.progress_bar}",
        f"Elapsed: {job.elapsed}",
        f"Average trial duration: {job.average_trial_duration}",
        f"Estimated time remaining: {job.time_remaining_average_success}",
        f"Complete: {job.is_done}",
    ]
    if job.n_done > 0:
        lines += [
            f"Success rate: {job.success_rate:.1%}",
            f"Requirement failure rate: {job.failure_rate:.1%}",
            f"Error rate: {job.error_rate:.1%}",
        ]
    return "\n".join(lines)


def describe_breakdown(job: JobStatus, at: datetime) -> str:
    """The trial numbers in each state, as ranges."""
    running = running_trials(job, at)
    running_nums = {r.trial_num for r in running}
    waiting = [n for n in job.pending_trial_nums if n not in running_nums]
    rows = [
        ("Succeeded", job.success_trial_nums),
        ("Failed requirements", job.failed_trial_nums),
        ("Errored", job.error_trial_nums),
        ("Running", sorted(running_nums)),
        ("Waiting to start", waiting),
    ]
    return "\n".join(
        f"{name} ({len(nums)}): {trial_numbers(nums)}" for name, nums in rows
    )


def describe_running(job: JobStatus, at: datetime) -> str:
    """Which trials are running, what step each is in and for how long."""
    running = running_trials(job, at)
    waiting = _waiting(job, running)
    if not running:
        state = (
            "The job is complete."
            if job.is_done
            else "The job may be between trials, or may have stopped."
        )
        return (
            f"No trial is running right now. {waiting} waiting to start and "
            f"{job.n_done} of {job.n_trial} finished. {state}"
        )
    lines = [
        f"Running now: {len(running)} of {job.n_trial} trials "
        f"({waiting} waiting to start, {job.n_done} finished). Longest running first:"
    ]
    lines += [
        f"  Trial {r.trial_num}: {r.step} for {fmt_duration(r.step_seconds)}, "
        f"running {fmt_duration(r.running_seconds)} in all"
        for r in running[:_MAX_LISTED]
    ]
    if len(running) > _MAX_LISTED:
        lines.append(f"  and {len(running) - _MAX_LISTED} more")
    return "\n".join(lines)


def _finished(job: JobStatus, outcome: Outcome) -> list[tuple[float, int, Completion]]:
    """The time, trial number and ending of each trial that finished as `outcome` says."""
    wanted = _OUTCOMES[outcome][0]
    return [
        (status.td.total_seconds(), trial_num, status.completion)
        for trial_num, status in _statuses(job)
        if status.completion in wanted
    ]


def describe_ranking(
    job: JobStatus, count: int, longest: bool, outcome: Outcome = "completed"
) -> str:
    """The trials that took the longest, or the shortest, each with its time and how it ended."""
    kind = _kind(outcome)
    rows = _finished(job, outcome)
    if not rows:
        return f"No {kind}trial has finished yet, so there are no times to rank."
    rows.sort(key=lambda item: (item[0], item[1]), reverse=longest)
    shown = rows[: max(1, min(count, _MAX_LISTED))]
    lines = [
        f"{'Longest' if longest else 'Shortest'} {len(shown)} of {len(rows)} {kind}trials:"
    ]
    lines += [
        f"  Trial {trial_num}: {fmt_duration(seconds)} ({completion})"
        for seconds, trial_num, completion in shown
    ]
    return "\n".join(lines)


def _quantile(sorted_values: list[float], fraction: float) -> float:
    """The value `fraction` of the way up a sorted list, by nearest rank."""
    return sorted_values[max(0, ceil(fraction * len(sorted_values)) - 1)]


def describe_duration_statistics(job: JobStatus) -> str:
    """How long the completed trials took, as a spread, by ending, by step, and how fast they are finishing."""
    rows = _finished(job, "completed")
    if not rows:
        return "No trial has completed yet, so there are no times to summarize."
    seconds = sorted(r[0] for r in rows)
    lines = [
        f"{len(rows)} completed trials (successes and those that missed a requirement; errored ones are left out):",
        f"  fastest {fmt_duration(seconds[0])}, median {fmt_duration(statistics.median(seconds))}, "
        f"mean {fmt_duration(statistics.fmean(seconds))}, 90th percentile {fmt_duration(_quantile(seconds, 0.9))}, "
        f"slowest {fmt_duration(seconds[-1])}",
    ]
    for completion in (c for c in Completion if c in TIMED_COMPLETIONS):
        times = [s for s, _, c in rows if c == completion]
        if times:
            lines.append(
                f"  {completion}: {len(times)} trials, mean {fmt_duration(statistics.fmean(times))}, "
                f"slowest {fmt_duration(max(times))}"
            )
    totals = job.total_runtimes()
    working = totals["generating"] + totals["solving"]
    if working > 0:
        lines.append(
            f"  time in each step, all trials together: generating {fmt_duration(totals['generating'])} "
            f"({totals['generating'] / working:.0%}), solving {fmt_duration(totals['solving'])} "
            f"({totals['solving'] / working:.0%})"
        )
    elapsed = job.elapsed.total_seconds()
    if elapsed > 0 and job.n_done > 0:
        lines.append(
            f"  finishing {job.n_done / (elapsed / 60):.1f} trials per minute "
            f"over the {fmt_duration(elapsed)} the job has run, with {job.n_proc} processes"
        )
    return "\n".join(lines)


def describe_errored(job: JobStatus) -> str:
    """The trials that errored, grouped by what each trial's log says went wrong, with the step each was in when it broke."""
    errored = [(n, s) for n, s in _statuses(job) if s.completion == Completion.ERROR]
    if not errored:
        return "No trial has errored."
    causes: dict[str, list[tuple[int, str]]] = {}
    no_log: list[int] = []
    no_error: list[int] = []
    for trial_num, status in errored[:_MAX_LOGS_READ]:
        entries = trial_log(job, trial_num)
        if entries is None:
            no_log.append(trial_num)
        elif (cause := error_line(entries)) is None:
            no_error.append(trial_num)
        else:
            causes.setdefault(cause, []).append((trial_num, _stage(status)))
    lines = [f"{len(errored)} trials errored: {trial_numbers(n for n, _ in errored)}."]
    if causes:
        lines.append("What the logs say went wrong, most common first:")
        for cause, items in sorted(causes.items(), key=lambda c: (-len(c[1]), c[0])):
            nums = [n for n, _ in items]
            stages = " or ".join(sorted({stage for _, stage in items}))
            lines.append(
                f"  {cause}: {_plural(nums)} {trial_numbers(nums)}, broke while {stages}"
            )
    if no_error:
        lines.append(
            f"  No error in the log of {_plural(no_error)} {trial_numbers(no_error)}."
        )
    if no_log:
        lines.append(f"  No log file for {_plural(no_log)} {trial_numbers(no_log)}.")
    if len(errored) > _MAX_LOGS_READ:
        lines.append(f"  Only the first {_MAX_LOGS_READ} logs were read.")
    lines.append("get_trial_log gives one trial's whole log, with the traceback.")
    return "\n".join(lines)


def _pick_requirement(names: list[str], name: str) -> str | None:
    """The requirement `name` means: the one with exactly that name (ignoring case), else the only one whose name contains it, else None."""
    wanted = name.strip().lower()
    exact = [n for n in names if n.lower() == wanted]
    partial = [n for n in names if wanted in n.lower()]
    chosen = exact or (partial if len(partial) == 1 else [])
    return chosen[0] if chosen else None


def trials_that_missed(job: JobStatus, requirement: str) -> list[int] | str:
    """
    The numbers of the trials that missed `requirement`, in order, or the sentence that says why there are none to give.

    `requirement` is a requirement's name or part of it. The special words `any` (every trial that missed one or more requirements) and `error` (the trials that crashed, which are not the same set: an errored trial never reached its requirements) are read as words only when no requirement has exactly that name, and before a part of a name is tried, so a requirement called `landing_position_error` cannot swallow `error`.
    """
    names = [r["name"] for r in job.requirement_summary]
    key = requirement.strip().lower()
    exact = [n for n in names if n.lower() == key]
    if not exact and key == "any":
        return sorted(job.failed_trial_nums)
    if not exact and key == "error":
        return sorted(job.error_trial_nums)
    if not names:
        return "No requirement results yet: none were registered, or no trial has finished."
    wanted = exact[0] if exact else _pick_requirement(names, requirement)
    if wanted is None:
        return f"No requirement is named '{requirement}'. The requirements are: {', '.join(names)}."
    return sorted(
        {
            trial_num
            for trial_num, status in _statuses(job)
            for result in status.requirements
            if result.name == wanted and not result.passed
        }
    )


def describe_requirements(job: JobStatus, name: str = "") -> str:
    """How each requirement did across the trials; for one named requirement, which trials missed it and the reasons given."""
    summary = job.requirement_summary
    if not summary:
        return "No requirement results yet: none were registered, or no trial has finished."
    if not name:
        ordered = sorted(summary, key=lambda r: (-r["n_failed"], r["name"]))
        lines = ["Requirements, most failures first:"]
        lines += [
            f"  {r['name']}: failed in {r['n_failed']} of {r['n_trials']} trials (pass rate {r['pass_rate']:.1%})"
            for r in ordered
        ]
        return "\n".join(lines)
    names = [r["name"] for r in summary]
    wanted = _pick_requirement(names, name)
    if wanted is None:
        return f"No requirement is named '{name}'. The requirements are: {', '.join(names)}."
    row = next(r for r in summary if r["name"] == wanted)
    missed: dict[int, str] = {}
    for trial_num, status in _statuses(job):
        for result in status.requirements:
            if result.name == wanted and not result.passed:
                missed[trial_num] = result.message
    lines = [
        f"{wanted}: failed in {row['n_failed']} of {row['n_trials']} trials (pass rate {row['pass_rate']:.1%})."
    ]
    if missed:
        lines.append(f"Failed in trials: {trial_numbers(missed)}.")
        reasons = Counter(" ".join(m.split())[:_REASON_LENGTH] for m in missed.values())
        lines.append("Reasons given:")
        lines += [
            f"  {text or '(no message)'}" + (f" ({n} trials)" if n > 1 else "")
            for text, n in reasons.most_common(_MAX_REASONS)
        ]
    return "\n".join(lines)


def describe_configuration(job: JobStatus) -> str:
    """How the job was started: what it runs, with which arguments, seed and processes."""

    def code(label: str, item: tuple[str, object, int | None]) -> str:
        name, path, line = item
        where = f" ({path}:{line})" if path and line else f" ({path})" if path else ""
        return f"{label}: {name}{where}"

    started = job.start_time.astimezone(UTC).isoformat(timespec="seconds")
    lines = [
        f"Job type: {job.job_type}",
        f"Started by {job.started_by} at {started}",
        f"Execution mode: {job.execution_mode}"
        + (f" (SLURM job {job.slurm_job_id})" if job.slurm_job_id else ""),
        f"Parallel processes: {job.n_proc}",
        f"Seed: {job.seed if job.seed is not None else 'none given'}",
        f"Working folder: {job.workdir}",
        code("Generator", job.generator),
        code("Runtime", job.runtime),
    ]
    if job.job_type == JobType.OPTIMIZE:
        lines.append(code("Objective", job.objective))
    lines.append(f"Arguments (--arg): {job.args_used or 'none'}")
    lines.append(f"Keyword arguments (--kwarg): {job.kwargs_used or 'none'}")
    return "\n".join(lines)


def describe_trial(job: JobStatus, trial_num: int, at: datetime) -> str:
    """One trial: how it ended, the time of each step, and each requirement's result."""
    status = _find_trial(job, trial_num)
    if isinstance(status, str):
        return status
    lines = [
        f"Trial {trial_num}: {status.completion} (step: {status.step})",
        *(f"  {name}: {_step_text(status, name)}" for name in _STEPS),
        f"  total time: {fmt_duration(status.td.total_seconds())}",
    ]
    live = next((r for r in running_trials(job, at) if r.trial_num == trial_num), None)
    if live is not None:
        lines.append(
            f"  running for {fmt_duration(live.running_seconds)} so far, in {live.step} for {fmt_duration(live.step_seconds)}"
        )
    if status.completion == Completion.ERROR:
        cause = _cause(job, trial_num)
        lines.append(
            f"  broke while {_stage(status)}: {cause}"
            if cause
            else f"  broke while {_stage(status)} (no cause found in its log; get_trial_log shows the log)"
        )
    if status.requirements:
        lines.append("  requirements:")
        lines += [
            f"    {'passed' if r.passed else 'FAILED'} {r.name}"
            + (f": {_one_line(r.message)}" if r.message else "")
            for r in status.requirements
        ]
    return "\n".join(lines)


def _names(names: list[str], shown: int = 3) -> str:
    """Names as `a, b, c and 2 more`."""
    text = ", ".join(names[:shown])
    return f"{text} and {len(names) - shown} more" if len(names) > shown else text


def describe_recent(
    job: JobStatus, at: datetime, count: int = 5, outcome: Outcome = "any"
) -> str:
    """The trials that finished most recently, newest first, each with when it finished, how long it took, and for a failure the requirements it missed or for an error what its log says."""
    wanted = _OUTCOMES[outcome][0]
    kind = _kind(outcome)
    rows: list[tuple[datetime, int, TrialStatus]] = []
    for trial_num, status in _statuses(job):
        if status.completion in wanted and (end := status.ended) is not None:
            rows.append((end, trial_num, status))
    if not rows:
        return f"No {kind}trial has finished yet."
    rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
    shown = rows[: max(1, min(count, _MAX_LISTED))]
    lines = [f"Most recent {len(shown)} of {len(rows)} {kind}trials, newest first:"]
    for end, trial_num, status in shown:
        ago = fmt_duration(max(0.0, (at - end).total_seconds()))
        line = (
            f"  Trial {trial_num}: {status.completion}, finished {ago} ago, "
            f"took {fmt_duration(status.td.total_seconds())}"
        )
        if status.completion in FAILED_COMPLETIONS:
            if missed := [r.name for r in status.requirements if not r.passed]:
                line += f", missed {_names(missed)}"
        elif status.completion == Completion.ERROR:
            cause = _cause(job, trial_num)
            line += f", {cause}" if cause else ", no cause found in its log"
        lines.append(line)
    return "\n".join(lines)


def describe_timeline(job: JobStatus, at: datetime) -> str:
    """When trials finished: the job's life so far cut into equal slices, each with how many finished, how they ended and their mean time, so a slowdown, a stall or the point errors began shows."""
    finished: list[tuple[datetime, int, TrialStatus]] = []
    for trial_num, status in _statuses(job):
        if (
            status.completion != Completion.INCOMPLETE
            and (end := status.ended) is not None
        ):
            finished.append((end, trial_num, status))
    if not finished:
        return "No trial has finished yet, so there is no timeline."
    running = bool(running_trials(job, at))
    last = max(end for end, _, _ in finished)
    span = max(((at if running else last) - job.start_time).total_seconds(), 0.0)
    slices = _TIMELINE_SLICES if span > 0 else 1
    width = span / slices if span > 0 else 1.0
    bins: list[list[TrialStatus]] = [[] for _ in range(slices)]
    for end, _, status in finished:
        offset = (end - job.start_time).total_seconds()
        bins[min(slices - 1, max(0, int(offset / width)))].append(status)
    lines = [
        f"{len(finished)} trials finished in the {fmt_duration(span)} the job has run, "
        f"in {slices} slices of {_short(width)}:"
    ]
    for index, items in enumerate(bins):
        label = f"+{_short(index * width)} to +{_short((index + 1) * width)}"
        if not items:
            lines.append(f"  {label}: none finished")
            continue
        parts = [f"{sum(s.completion == Completion.SUCCESS for s in items)} succeeded"]
        if failed := sum(s.completion in FAILED_COMPLETIONS for s in items):
            parts.append(f"{failed} failed requirements")
        if errored := sum(s.completion == Completion.ERROR for s in items):
            parts.append(f"{errored} errored")
        text = f"  {label}: {len(items)} finished ({', '.join(parts)})"
        if times := [
            s.td.total_seconds() for s in items if s.completion in TIMED_COMPLETIONS
        ]:
            text += f", mean {fmt_duration(statistics.fmean(times))}"
        lines.append(text)
    errors = sorted(
        (end, num) for end, num, s in finished if s.completion == Completion.ERROR
    )
    if errors:
        end, num = errors[0]
        offset = (end - job.start_time).total_seconds()
        lines.append(
            f"The first errored trial to finish was trial {num}, at +{_short(offset)}."
        )
    if not running and not job.is_done:
        idle = fmt_duration(max(0.0, (at - last).total_seconds()))
        lines.append(f"Nothing is running, and the last trial finished {idle} ago.")
    return "\n".join(lines)


def _log_block(entry: dict[str, Any]) -> list[str]:
    """One log entry as lines: its time, level and message, a long message (a traceback) cut to its first line and its last few."""
    try:
        stamp = datetime.fromtimestamp(float(entry["timestamp"]) / 1000, UTC)
        clock = stamp.strftime("%H:%M:%S") if entry["timestamp"] else "--:--:--"
    except (OverflowError, OSError, ValueError, TypeError):
        clock = "--:--:--"
    rows = [line[:_LOG_LINE_LENGTH] for line in str(entry["message"]).splitlines()]
    rows = rows or [""]
    if len(rows) > _LOG_ENTRY_LINES:
        keep = _LOG_ENTRY_LINES - 2
        rows = [
            rows[0],
            f"... {len(rows) - 1 - keep} lines left out ...",
            *rows[-keep:],
        ]
    head = f"  {clock} {entry['level']!s:<8} {rows[0]}"
    return [head, *(f"      {row}" for row in rows[1:])]


def describe_trial_log(
    job: JobStatus, trial_num: int, count: int = 20, level: LogLevel = "any"
) -> str:
    """The end of one trial's log, oldest of those shown first: each entry's time, level and message, tracebacks cut to their first and last lines."""
    if (missing := _no_such_trial(job, trial_num)) is not None:
        return missing
    entries = trial_log(job, trial_num)
    if entries is None:
        return f"Trial {trial_num} has no log file."
    wanted = [
        e
        for e in entries
        if _LOG_LEVELS.get(str(e["level"]), 0) >= _MIN_LOG_LEVEL[level]
    ]
    if not wanted:
        if level == "any":
            return f"The log of trial {trial_num} has no entries."
        return (
            f"The log of trial {trial_num} has no {level} entries "
            f"({len(entries)} entries in all)."
        )
    shown = wanted[-max(1, min(count, _MAX_LOG_ENTRIES)) :]
    blocks = [_log_block(e) for e in shown]
    while len(blocks) > 1 and sum(len(r) for b in blocks for r in b) > _MAX_LOG_CHARS:
        blocks.pop(0)
    kind = "" if level == "any" else f"{level}-or-worse "
    lines = [
        f"Last {len(blocks)} of {len(wanted)} {kind}log entries of trial {trial_num}, oldest first:"
    ]
    for block in blocks:
        lines += block
    if len(blocks) < len(shown):
        lines.append("(older entries were left out to keep this short)")
    return "\n".join(lines)


def describe_comparison(job: JobStatus, trial_nums: list[int], at: datetime) -> str:
    """Trials side by side: how each ended, its time in each step, which requirements differ between them, and for an errored one what its log says."""
    nums = list(dict.fromkeys(trial_nums))
    if len(nums) < 2:
        return "Name at least two different trials to compare, such as [3, 7]."
    if len(nums) > _MAX_COMPARED:
        return (
            f"Compare at most {_MAX_COMPARED} trials at once; {len(nums)} were named."
        )
    found = {n: _find_trial(job, n) for n in nums}
    if problems := [f for f in found.values() if isinstance(f, str)]:
        return "\n".join(problems)
    statuses = {n: f for n, f in found.items() if isinstance(f, TrialStatus)}
    live = {r.trial_num: r for r in running_trials(job, at)}

    def each(value: Callable[[int, TrialStatus], str]) -> str:
        return ", ".join(f"trial {n} {value(n, s)}" for n, s in statuses.items())

    def total(n: int, s: TrialStatus) -> str:
        if n in live:
            return f"{fmt_duration(live[n].running_seconds)} so far"
        return fmt_duration(s.td.total_seconds())

    lines = [
        f"Comparing trials {', '.join(str(n) for n in nums)}:",
        "  outcome: "
        + each(
            lambda n, s: f"{s.completion}" + (f" ({live[n].step})" if n in live else "")
        ),
        f"  total time: {each(total)}",
        *(
            f"  {name}: {each(lambda _, s, name=name: _step_text(s, name))}"
            for name in _STEPS
        ),
    ]
    done = {n: s.td.total_seconds() for n, s in statuses.items() if n not in live}
    if len(done) >= 2:
        slow = max(done, key=lambda n: (done[n], n))
        fast = min(done, key=lambda n: (done[n], -n))
        if done[slow] > done[fast] > 0:
            lines.append(
                f"  trial {slow} took {fmt_duration(done[slow] - done[fast])} longer than "
                f"trial {fast} ({done[slow] / done[fast]:.1f}x)"
            )
    names = list(
        dict.fromkeys(r.name for s in statuses.values() for r in s.requirements)
    )
    if not names:
        lines.append("  requirements: none recorded")
    results = {n: {r.name: r for r in s.requirements} for n, s in statuses.items()}
    same: list[str] = []
    differ: list[str] = []
    for name in names:
        per = {n: results[n].get(name) for n in statuses}
        outcomes = {None if r is None else r.passed for r in per.values()}
        if len(outcomes) == 1:
            same.append(f"{name} ({'passed' if outcomes == {True} else 'FAILED'})")
            continue
        parts = []
        for n, r in per.items():
            if r is None:
                parts.append(f"trial {n} not checked")
            else:
                note = (
                    f" ({_one_line(r.message)})" if r.message and not r.passed else ""
                )
                parts.append(f"trial {n} {'passed' if r.passed else 'FAILED'}{note}")
        differ.append(f"    {name}: {', '.join(parts)}")
    if differ:
        lines += ["  requirements that differ:", *differ]
    if same:
        lines.append(
            f"  requirements that are the same in every trial: {', '.join(same)}"
        )
    for n, s in statuses.items():
        if s.completion == Completion.ERROR:
            cause = _cause(job, n)
            lines.append(f"  trial {n} errored: {cause or 'no cause found in its log'}")
    return "\n".join(lines)
