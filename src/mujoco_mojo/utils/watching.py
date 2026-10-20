"""Keeps a job's status file and runtime report current while other processes run its trials."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.slurm import slurm_job_active
from mujoco_mojo.utils.statusing import JOB_STATUS_FNAME, JobStatus

if TYPE_CHECKING:
    from rich.console import Console

__all__ = ["WatchOutcome", "watch_job"]

logger = get_logger(__name__)


class WatchOutcome(StrEnum):
    """How `watch_job` ended."""

    DONE = "done"
    """Every trial finished."""

    ENDED_INCOMPLETE = "ended_incomplete"
    """The scheduler no longer has the job, but some trials never reported a result (killed, timed out, or cancelled)."""


def watch_job(
    workdir: Path,
    *,
    interval: float = 10.0,
    n_proc: int = 1,
    console: Console | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> WatchOutcome:
    """
    Keeps a job's `job_status.json` and runtime report current until its trials are done.

    This is for jobs whose trials are run by other processes, such as the array tasks of a SLURM job. Those write only their own trial's status, and nothing else writes the job-level file, so without this it stays exactly as it was at submission (no elapsed time, no trial durations) and the report is never written. Every `interval` seconds this reads the trials' status files, saves the refreshed job status, and rewrites the report when the number of finished trials changed. The job's start time is moved forward to when its first trial began, since the job file is created when the wizard starts, which can be long before the job is submitted or any trial runs; the time a job spends waiting in the queue is therefore not counted. It returns when every trial is done, or, for a job submitted to SLURM by Mojo, when SLURM no longer has the job; either way the final report, with its alerts, is written.

    Args:
        workdir: The job's workdir, which holds `job_status.json`.
        interval: Seconds between passes.
        n_proc: Threads used to read trial status files.
        console: Where to print progress. Nothing is printed without one.
        sleep: How to wait between passes; replaceable so tests need not wait.

    Raises:
        FileNotFoundError: If the workdir has no `job_status.json`.

    """
    status_file = workdir.resolve() / JOB_STATUS_FNAME
    if not status_file.exists():
        msg = f"No job status file found at {status_file}. Start a job first."
        logger.error(msg)
        raise FileNotFoundError(msg)

    job = JobStatus.model_validate_json(status_file.read_text(encoding="utf-8"))
    reported = -1

    def say(text: str) -> None:
        # with a console the line is already on screen, so the log copy is file-only
        logger.info(text, extra={"file_only": True} if console is not None else None)
        if console is not None:
            from rich.markup import escape

            console.print(escape(text))

    say(
        f"Watching {job.n_trial} trials in {job.workdir}"
        + (f" (SLURM job {job.slurm_job_id})" if job.slurm_job_id else "")
        + ". Press Ctrl+C to stop; the job keeps running."
    )

    while True:
        job.refresh_from_disk(n_proc=n_proc, persist=True, start_from_trials=True)

        if job.n_done != reported:
            reported = job.n_done
            job.generate_report()
            say(
                f"[{datetime.now():%H:%M:%S}] {job.n_done}/{job.n_trial} done "
                f"({job.progress:.0%}), {job.n_failed} failed, {job.n_error} errors"
            )

        if job.is_done:
            job.generate_report(alert_generation=True)
            say("All trials finished. Final report written.")
            return WatchOutcome.DONE

        if job.slurm_job_id is not None and slurm_job_active(job.slurm_job_id) is False:
            # something may have been written between the last scan and the queue check
            job.refresh_from_disk(n_proc=n_proc, persist=True, start_from_trials=True)
            job.generate_report(alert_generation=True)
            if job.is_done:
                say("All trials finished. Final report written.")
                return WatchOutcome.DONE
            say(
                f"SLURM no longer has job {job.slurm_job_id}, but "
                f"{job.n_trial - job.n_done} trials never finished (killed, timed out, "
                "or cancelled). Their logs are in the workdir's logs folder."
            )
            return WatchOutcome.ENDED_INCOMPLETE

        sleep(interval)
