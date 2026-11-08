"""Tests for `TrialStatus.ended`, when a trial's latest finished step ended, and the job timeline that is built from it."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from mujoco_mojo.utils.statusing import (
    Completion,
    ExecutionMode,
    JobStatus,
    JobType,
    StepStatus,
    TrialStatus,
)

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


class TestEnded:
    def test_it_is_when_the_latest_finished_step_ended(self) -> None:
        status = TrialStatus(
            trial_num=0,
            pending=StepStatus(started=at(0), elapsed=1.0),
            generating=StepStatus(started=at(1), elapsed=4.0),
            solving=StepStatus(started=at(5), elapsed=10.0),
        )

        assert status.ended == at(15)

    def test_a_step_still_running_does_not_count(self) -> None:
        status = TrialStatus(
            trial_num=0,
            pending=StepStatus(started=at(0), elapsed=1.0),
            generating=StepStatus(started=at(1), elapsed=4.0),
            solving=StepStatus(started=at(5)),
        )

        assert status.ended == at(5)

    def test_a_step_with_a_time_but_no_start_does_not_count(self) -> None:
        status = TrialStatus(
            trial_num=0,
            pending=StepStatus(started=at(0), elapsed=1.0),
            solving=StepStatus(elapsed=99.0),
        )

        assert status.ended == at(1)

    def test_it_is_none_when_no_step_has_finished(self) -> None:
        status = TrialStatus(trial_num=0, generating=StepStatus(started=at(0)))

        assert status.ended is None

    def test_it_is_the_latest_even_when_an_earlier_step_ran_longer(self) -> None:
        status = TrialStatus(
            trial_num=0,
            pending=StepStatus(started=at(0), elapsed=50.0),
            generating=StepStatus(started=at(1), elapsed=1.0),
        )

        assert status.ended == at(50)

    def test_it_is_not_written_to_the_status_file(self) -> None:
        status = TrialStatus(
            trial_num=0, pending=StepStatus(started=at(0), elapsed=1.0)
        )

        assert "ended" not in status.model_dump_json()


def bare_job(workdir: Path, n_trial: int) -> JobStatus:
    """A job that starts at `T0` with no trial status loaded."""
    return JobStatus(
        job_type=JobType.MONTE_CARLO,
        execution_mode=ExecutionMode.LOCAL,
        workdir=workdir,
        n_proc=1,
        padding_style="02",
        seed=0,
        start_time=at(0),
        generator=("g", None, None),
        runtime=("r", None, None),
        objective=("o", None, None),
        trial_nums=list(range(n_trial)),
    )


def timeline_job(workdir: Path) -> JobStatus:
    """A job with one trial of each ending, one running and one only claimed, none running a step after its finish."""
    job = bare_job(workdir, 6)
    for trial_num, completion, began, took in (
        (0, Completion.SUCCESS, 0, 10.0),
        (1, Completion.FAILURE, 5, 10.0),
        (2, Completion.ERROR, 10, 10.0),
        (3, Completion.TERMINATED, 15, 5.0),
    ):
        job.update_trial(
            TrialStatus(
                trial_num=trial_num,
                completion=completion,
                solving=StepStatus(started=at(began), elapsed=took),
            ),
            save=False,
        )
    return job


class TestCompletionTimeline:
    def test_the_last_bin_counts_every_finished_trial_by_how_it_ended(
        self, tmp_path: Path
    ) -> None:
        [*_, last] = timeline_job(tmp_path).completion_timeline(5)

        assert (last["n_success"], last["n_failed"], last["n_error"]) == (1, 2, 1)

    def test_a_trial_is_counted_from_when_it_finished(self, tmp_path: Path) -> None:
        """Trial 0 ended at 10 seconds and trial 3 at 20, so the first bin of the 20 second axis, at 0, has neither."""
        bins = timeline_job(tmp_path).completion_timeline(3)

        assert bins[0]["n_success"] + bins[0]["n_failed"] + bins[0]["n_error"] == 0
        assert bins[1]["n_success"] == 1
        assert bins[-1]["n_failed"] == 2

    def test_a_trial_with_no_finished_step_is_left_out(self, tmp_path: Path) -> None:
        job = timeline_job(tmp_path)
        job.update_trial(
            TrialStatus(
                trial_num=4,
                completion=Completion.ERROR,
                generating=StepStatus(started=at(30)),
            ),
            save=False,
        )

        [*_, last] = job.completion_timeline(5)

        assert last["n_error"] == 1

    def test_a_trial_that_has_begun_is_running_and_one_only_claimed_is_pending(
        self, tmp_path: Path
    ) -> None:
        job = timeline_job(tmp_path)
        job.update_trial(
            TrialStatus(trial_num=4, generating=StepStatus(started=at(1))),
            save=False,
        )

        [*_, last] = job.completion_timeline(5)

        assert last["n_running"] == 1
        assert last["n_pending"] == 1

    def test_a_job_with_nothing_finished_or_running_has_no_timeline(
        self, tmp_path: Path
    ) -> None:
        job = timeline_job(tmp_path)
        job.clear_cache()
        assert job.completion_timeline() == []


class TestTheElapsedTimeOfAFinishedJob:
    """A finished job that nobody updates (SLURM workers never touch its file) reads its length off the trials: it ran until the last of them ended."""

    def write(self, job: JobStatus, trial_num: int, began: float, took: float) -> None:
        folder = job.trial_num_to_path(trial_num)
        folder.mkdir(parents=True)
        TrialStatus(
            trial_num=trial_num,
            completion=Completion.SUCCESS,
            solving=StepStatus(started=at(began), elapsed=took),
        ).dump_to_path(folder / "trial_status.json")

    def test_it_is_how_long_until_the_last_trial_ended(self, tmp_path: Path) -> None:
        job = bare_job(tmp_path, 3)
        for trial_num, began, took in ((0, 0, 10.0), (1, 5, 30.0), (2, 8, 4.0)):
            self.write(job, trial_num, began, took)

        job.refresh_from_disk(persist=False)

        assert job.is_done
        assert job.elapsed == timedelta(seconds=35)
