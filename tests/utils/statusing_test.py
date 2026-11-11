"""Tests for when a trial ran (`TrialStatus.ended`, `run_started`), the job timeline built from them, and the throughput and time remaining that depend on how many trials run at once."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

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


class TestRunStarted:
    def test_it_is_the_earlier_of_generating_and_solving(self) -> None:
        status = TrialStatus(
            trial_num=0,
            generating=StepStatus(started=at(7)),
            solving=StepStatus(started=at(3)),
        )

        assert status.run_started == at(3)

    def test_a_trial_that_has_only_been_claimed_has_not_begun(self) -> None:
        status = TrialStatus(trial_num=0, pending=StepStatus(started=at(0)))

        assert status.run_started is None

    def test_it_is_kept_after_the_trial_finishes(self) -> None:
        status = TrialStatus(
            trial_num=0,
            completion=Completion.SUCCESS,
            generating=StepStatus(started=at(1), elapsed=2.0),
            solving=StepStatus(started=at(3), elapsed=5.0),
        )

        assert status.run_started == at(1)

    def test_it_is_not_written_to_the_status_file(self) -> None:
        status = TrialStatus(trial_num=0, generating=StepStatus(started=at(1)))

        assert "run_started" not in status.model_dump_json()


def bare_job(
    workdir: Path,
    n_trial: int,
    *,
    mode: ExecutionMode = ExecutionMode.LOCAL,
    n_proc: int = 1,
    start_time: datetime = T0,
) -> JobStatus:
    """A job that starts at `start_time` (`T0` unless given) with no trial status loaded."""
    return JobStatus(
        job_type=JobType.MONTE_CARLO,
        execution_mode=mode,
        workdir=workdir,
        n_proc=n_proc,
        padding_style="02",
        seed=0,
        start_time=start_time,
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

    def test_a_finished_trial_is_running_from_when_it_began_until_it_ended(
        self, tmp_path: Path
    ) -> None:
        """Trials 0 to 3 ran over 0-10, 5-15, 10-20 and 15-20 seconds, so on the 20 second axis the bins at 5, 10, 15 and 20 have 2, 2, 2 and 0 running. Before this they had none: a trial counted as running only while it was still going when the page was drawn."""
        bins = timeline_job(tmp_path).completion_timeline(4)

        assert [b["n_running"] for b in bins] == [2, 2, 2, 0]
        assert [b["n_success"] for b in bins] == [0, 1, 1, 1]

    def test_every_trial_is_in_exactly_one_band_of_every_bin(
        self, tmp_path: Path
    ) -> None:
        job = timeline_job(tmp_path)
        job.update_trial(
            TrialStatus(trial_num=4, generating=StepStatus(started=at(12))),
            save=False,
        )

        for b in job.completion_timeline(7):
            total = (
                b["n_success"]
                + b["n_failed"]
                + b["n_error"]
                + b["n_running"]
                + b["n_pending"]
            )
            assert total == 6

    def test_a_trial_that_errored_before_a_step_ended_is_not_running_afterward(
        self, tmp_path: Path
    ) -> None:
        job = bare_job(tmp_path, 2)
        job.update_trial(
            TrialStatus(
                trial_num=0,
                completion=Completion.ERROR,
                generating=StepStatus(started=at(0), elapsed=4.0),
            ),
            save=False,
        )
        job.update_trial(
            TrialStatus(
                trial_num=1,
                completion=Completion.SUCCESS,
                solving=StepStatus(started=at(0), elapsed=10.0),
            ),
            save=False,
        )

        [first, *_, last] = job.completion_timeline(5)

        assert first["n_running"] == 2
        assert last["n_running"] == 0

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


def done_trial(trial_num: int, began: datetime, took: float) -> TrialStatus:
    """A finished trial that ran for `took` seconds from `began`, split into a one second generating step and the rest solving."""
    return TrialStatus(
        trial_num=trial_num,
        completion=Completion.SUCCESS,
        pending=StepStatus(started=began, elapsed=0.0),
        generating=StepStatus(started=began, elapsed=1.0),
        solving=StepStatus(started=began + timedelta(seconds=1), elapsed=took - 1.0),
    )


def running_trial(trial_num: int, began: datetime) -> TrialStatus:
    return TrialStatus(
        trial_num=trial_num,
        pending=StepStatus(started=began, elapsed=0.0),
        generating=StepStatus(started=began, elapsed=1.0),
        solving=StepStatus(started=began + timedelta(seconds=1)),
    )


def slurm_array_job(workdir: Path, *, n_proc: int) -> JobStatus:
    """A SLURM job observed 150 seconds in, with 20 of its 100 trials running at once for 60 seconds each: two waves have finished and the third is 30 seconds in."""
    now = datetime.now(UTC)
    began = now - timedelta(seconds=150)
    job = bare_job(
        workdir, 100, mode=ExecutionMode.SLURM, n_proc=n_proc, start_time=began
    )
    for trial_num in range(60):
        wave = trial_num // 20
        began_wave = began + timedelta(seconds=60 * wave)
        status = (
            done_trial(trial_num, began_wave, 60.0)
            if wave < 2
            else running_trial(trial_num, began_wave)
        )
        job.update_trial(status, save=False)
    return job


class TestParallelism:
    """How many trials run at once: `n_proc` for a local pool, measured for a job the scheduler runs, whose `n_proc` is just the local default."""

    def test_a_local_job_runs_n_proc_trials_at_once(self, tmp_path: Path) -> None:
        assert bare_job(tmp_path, 10, n_proc=4).parallelism == 4.0

    def test_a_slurm_job_with_no_trial_run_yet_falls_back_to_n_proc(
        self, tmp_path: Path
    ) -> None:
        job = bare_job(tmp_path, 10, mode=ExecutionMode.SLURM, n_proc=3)

        assert job.parallelism == 3.0

    def test_a_slurm_job_is_measured_not_taken_from_n_proc(
        self, tmp_path: Path
    ) -> None:
        assert slurm_array_job(tmp_path / "a", n_proc=1).parallelism == pytest.approx(
            20.0, rel=0.01
        )
        assert slurm_array_job(tmp_path / "b", n_proc=8).parallelism == pytest.approx(
            20.0, rel=0.01
        )

    def test_trials_that_ran_one_after_another_are_one_at_a_time(
        self, tmp_path: Path
    ) -> None:
        now = datetime.now(UTC)
        job = bare_job(
            tmp_path,
            9,
            mode=ExecutionMode.SLURM,
            start_time=now - timedelta(seconds=180),
        )
        for trial_num in range(3):
            began = now - timedelta(seconds=180 - 60 * trial_num)
            job.update_trial(done_trial(trial_num, began, 60.0), save=False)

        assert job.parallelism == pytest.approx(1.0, rel=0.01)

    def test_a_trial_from_before_the_job_began_does_not_count(
        self, tmp_path: Path
    ) -> None:
        """A resumed job's earlier trials ran before `start_time`, and counting them would make the job look wider than it was."""
        now = datetime.now(UTC)
        job = bare_job(
            tmp_path,
            9,
            mode=ExecutionMode.SLURM,
            start_time=now - timedelta(seconds=120),
        )
        job.update_trial(
            done_trial(0, now - timedelta(seconds=1000), 500.0), save=False
        )
        job.update_trial(done_trial(1, now - timedelta(seconds=120), 60.0), save=False)

        assert job.parallelism == pytest.approx(0.5, rel=0.01)

    def test_a_finished_job_keeps_its_value_however_long_ago_it_finished(
        self, tmp_path: Path
    ) -> None:
        """Two trials ran together for the job's whole 60 seconds, a year ago: still 2, not a number that shrinks as time since passes."""
        job = bare_job(tmp_path, 2, mode=ExecutionMode.SLURM)
        job.update_trial(done_trial(0, at(0), 60.0), save=False)
        job.update_trial(done_trial(1, at(0), 60.0), save=False)
        job.elapsed = timedelta(seconds=60)

        assert job.is_done
        assert job.parallelism == pytest.approx(2.0)


