import logging
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field, PrivateAttr

from mujoco_mojo.base import MojoBaseModel

__all__ = []

Step = Literal["generating", "solving", "done"]

logger = logging.getLogger(__name__)


class Completion(StrEnum):
    INCOMPLETE = "incomplete"
    """Neither completed nor failed. Indicates the process is ongoing."""

    COMPLETED = "completed"
    """Completed successfully with no detected exceptions."""

    FAILED = "failed"
    """Completed due to a failure/exceptions."""


class StepStatus(MojoBaseModel):
    started: datetime | None = None
    """Time the step started.

    A `None` value indicates the step has not begun."""

    elapsed: float | None = None
    """Time the step took to run.

    A `None` value indicates the step has no completed. This value is not updated throughout the step's execution (i.e., if the step is in progress, this value will still report `None`)."""

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
        if self.completion in (Completion.COMPLETED, Completion.FAILED):
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
    ) -> StepStatus | Literal[Completion.COMPLETED, Completion.FAILED]:
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
