from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import Field

from mujoco_mojo.base import MojoBaseModel

__all__ = []


class Completion(StrEnum):
    INCOMPLETE = "incomplete"
    """Neither completed nor failed. Typically indicates pending."""

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

    pending: StepStatus = Field(default=StepStatus(started=datetime.now(UTC)))
    """Pending step.

    * Information on times when the job sequencer has not yet begun processing this Trial yet.
    * This step must be completed before moving to `generating`.
    * It is the first step in the sequence."""

    generating: StepStatus = Field(default_factory=StepStatus)
    """Generation step.

    * Information on times during which the job sequencer is generating XML (not yet running MuJoCo).
    * This step must be completed before moving to `solving`.
    * It is the second step in the sequence."""

    solving: StepStatus = Field(default_factory=StepStatus)
    """Solving step.

    * Information on times during which the job sequencer is running MuJoCo.
    * This step is the third step in the sequence.
    * Completion of the step is the end of the trial."""

    @property
    def status(self) -> Literal["pending", "generating", "solving", "done"]:
        # early exit for jobs that are no longer being considered
        if self.completion in (Completion.COMPLETED, Completion.FAILED):
            return "done"

        # trial is incomplete, check if it is pending
        if self.pending.is_pending or self.pending.is_in_progress:
            return "pending"

        # trial is no longer pending, check if generating
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
            case "pending":
                return self.pending
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
