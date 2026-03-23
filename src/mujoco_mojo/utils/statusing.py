import getpass
import math
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from importlib.metadata import version
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import Field, PrivateAttr, computed_field

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.meta import REPO_URL
from mujoco_mojo.utils.log import get_logger

__all__ = ["TRIAL_STATUS_FNAME", "Completion", "JobStatus", "StepStatus", "TrialStatus"]

logger = get_logger(__name__)

Step = Literal["pending", "generating", "solving", "done"]
"""Steps a trial can have"""

TRIAL_STATUS_FNAME = "trial_status.json"
"""Filename of trial status files."""

JOB_STATUS_FNAME = "job_status.json"
"""Filename of job status files."""


class JobType(StrEnum):
    MONTE_CARLO = "monte_carlo"
    OPTIMIZE = "optimize"


class ExecutionMode(StrEnum):
    LOCAL = "local"
    SLURM = "slurm"


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
    def td(self) -> timedelta | None:
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

    @property
    def td(self) -> timedelta:
        """The current timedelta for the trial to be completed. Incomplete steps are assumed to have 0 runtime."""
        pending = self.pending.td if self.pending.td is not None else timedelta()
        generating = (
            self.generating.td if self.generating.td is not None else timedelta()
        )
        solving = self.solving.td if self.solving.td is not None else timedelta()
        return pending + generating + solving


