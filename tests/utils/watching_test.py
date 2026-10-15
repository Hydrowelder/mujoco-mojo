import io
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console
from typer.testing import CliRunner

import mujoco_mojo.utils.watching as watching_module
from mujoco_mojo.utils.layers.cli import cli_app
from mujoco_mojo.utils.runner import MojoRunner, MonteCarloConfig
from mujoco_mojo.utils.statusing import JOB_STATUS_FNAME, JobStatus
from mujoco_mojo.utils.watching import WatchOutcome, watch_job

REPORT = "MOJO_RUNTIME_REPORT.md"


def _generate(mojo_model: Any, overrides: Any, *args: Any, **kwargs: Any) -> Any:
    return mojo_model


class SlurmCluster:
    """A submitted job whose array tasks finish one at a time, the way workers on compute nodes do."""

    def __init__(
        self,
        workdir: Path,
        monkeypatch: pytest.MonkeyPatch,
        *,
        n_trial: int = 3,
        job_id: str | None = "4242",
    ) -> None:
        self.workdir = workdir
        self.monkeypatch = monkeypatch
        self.runner = MojoRunner(
            generator=_generate,
            generator_path="sim.generate",
            workdir=workdir,
            config=MonteCarloConfig(n_trial=n_trial, n_proc=1, resume=True),
        )
        job = self.runner.prepare_slurm_job()
        assert job is not None
        job.status.slurm_job_id = job_id
        job.status.dump_to_path(workdir / JOB_STATUS_FNAME)
        self.pending = list(job.to_run)

    def finish_next_trial(self) -> int | None:
        """Runs the next waiting array task exactly as the sbatch script does (`SLURM_ARRAY_TASK_ID` picks the trial)."""
        if not self.pending:
            return None
        trial_num = self.pending.pop(0)
        self.monkeypatch.setenv("SLURM_ARRAY_TASK_ID", str(trial_num))
        try:
            self.runner.run(trial_nums=[trial_num])
        finally:
            self.monkeypatch.delenv("SLURM_ARRAY_TASK_ID")
        return trial_num

    def advance(self, seconds: float) -> None:
        """Stands in for the watcher's sleep: one more array task finishes while it waits."""
        self.finish_next_trial()

    def on_disk(self) -> JobStatus:
        return JobStatus.model_validate_json(
            (self.workdir / JOB_STATUS_FNAME).read_text()
        )