class TestThroughputAndTimeRemaining:
    def test_a_slurm_job_reports_the_rate_of_every_task_running(
        self, tmp_path: Path
    ) -> None:
        """20 tasks of 60 seconds each is 20 trials a minute. With `n_proc` of 1 it said 1."""
        job = slurm_array_job(tmp_path, n_proc=1)

        assert job.to_monitor_json()["throughput"] == pytest.approx(20.0, rel=0.01)

    def test_a_slurm_job_estimates_its_remaining_time_from_that_rate(
        self, tmp_path: Path
    ) -> None:
        """60 trials are left (20 running and 40 not started) at 20 a minute, so 3 minutes. With `n_proc` of 1 it said an hour."""
        job = slurm_array_job(tmp_path, n_proc=1)

        remaining = job.time_remaining_average_success

        assert abs(remaining - timedelta(minutes=3)) <= timedelta(seconds=2)

    def test_the_eta_follows_the_same_estimate(self, tmp_path: Path) -> None:
        job = slurm_array_job(tmp_path, n_proc=1)

        eta = job.end_time - datetime.now(UTC)

        assert abs(eta - job.time_remaining_average_success) <= timedelta(seconds=2)

    def test_a_local_job_still_counts_waves_of_n_proc(self, tmp_path: Path) -> None:
        """10 trials left on 4 processes is 3 waves of 60 seconds."""
        job = bare_job(tmp_path, 20, n_proc=4)
        for trial_num in range(10):
            job.update_trial(done_trial(trial_num, at(0), 60.0), save=False)

        assert job.time_remaining_average_success == timedelta(seconds=180)
        assert job.to_monitor_json()["throughput"] == 4.0

    def test_nothing_is_estimated_before_a_trial_has_finished(
        self, tmp_path: Path
    ) -> None:
        job = bare_job(tmp_path, 10, mode=ExecutionMode.SLURM)

        assert job.time_remaining_average_success == timedelta(0)
        assert job.to_monitor_json()["throughput"] == 0