class JobStatus(MojoBaseModel):
    """
    Orchestrates the global state of a job.

    This class acts as a cache and aggregator for the individual TrialStatus files on disk. It provides high-level metrics needed for dashboards and job resumption.
    """

    started_by: str = Field(default_factory=getpass.getuser)
    """Who owns the job."""

    job_type: JobType
    """What type of job it is."""

    execution_mode: ExecutionMode
    """What execution mode the job was run with."""

    workdir: Path
    """Job workdir."""

    n_proc: int
    """Number of processors used to define the job."""

    padding_style: str
    """Trial folder number padding style."""

    seed: int | None
    """Seed used to generate the job."""

    start_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    """Initial start time of the job."""

    elapsed: timedelta = Field(default=timedelta(0))
    """Time elapsed running the job."""

    average_trial_duration: timedelta = Field(default=timedelta(0))

    generator: tuple[str, Path | None, int | None]
    """What generator was used. Name of runtime, Path to the runtime, and linenumber."""

    runtime: tuple[str, Path | None, int | None]
    """What runtime was used. Name of runtime, Path to the runtime, and linenumber."""

    gen_args_used: bool
    """Whether or not *args were used for the generator."""

    gen_kwargs_used: bool
    """Whether or not **kwargs were used for the generator."""

    run_args_used: bool
    """Whether or not *args were used for the runtime."""

    run_kwargs_used: bool
    """Whether or not **kwargs were used for the runtime."""

    trial_nums: list[int]
    """The exhaustive list of trial identifiers expected for this job."""

    _cache: dict[int, TrialStatus] = PrivateAttr(default_factory=dict)
    """Internal cache of TrialStatus objects to avoid redundant I/O."""

    @property
    def _registry(self) -> dict[int, Completion]:
        """Provides a mapping of trial_num to its last known completion status."""
        reg = {tn: Completion.INCOMPLETE for tn in self.trial_nums}
        for tn, status in self._cache.items():
            reg[tn] = status.completion

        return reg

    @property
    def n_trial(self) -> int:
        """Number of trials used to define the job."""
        return len(self.trial_nums)

    @property
    def n_remaining(self) -> int:
        return self.n_trial - self.n_done

    def trial_num_to_path(self, trial_num: int) -> Path:
        return self.workdir / "trials" / f"trial_{trial_num:{self.padding_style}}"

    def refresh_from_disk(
        self, n_proc: int = 1, progress_callback: Callable[[float], None] | None = None
    ) -> None:
        """
        Scans the workdir to identify which trials still need execution, but only for runs not already in the cache (i.e., completed).
        """
        max_workers = max(1, n_proc)

        # identify work
        needed_tns = [
            tn
            for tn in self.trial_nums
            if tn not in self._cache
            or self._cache[tn].completion == Completion.INCOMPLETE
        ]

        if not needed_tns:
            if progress_callback:
                return progress_callback(100.0)
            return

        def _load_status(tn: int) -> tuple[int, TrialStatus | None]:
            path = self.trial_num_to_path(tn) / TRIAL_STATUS_FNAME
            if not path.exists():
                return tn, None
            try:
                return tn, TrialStatus.model_validate_json(path.read_text())
            except Exception:
                return tn, None

        # execute with real-time tracking
        total_tasks = len(needed_tns)
        completed_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_tn = {executor.submit(_load_status, tn): tn for tn in needed_tns}

            # as completed yields futures as soon as done
            for future in as_completed(future_to_tn):
                tn, status = future.result()

                # update the cache immediately
                if status is not None:
                    self._cache[tn] = status

                # broadcast status
                completed_count += 1
                if progress_callback:
                    pct = (completed_count / total_tasks) * 100
                    progress_callback(pct)

        # post calculations
        success_durations = [
            s.td.total_seconds()
            for s in self._cache.values()
            if s.completion == Completion.SUCCESS
        ]
        if success_durations:
            avg_sec = sum(success_durations) / len(success_durations)
            self.average_trial_duration = timedelta(seconds=avg_sec)

        if not self.is_done:
            self.elapsed = datetime.now(UTC) - self.start_time
        self.dump_to_path(self.workdir / JOB_STATUS_FNAME)

    def total_runtimes(
        self,
    ) -> dict[Literal["pending", "generating", "solving", "total"], float]:
        totals = {"pending": 0.0, "generating": 0.0, "solving": 0.0}

        for status in self._cache.values():
            for step_name in totals.keys():
                step_obj: StepStatus = getattr(status, step_name)

                if step_obj.elapsed is not None:
                    # step is finished, add the recorded duration
                    totals[step_name] += step_obj.elapsed
                elif step_obj.started is not None:
                    # step is currently running, add time spent so far
                    now = datetime.now(UTC)
                    totals[step_name] += (now - step_obj.started).total_seconds()

        totals["total"] = sum(totals.values())
        return totals  # pyright: ignore[reportReturnType]

    @property
    def pending_trial_nums(self) -> list[int]:
        """Returns trial numbers which are either missing or marked as incomplete."""
        return [
            tn for tn, comp in self._registry.items() if comp == Completion.INCOMPLETE
        ]

    @property
    def time_remaining_wall_clock(self) -> timedelta:
        """
        Calculates the estimated time ramianing based on elapsed wall-clock time.

        For simulations which were not resumed, this property is more accurate than the time_remaining_average_success property.
        """
        elapsed = (datetime.now(UTC) - self.start_time).total_seconds()

        if self.progress <= 0 or self.progress == 1:
            return timedelta(seconds=0)

        total_est_time = elapsed / self.progress
        remaining_seconds = total_est_time - elapsed
        return timedelta(seconds=max(1, int(remaining_seconds)))

    @property
    def time_remaining_average_success(self) -> timedelta:
        """
        Calculates the estimated time ramianing based on the average successful trial completion rate.

        For simulations which were resumed, this property is more accurate than the time_remaining_wall_clock property.
        """
        avg_sec = self.average_trial_duration.total_seconds()
        if self.n_remaining <= 0 or avg_sec == 0:
            return timedelta(0)

        # the number of processors used will change the estimate!
        waves_remaining = math.ceil(self.n_remaining / max(1, self.n_proc))
        total_remaining_seconds = waves_remaining * avg_sec

        return timedelta(seconds=int(total_remaining_seconds))

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
            return datetime.now(UTC) + self.time_remaining_average_success

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
    def success_trial_nums(self) -> list[int]:
        tns = []
        for tn in self._registry.keys():
            if self._registry[tn] == Completion.SUCCESS:
                tns.append(tn)
        return sorted(tns)

    @computed_field
    @property
    def failed_trial_nums(self) -> list[int]:
        tns = []
        for tn in self._registry.keys():
            if self._registry[tn] == Completion.FAILED:
                tns.append(tn)
        return sorted(tns)

    def update_trial(self, status: TrialStatus, save: bool = True):
        """Updates the internal registry and average trial duration and optionally persists the global status."""
        self._cache[status.trial_num] = status

        success_durations = [
            s.td.total_seconds()
            for s in self._cache.values()
            if s.completion == Completion.SUCCESS and s.td is not None
        ]

        if success_durations:
            self.average_trial_duration = timedelta(
                seconds=sum(success_durations) / len(success_durations)
            )

        self.elapsed = datetime.now(UTC) - self.start_time

        if save:
            self.dump_to_path(self.workdir / JOB_STATUS_FNAME)

    @property
    def is_done(self) -> bool:
        return self.n_done == self.n_trial

    @staticmethod
    def _utc_to_local(utc_aware: datetime) -> datetime:
        return utc_aware.astimezone()

    @property
    def local_tzabbr(self) -> str:
        name = self._utc_to_local(datetime.now(UTC)).tzname() or ""

        # If the name is long (Windows style), take the first letter of each word
        if len(name) > 5 and " " in name:
            return "".join([word[0] for word in name.split() if word[0].isupper()])

        return name

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
            "Job Type": str(self.job_type),
            "Execution Mode": str(self.execution_mode),
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

    def _run_time_series(self) -> pd.DataFrame:
        data = {
            "Total Elapsed": str(self.elapsed).split(".")[0],
            "Total Remaining": str(self.time_remaining_average_success).split(".")[0],
            "Start Time": f"{self._utc_to_local(self.start_time).strftime('%Y-%m-%d %H:%M:%S')} {self.local_tzabbr} (*{self.start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC*)",
            "End Time"
            if self.is_done
            else "End Time (est.)": f"{self._utc_to_local(self.end_time).strftime('%Y-%m-%d %H:%M:%S')} {self.local_tzabbr} (*{self.end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC*)",
        }

        if self.is_done:
            # only run this part if the job is done (it is a slow method)
            runtimes = self.total_runtimes()
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
{self._run_time_series().to_markdown(index=False)}

