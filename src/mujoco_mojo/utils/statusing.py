import getpass
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from importlib.metadata import version
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd
from pydantic import Field, PrivateAttr

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.meta import REPO_URL
from mujoco_mojo.utils.logging import get_logger

__all__ = ["STATUS_FNAME", "Completion", "JobStatus", "StepStatus", "TrialStatus"]

logger = get_logger(__name__)

Step = Literal["pending", "generating", "solving", "done"]
"""Steps a trial can have"""

STATUS_FNAME = "status.json"
"""Filename of status files."""


class Completion(StrEnum):
    INCOMPLETE = "incomplete"
    """Neither completed nor failed. Indicates the process is ongoing."""

    SUCCESS = "success"
    """Completed successfully with no detected exceptions."""

    FAILED = "failed"
    """Completed due to a failure/exceptions."""


class StepStatus(MojoBaseModel):
    started: datetime | None = None
    """Time the step started.

    A `None` value indicates the step has not begun."""

    elapsed: float | None = None
    """Time the step took to run.

    A `None` value indicates the step has not completed. This value is not updated throughout the step's execution (i.e., if the step is in progress, this value will still report `None`)."""

    @property
    def timedelta(self) -> timedelta | None:
        """Time delta object provided by `datetime`."""
        if self.elapsed is not None:
            return timedelta(seconds=self.elapsed)
        return None


class TrialStatus(MojoBaseModel):
    """Persistant state of a single trial, saved to disk."""

    trial_num: int
    """Trial number identifier."""

    step: Step = "pending"
    """The current step of the trial."""

    completion: Completion = Completion.INCOMPLETE
    """The overall completion type.

    Included here so that the MojoRunner can set the bulk status of the job with a try-except block."""

    pending: StepStatus = Field(default=StepStatus(started=datetime.now(UTC)))
    """Pending step.

    This is not really a real "step", it is really just an indicator the MuJoCo Mojo is waiting to run this trial."""

    generating: StepStatus = Field(default_factory=StepStatus)
    """Generation step.

    * Information on times during which the job sequencer is generating XML (not yet running MuJoCo).
    * This step must be completed before moving to `solving`.
    * It is the first step in the sequence."""

    solving: StepStatus = Field(default_factory=StepStatus)
    """Solving step.

    * Information on times during which the job sequencer is running MuJoCo.
    * This step is the second step in the sequence.
    * Completion of the step is the end of the trial."""

    _path: Path | None = PrivateAttr(default=None)
    """Where this status file is serialized."""

    @contextmanager
    def record_step(self, step_name: Step):
        # get the current step to update
        self.step = step_name

        match step_name:
            case "pending":
                step = self.pending
            case "generating":
                step = self.generating
            case "solving":
                step = self.solving
            case _:
                logger.warning(f"There is no step associated with {step_name}")
                return

        if self._path is None:
            msg = "Unable to record a step for trial since no serialization path was provided."
            logger.error(msg)
            raise ValueError(msg)
        self._path.parent.mkdir(parents=True, exist_ok=True)

        # steps which are a completion state should not be updated further, they should be done
        assert not isinstance(step, Completion), "Status of step was Completion"

        # configure the step status
        step.started = datetime.now(UTC)
        start_time = time.perf_counter()

        self.dump_to_path(self._path)

        try:
            # run the code inside the `with` block
            yield
        finally:
            # teardown: record duration even if the block failed
            step.elapsed = time.perf_counter() - start_time
            self.dump_to_path(self._path)


