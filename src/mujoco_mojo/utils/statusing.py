import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import Field, PrivateAttr, computed_field, field_serializer

from mujoco_mojo.base import MojoBaseModel

__all__ = ["STATUS_FNAME", "Completion", "JobStatus", "StepStatus", "TrialStatus"]

logger = logging.getLogger(__name__)

Step = Literal["generating", "solving", "done"]
"""Steps a trial can have"""

STATUS_FNAME = "status.json"
"""Filename of status files."""


class Completion(StrEnum):
    INCOMPLETE = "incomplete"
    """Neither completed nor failed. Indicates the process is ongoing."""

    SUCCESS = "completed"
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

    @property
    def is_pending(self) -> bool:
        return self.started is None

    @property
    def is_in_progress(self) -> bool:
        if isinstance(self.started, datetime) and not isinstance(self.elapsed, float):
            return True
        else:
            return False

    @property
    def is_done(self) -> bool:
        if isinstance(self.started, datetime) and isinstance(self.elapsed, float):
            return True
        else:
            return False


class TrialStatus(MojoBaseModel):
    """Persistant state of a single trial, saved to disk."""

    trial_num: int
    """Trial number identifier."""

    completion: Completion = Completion.INCOMPLETE
    """The overall completion type.

    Included here so that the MojoRunner can set the bulk status of the job with a try-except block."""

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

    @property
    def status(self) -> Step:
        # early exit for jobs that are no longer being considered
        if self.completion in (Completion.SUCCESS, Completion.FAILED):
            return "done"

        # trial is not pending, check if generating
        if self.generating.is_in_progress:
            return "generating"

        # trial is no longer generating, check if solving
        if self.solving.is_in_progress:
            return "solving"

        # trial is not pending, generating, or solving therefore it must be done
        return "done"

    @property
    def step(
        self,
    ) -> StepStatus | Literal[Completion.SUCCESS, Completion.FAILED]:
        match self.status:
            case "generating":
                return self.generating
            case "solving":
                return self.solving
            case "done":
                assert self.completion is not Completion.INCOMPLETE
                return self.completion
            case _:
                raise NotImplementedError(
                    f"A trial status of {self.status} has not yet been implemented"
                )

    @contextmanager
    def record_step(self):
        # get the current step to update
        step = self.step

        # steps which are a completion state should not be updated further, they should be done
        assert not isinstance(step, Completion)

        # configure the step status
        step.started = datetime.now(UTC)
        start_time = time.perf_counter()

        if self._path is None:
            msg = "Unable to record a step for trial since no serialization path was provided."
            logger.error(msg)
            raise ValueError(msg)
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

    workdir: Path
    n_trial: int
    padding_style: str
    start_time: datetime = Field(default_factory=lambda: datetime.now(UTC))

    _trial_nums: list[int] = PrivateAttr(default_factory=list)
    _registry: dict[int, Completion] = PrivateAttr(default_factory=dict)

    def refresh_from_disk(self, n_proc: int = 1) -> None:
        """
        Scans the workdir do identify which trials still need execution.

        This is done using:
        1. `glob` to quickly find the trials which at least started.
        2. Parallel pooling to process the globbed files to reduce I/O wait time.
        """
        # discover started trials
        status_files = list(self.workdir.glob(f"trial_*/{STATUS_FNAME}"))

        # map of trail_num to path
        found_map: dict[int, Path] = {}
        for p in status_files:
            try:
                tn = int(p.parent.name.split("_")[-1])
                found_map[tn] = p
            except (ValueError, IndexError):
                continue

        def _check_file(tn: int) -> tuple[int, Completion]:
            """Worker function for the TreadPool."""
            # if the status file didnt exist the trial is pending
            if tn not in found_map:
                return tn, Completion.INCOMPLETE

            try:
                status = TrialStatus.model_validate_json(found_map[tn].read_text())
                return tn, status.completion
            except Exception:
                # if the JSON was corrupted, assume it needs to be rerun
                return tn, Completion.INCOMPLETE

        # run the checks in parallel
        max_workers = n_proc if n_proc > 1 else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(_check_file, self._trial_nums))

        self._registry = dict(results)

    @property
    def pending_trial_nums(self) -> list[int]:
        """Returns trial numbers which are either missing or marked as incomplete."""
        return [
            tn for tn, comp in self._registry.items() if comp == Completion.INCOMPLETE
        ]

    @computed_field
    @property
    def n_success(self) -> int:
        return sum(1 for c in self._registry.values() if c == Completion.SUCCESS)

    @computed_field
    @property
    def n_failed(self) -> int:
        return sum(1 for c in self._registry.values() if c == Completion.FAILED)

    @property
    def n_done(self) -> int:
        return self.n_success + self.n_failed

    @field_serializer("n_success", "n_failed")
    def serialize_n_done(self, v: int) -> str:
        return str(v)

    @computed_field
    @property
    def progress(self) -> float:
        return min(max(0, self.n_done / self.n_trial), 1)

    @computed_field
    @property
    def time_remaining(self) -> timedelta:
        """Calculates the estimated time ramianing based on elapsed wall-clock time."""
        elapsed = (datetime.now(UTC) - self.start_time).total_seconds()

        if self.progress <= 0:
            return timedelta(seconds=0)

        total_est_time = elapsed / self.progress
        remaining_seconds = total_est_time - elapsed
        return timedelta(seconds=max(1, int(remaining_seconds)))

    @computed_field
    @property
    def elapsed(self) -> timedelta:
        return datetime.now(UTC) - self.start_time

    @computed_field
    @property
    def end_time(self) -> datetime:
        return self.start_time + self.elapsed

    @computed_field
    @property
    def failure_rate(self) -> float:
        return self.n_failed / self.n_done if self.n_done else 0

    @property
    def success_rate(self) -> float:
        return self.n_success / self.n_done if self.n_done else 0

    @computed_field
    @property
    def progress_bar(self) -> str:
        """Visual progress bar for text-based monitoring."""
        width = 40
        p = self.progress
        filled_length = int(width * p)
        return f"[{'█' * filled_length}{'░' * (width - filled_length)}]"

    @computed_field
    @property
    def failed_trial_nums(self) -> list[int]:
        failed_tn = []
        for tn in self._registry.keys():
            if self._registry[tn] == Completion.FAILED:
                failed_tn.append(tn)
        return sorted(failed_tn)

    @field_serializer("progress", "failure_rate")
    def serialize_float_as_perc(self, v: float) -> str:
        return f"{v:.2%}"

    @field_serializer("time_remaining", "elapsed")
    def serialize_timedelta(self, v: timedelta) -> str:
        return str(v)

    def update_trial(self, trial_num: int, completion: Completion, save: bool = True):
        """Updates the internal registry and optionally persists the global status."""
        self._registry[trial_num] = completion

        if save:
            status_path = self.workdir / STATUS_FNAME
            self.dump_to_path(status_path, indent=4)

    @property
    def _metrics_df(self) -> pd.DataFrame:
        data = {
            "Workdir": self.workdir.as_posix(),
            "Number of Trials": str(self.n_trial),
            "Successes": f"{self.n_success} ({self.success_rate:.1%})",
            "Failures": f"{self.n_failed} ({self.failure_rate:.1%})",
            "Progress": f"{self.progress:.2%}",
        }
        return pd.DataFrame(data=data)

    @property
    def _run_time_df(self) -> pd.DataFrame:
        data = {
            "Total Elapsed": str(self.elapsed).split(".")[0],
            "Start Time": f"{self.start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "End Time": f"{self.end_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        }
        return pd.DataFrame(data=data)

    @property
    def _failed_runs_md(self) -> str:
        if not self.failed_trial_nums:
            return "✅ **No failures detected.** 🎉"

        # Using a list with bullet points for clean Markdown rendering
        nums = [f"`{tn:{self.padding_style}}`" for tn in sorted(self.failed_trial_nums)]
        return "### ❌ Failed Trials:\n* " + "\n* ".join(nums)

    def generate_report(self, filename: str = "MOJO_RUNTIME_REPORT.md") -> None:
        report_path = self.workdir / filename

        content = f"""
# Simulation Campaign Report
*Report generated at {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")} UTC*

---

## Metrics:
{self._metrics_df.to_markdown()}

---

## Run Times:
{self._run_time_df.to_markdown()}

---

{self._failed_runs_md}

---

**Generated by mujoco-mojo**
""".strip()
        report_path.write_text(content)
        logger.info(f"MuJoCo Mojo report generated at {report_path}")