---

{self._failed_runs_md}

---

> **Generated by [`mujoco-mojo`]({REPO_URL})**
""".strip()

        # i like having an ending newline
        report_path.write_text(content + "\n", encoding="utf-8")

        if alert_generation:
            logger.info(f"MuJoCo Mojo report generated at {report_path}")

    def to_monitor_json(self, n_proc: int | None = None) -> dict:
        """Returns a lightweight summary optimized for the Alpine.js dashboard."""
        from mujoco_mojo.runtime.results_manager import ResultsManager

        # We trigger the disk refresh here so the data is fresh
        obj = self.model_validate_json((self.workdir / JOB_STATUS_FNAME).read_text())
        obj.refresh_from_disk(n_proc=obj.n_proc if n_proc is None else n_proc)

        avg_seconds = obj.average_trial_duration.total_seconds()

        # Avoid divide by zero if no trials have finished yet
        throughput = 0
        if avg_seconds > 0:
            throughput = (60.0 / avg_seconds) * obj.n_proc

        success_tns = [
            tn for tn, comp in obj._registry.items() if comp == Completion.SUCCESS
        ]
        last_success_tn = max(success_tns) if success_tns else None

        failed_with_db = []
        failed_tns = obj.failed_trial_nums
        for tn in failed_tns:
            if (obj.trial_num_to_path(tn) / ResultsManager.default_db_name()).exists():
                failed_with_db.append(tn)

        return {
            "progress": obj.progress * 100,
            "n_success": obj.n_success,
            "n_failed": obj.n_failed,
            "n_trial": obj.n_trial,
            "n_done": obj.n_done,
            "n_remaining": obj.n_remaining,
            "failure_rate": obj.failure_rate,
            "throughput": round(throughput, 1),
            "avg_duration": str(obj.average_trial_duration).split(".")[0],
            "time_remaining": str(obj.time_remaining_average_success).split(".")[0],
            "elapsed": str(obj.elapsed).split(".")[0],
            "is_complete": obj.progress >= 1.0,
            "success_tns": obj.success_trial_nums,
            "failure_tns": failed_tns,
            "last_success_tn": last_success_tn,
            "start_time": f"{obj._utc_to_local(obj.start_time).strftime('%Y-%m-%d %H:%M:%S')} {obj.local_tzabbr}",
            "end_time": f"{obj._utc_to_local(obj.end_time).strftime('%Y-%m-%d %H:%M:%S')} {obj.local_tzabbr}",
            "version": f"mujoco-mojo v{version('mujoco-mojo')}",
            "padding_style": obj.padding_style,
            "failure_tns_with_db": failed_with_db,
        }