class JobStatus(MojoBaseModel):
    """
    Orchestrates the global state of a job.

    This class acts as a cache and aggregator for the individual TrialStatus files on disk. It provides high-level metrics needed for dashboards and job resumption.
    """

    started_by: str = Field(default_factory=getpass.getuser)
    workdir: Path
    n_trial: int
    n_proc: int
    padding_style: str
    start_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    elapsed: timedelta = Field(default_factory=timedelta)
    generator: tuple[str, Path | None, int | None]
    runtime: tuple[str, Path | None, int | None]
    gen_args_used: bool
    gen_kwargs_used: bool
    run_args_used: bool
    run_kwargs_used: bool

    @property
    def trial_nums(self) -> list[int]:
        from mujoco_mojo.utils.runner import MonteCarloConfig

        return MonteCarloConfig._trial_nums(self.n_trial)

    _registry: dict[int, Completion] = PrivateAttr(default_factory=dict)

    def trial_num_to_path(self, trial_num: int) -> Path:
        return self.workdir / "trials" / f"trial_{trial_num:{self.padding_style}}"

    def trial_statuses(self, n_proc: int = 1) -> dict[int, TrialStatus | None]:
        """
        Scans the workdir to serialize trial statuses.

        This is done using:
        1. `glob` to quickly find the trials which at least started.
        2. Parallel pooling to process the globbed files to reduce I/O wait time.
        """
        # discover started trials
        status_files = list((self.workdir / "trials").glob(f"trial_*/{STATUS_FNAME}"))

        # map of trial_num to path
        found_map: dict[int, Path] = {}
        for p in status_files:
            try:
                tn = int(p.parent.name.split("_")[-1])
                found_map[tn] = p
            except (ValueError, IndexError):
                continue

        def _check_file(tn: int) -> TrialStatus | None:
            """Worker function for the TreadPool."""
            # if the status file didnt exist the trial is pending
            if tn not in found_map:
                return None

            try:
                status = TrialStatus.model_validate_json(found_map[tn].read_text())
                if status.completion == Completion.INCOMPLETE:
                    return None
                else:
                    return status
            except Exception:
                # if the JSON was corrupted, assume it needs to be rerun
                return None

        # run the checks in parallel
        max_workers = n_proc if n_proc > 1 else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(_check_file, self.trial_nums))

        return {
            tn: status
            for tn, status in zip(self.trial_nums, results)
            if status is not None
        }

    def refresh_from_disk(self, n_proc: int = 1) -> None:
        """
        Scans the workdir to identify which trials still need execution.

        This is done using:
        1. `glob` to quickly find the trials which at least started.
        2. Parallel pooling to process the globbed files to reduce I/O wait time.
        """
        self._registry = {
            tn: (status.completion if status is not None else Completion.INCOMPLETE)
            for tn, status in self.trial_statuses(n_proc=n_proc).items()
        }

    def total_runtimes(
        self, n_proc: int = 1
    ) -> dict[Literal["pending", "generating", "solving", "total"], float]:
        time_pending = 0
        time_generating = 0
        time_solving = 0
        for tn, status in self.trial_statuses(n_proc=n_proc).items():
            if status is None:
                continue

            if status.pending.elapsed is None:
                continue
            time_pending += status.pending.elapsed

            if status.generating.elapsed is None:
                continue
            time_generating += status.generating.elapsed

            if status.solving.elapsed is None:
                continue
            time_solving += status.solving.elapsed

        return {
            "pending": time_pending,
            "generating": time_generating,
            "solving": time_solving,
            "total": time_pending + time_generating + time_solving,
        }

    @property
    def pending_trial_nums(self) -> list[int]:
        """Returns trial numbers which are either missing or marked as incomplete."""
        return [
            tn for tn, comp in self._registry.items() if comp == Completion.INCOMPLETE
        ]

    @property
    def time_remaining(self) -> timedelta:
        """Calculates the estimated time ramianing based on elapsed wall-clock time."""
        elapsed = (datetime.now(UTC) - self.start_time).total_seconds()

        if self.progress <= 0 or self.progress == 1:
            return timedelta(seconds=0)

        total_est_time = elapsed / self.progress
        remaining_seconds = total_est_time - elapsed
        return timedelta(seconds=max(1, int(remaining_seconds)))

    @property
    def n_done(self) -> int:
        return self.n_success + self.n_failed

    @property
    def progress(self) -> float:
        return min(max(0, self.n_done / self.n_trial), 1)

    @property
    def end_time(self) -> datetime:
        if self.is_done:
            # job is done
            return self.start_time + self.elapsed
        else:
            # job is not done, predict completion time
            return datetime.now(UTC) + self.time_remaining

    @property
    def failure_rate(self) -> float:
        return self.n_failed / self.n_done if self.n_done else 0

    @property
    def success_rate(self) -> float:
        return self.n_success / self.n_done if self.n_done else 0

    @property
    def progress_bar(self) -> str:
        """Visual progress bar for text-based monitoring."""
        width = 40
        p = self.progress
        filled_length = int(width * p)
        return f"|{'█' * filled_length}{'░' * (width - filled_length)}|"

    @property
    def n_success(self) -> int:
        return sum(1 for c in self._registry.values() if c == Completion.SUCCESS)

    @property
    def n_failed(self) -> int:
        return sum(1 for c in self._registry.values() if c == Completion.FAILED)

    @property
    def failed_trial_nums(self) -> list[int]:
        failed_tn = []
        for tn in self._registry.keys():
            if self._registry[tn] == Completion.FAILED:
                failed_tn.append(tn)
        return sorted(failed_tn)

    def update_trial(self, trial_num: int, completion: Completion, save: bool = True):
        """Updates the internal registry and optionally persists the global status."""
        self._registry[trial_num] = completion
        self.elapsed = datetime.now(UTC) - self.start_time
        if save:
            status_path = self.workdir / STATUS_FNAME
            self.dump_to_path(status_path, indent=4)

    @property
    def is_done(self) -> bool:
        return self.n_done == self.n_trial

    @staticmethod
    def _utc_to_local(utc_aware: datetime) -> datetime:
        return utc_aware.astimezone(tz=ZoneInfo("localtime"))

    @property
    def _metrics_series(self) -> pd.DataFrame:
        def _parse_func(name: str, path: Path | None, line: int | None) -> str:
            if path is None or line is None:
                return name

            uri = path.as_uri()
            return f"`{name}` at [`{'/'.join(path.parts[-2:])}:{line}`]({uri})"

        data = {
            "Started By": self.started_by,
            "Workdir": f"`{self.workdir.as_posix()}`",
            "Number of Trials": str(self.n_trial),
            "Number of Processers": str(self.n_proc),
            "Successes": (
                f"{self.n_success} ({self.success_rate:.1%}) "
                f'<progress value="{self.n_success}" max="{self.n_done}" '
                f'style="accent-color: #22C55E;">'
                f"{self.n_success}</progress>"
            ),
            "Failures": (
                f"{self.n_failed} ({self.failure_rate:.1%}) "
                f'<progress value="{self.n_failed}" max="{self.n_done}" '
                f'style="accent-color: #EF4444;">'
                f"{self.n_failed}</progress>"
            ),
            "Generator": _parse_func(*self.generator),
            "Runtime": _parse_func(*self.runtime),
            "Generator Args Used?": "✅" if self.gen_args_used else "❌",
            "Generator Kwargs Used?": "✅" if self.gen_kwargs_used else "❌",
            "Runtime Args Used?": "✅" if self.run_args_used else "❌",
            "Runtime Kwargs Used?": "✅" if self.run_kwargs_used else "❌",
        }
        return pd.DataFrame(data=data.items(), columns=("Metric", "Value"))

    def _run_time_series(self, n_proc: int = 1) -> pd.DataFrame:
        data = {
            "Total Elapsed": str(self.elapsed).split(".")[0],
            "Total Remaining": str(self.time_remaining).split(".")[0],
            "Start Time": f"{self._utc_to_local(self.start_time).strftime('%Y-%m-%d %H:%M:%S %Z%z')} (*{self.start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC*)",
            "End Time"
            if self.is_done
            else "End Time (est.)": f"{self._utc_to_local(self.end_time).strftime('%Y-%m-%d %H:%M:%S %Z%z')} (*{self.end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC*)",
        }

        if self.is_done:
            # only run this part if the job is done (it is a slow method)
            runtimes = self.total_runtimes(n_proc=n_proc)
            data.update(
                {
                    "Elapsed Pending": f"{str(timedelta(seconds=runtimes['pending'])).split('.')[0]} ({runtimes['pending'] / runtimes['total']:.2%})",
                    "Elapsed Generating": f"{str(timedelta(seconds=runtimes['generating'])).split('.')[0]} ({runtimes['generating'] / runtimes['total']:.2%})",
                    "Elapsed Solving": f"{str(timedelta(seconds=runtimes['solving'])).split('.')[0]} ({runtimes['solving'] / runtimes['total']:.2%})",
                }
            )
        return pd.DataFrame(data=data.items(), columns=("Metric", "Value"))

    @property
    def _failed_runs_md(self) -> str:
        if not self.failed_trial_nums:
            return "## Failed Trials:\n✅ **No failures detected.** 🎉"

        # Using a list with bullet points for clean Markdown rendering
        nums = [f"`{tn:{self.padding_style}}`" for tn in sorted(self.failed_trial_nums)]
        return "## ❌ Failed Trials:\n* " + "\n* ".join(nums)

    def generate_report(
        self,
        filename: str = "MOJO_RUNTIME_REPORT.md",
        n_proc: int = 1,
        alert_generation: bool = False,
    ) -> None:
        report_path = self.workdir / filename

        disclaimer = ""
        if not self.is_done:
            disclaimer = (
                "\n### ⚠️ **WARNING: JOB INCOMPLETE**\n```\n"
                f"This report was generated while the job was incomplete.\n"
                f"Metrics and completion times are estimates based on the current "
                f"{self.progress:.1%} progress.\n```\n"
            )

        content = f"""
# Simulation Campaign Report
> *Report generated at {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")} UTC*
{disclaimer}
---

## Metrics:

> Progress: **{self.progress:.1%}** <progress value="{self.progress}" max="1">{self.progress:.1%}</progress>

{self._metrics_series.to_markdown(index=False)}

---

## Run Times:
{self._run_time_series(n_proc=n_proc).to_markdown(index=False)}

---

{self._failed_runs_md}

---

> **Generated by [`mujoco-mojo`]({REPO_URL})**
""".strip()
        report_path.write_text(content + "\n")  # i like having an ending newline

        if alert_generation:
            logger.info(f"MuJoCo Mojo report generated at {report_path}")

    def to_dashboard_json(self, n_proc: int | None = None) -> dict:
        """Returns a lightweight summary optimized for the Alpine.js dashboard."""
        # We trigger the disk refresh here so the data is fresh
        self = self.model_validate_json((self.workdir / STATUS_FNAME).read_text())
        self.refresh_from_disk(n_proc=self.n_proc if n_proc is None else n_proc)

        return {
            "progress": self.progress * 100,
            "n_success": self.n_success,
            "n_failed": self.n_failed,
            "n_trial": self.n_trial,
            "n_done": self.n_done,
            "failure_rate": self.failure_rate,
            "time_remaining": str(self.time_remaining).split(".")[0],
            "elapsed": str(self.elapsed).split(".")[0],
            "is_complete": self.progress >= 1.0,
            "failure_tns": self.failed_trial_nums,
            "end_time": f"{self._utc_to_local(self.end_time).strftime('%Y-%m-%d %H:%M:%S %Z%z')}",
            "version": f"mujoco-mojo v{version('mujoco-mojo')}",
        }