@pytest.fixture
def cluster(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SlurmCluster:
    monkeypatch.setattr(
        "mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", tmp_path / "no-global.toml"
    )
    return SlurmCluster(tmp_path / "work", monkeypatch)


def _console() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    return Console(file=buffer, width=300, force_terminal=False), buffer


def _scheduler(monkeypatch: pytest.MonkeyPatch, answer: bool | None) -> list[str]:
    """Makes the scheduler answer every query the same way, and returns the job ids it was asked about."""
    asked: list[str] = []

    def active(job_id: str) -> bool | None:
        asked.append(job_id)
        return answer

    monkeypatch.setattr(watching_module, "slurm_job_active", active)
    return asked


# --- what the status file looks like without a watcher ---


def test_the_status_file_is_stale_once_workers_finish(cluster: SlurmCluster) -> None:
    """The problem being fixed: only the orchestrator writes the job file, and it stops at submission."""
    while cluster.finish_next_trial() is not None:
        pass

    stale = cluster.on_disk()

    # what was written at submission: no trial durations, and a clock that stopped within moments of the start
    assert stale.average_trial_duration == timedelta(0)
    assert stale.elapsed < timedelta(seconds=1)
    assert not (cluster.workdir / REPORT).exists()


def test_a_finished_jobs_elapsed_is_read_from_its_trials(cluster: SlurmCluster) -> None:
    while cluster.finish_next_trial() is not None:
        pass
    job = cluster.on_disk()

    job.refresh_from_disk(persist=False)

    assert job.is_done
    assert job.elapsed > timedelta(0)
    assert job.average_trial_duration > timedelta(0)
    assert job.end_time == job.start_time + job.elapsed


def test_a_stored_elapsed_is_never_shortened(cluster: SlurmCluster) -> None:
    """A local run tracked its own time, which can be longer than the trials' span (a resumed job)."""
    while cluster.finish_next_trial() is not None:
        pass
    job = cluster.on_disk()
    job.elapsed = timedelta(hours=1)

    job.refresh_from_disk(persist=False)

    assert job.elapsed == timedelta(hours=1)


# --- the watcher ---


def test_the_watcher_keeps_the_status_current_and_stops_when_the_job_is_done(
    cluster: SlurmCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scheduler(monkeypatch, True)
    durations: list[timedelta] = []

    def between_passes(seconds: float) -> None:
        durations.append(cluster.on_disk().average_trial_duration)
        cluster.finish_next_trial()

    console, output = _console()
    outcome = watch_job(
        cluster.workdir, interval=0, console=console, sleep=between_passes
    )

    assert outcome is WatchOutcome.DONE
    # the file on disk moved along with the job, not just in the watcher's memory
    assert durations[0] == timedelta(0)
    assert all(duration > timedelta(0) for duration in durations[1:])
    assert len(durations) == 3
    final = cluster.on_disk()
    assert final.elapsed > timedelta(0)
    assert final.average_trial_duration > timedelta(0)
    assert "3/3 done" in output.getvalue()
    assert "Final report written" in output.getvalue()


def test_the_watcher_writes_the_runtime_report(
    cluster: SlurmCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scheduler(monkeypatch, True)

    watch_job(cluster.workdir, interval=0, sleep=cluster.advance)

    report = (cluster.workdir / REPORT).read_text(encoding="utf-8")
    assert "| Number of Trials" in report
    assert "Successes" in report
    assert "3 (100.0%)" in report


def test_the_watcher_stops_when_slurm_no_longer_has_the_job(
    cluster: SlurmCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A task that was killed or timed out never reports, so waiting for 100% would wait forever."""
    cluster.finish_next_trial()
    cluster.finish_next_trial()
    asked = _scheduler(monkeypatch, False)
    console, output = _console()

    outcome = watch_job(
        cluster.workdir, interval=0, console=console, sleep=lambda seconds: None
    )

    assert outcome is WatchOutcome.ENDED_INCOMPLETE
    assert asked == ["4242"]
    assert "1 trials never finished" in output.getvalue()
    # what finished is still reported, flagged as incomplete
    report = (cluster.workdir / REPORT).read_text(encoding="utf-8")
    assert "JOB INCOMPLETE" in report
    assert "2 (100.0%)" in report
    assert "66.7%" in report
    assert cluster.on_disk().elapsed > timedelta(0)


def test_a_job_that_finished_before_the_watcher_started_needs_no_scheduler(
    cluster: SlurmCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    while cluster.finish_next_trial() is not None:
        pass
    asked = _scheduler(monkeypatch, True)

    outcome = watch_job(cluster.workdir, interval=0, sleep=lambda seconds: None)

    assert outcome is WatchOutcome.DONE
    assert asked == []
    assert cluster.on_disk().elapsed > timedelta(0)
    assert (cluster.workdir / REPORT).exists()


def test_without_a_saved_job_id_only_the_trials_decide(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A job submitted by hand with `sbatch` has no id on file."""
    monkeypatch.setattr(
        "mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", tmp_path / "no-global.toml"
    )
    manual = SlurmCluster(tmp_path / "work", monkeypatch, job_id=None)
    asked = _scheduler(monkeypatch, False)

    outcome = watch_job(manual.workdir, interval=0, sleep=manual.advance)

    assert outcome is WatchOutcome.DONE
    assert asked == []


def test_watching_a_workdir_that_has_no_job_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="job status file"):
        watch_job(tmp_path)


# --- the status file itself ---


def test_status_files_from_before_the_job_id_existed_still_load(
    cluster: SlurmCluster,
) -> None:
    saved = json.loads((cluster.workdir / JOB_STATUS_FNAME).read_text())
    saved.pop("slurm_job_id")

    assert JobStatus.model_validate(saved).slurm_job_id is None


# --- the command ---


def test_job_watch_exits_cleanly_once_everything_is_done(
    cluster: SlurmCluster, monkeypatch: pytest.MonkeyPatch, isolated_logging: None
) -> None:
    while cluster.finish_next_trial() is not None:
        pass
    _scheduler(monkeypatch, True)

    result = CliRunner().invoke(
        cli_app, ["run", "watch-workdir", "--workdir", str(cluster.workdir)]
    )

    assert result.exit_code == 0, result.output
    assert "All trials finished" in result.output
    assert cluster.on_disk().elapsed > timedelta(0)


def test_job_watch_exits_with_an_error_when_the_job_ended_incomplete(
    cluster: SlurmCluster, monkeypatch: pytest.MonkeyPatch, isolated_logging: None
) -> None:
    cluster.finish_next_trial()
    _scheduler(monkeypatch, False)

    result = CliRunner().invoke(
        cli_app, ["run", "watch-workdir", "--workdir", str(cluster.workdir)]
    )

    assert result.exit_code == 1
    assert "never finished" in result.output


def test_job_watch_explains_a_workdir_with_no_job(
    tmp_path: Path, isolated_logging: None
) -> None:
    result = CliRunner().invoke(
        cli_app, ["run", "watch-workdir", "--workdir", str(tmp_path)]
    )

    assert result.exit_code == 1
    assert "No job status file found" in result.output
