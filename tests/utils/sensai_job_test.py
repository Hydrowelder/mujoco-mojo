"""Tests for what SensAI's job agent can say about a job: `sensai/job_report.py`, one function per question, run on real `JobStatus` objects with a clock the test sets."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from mujoco_mojo.utils.layers.dojo.sensai import job_report
from mujoco_mojo.utils.layers.dojo.sensai.job_report import (
    describe_breakdown,
    describe_comparison,
    describe_configuration,
    describe_duration_statistics,
    describe_errored,
    describe_ranking,
    describe_recent,
    describe_requirements,
    describe_running,
    describe_summary,
    describe_timeline,
    describe_trial,
    describe_trial_log,
    error_line,
    fmt_duration,
    running_trials,
    trial_log,
)
from mujoco_mojo.utils.statusing import (
    Completion,
    ExecutionMode,
    JobStatus,
    JobType,
    RequirementResult,
    StepStatus,
    TrialStatus,
)

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
"""When the trials in these tests begin, and a little after it is the test's `now`."""


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def new_job(workdir: Path, n_trial: int) -> JobStatus:
    return JobStatus(
        job_type=JobType.MONTE_CARLO,
        execution_mode=ExecutionMode.LOCAL,
        workdir=workdir,
        n_proc=2,
        padding_style="02",
        seed=7,
        start_time=T0,
        generator=("generate", None, None),
        runtime=("runtime", None, None),
        objective=("objective", None, None),
        trial_nums=list(range(n_trial)),
    )


def finish(
    job: JobStatus,
    trial_num: int,
    seconds: float,
    completion: Completion = Completion.SUCCESS,
    requirements: list[RequirementResult] | None = None,
    generating: float = 0.0,
) -> None:
    """A trial that finished, whose solving took `seconds` (and generating `generating`)."""
    job.update_trial(
        TrialStatus(
            trial_num=trial_num,
            completion=completion,
            step="solving",
            pending=StepStatus(started=T0, elapsed=0.0),
            generating=StepStatus(started=T0, elapsed=generating),
            solving=StepStatus(started=T0, elapsed=seconds),
            requirements=requirements or [],
        ),
        save=False,
    )


def begin(
    job: JobStatus,
    trial_num: int,
    generating_started: float | None = None,
    generating_took: float | None = None,
    solving_started: float | None = None,
) -> None:
    """A trial that has not finished: with nothing started it is only waiting, else it is running in whichever step has started last."""
    job.update_trial(
        TrialStatus(
            trial_num=trial_num,
            step="solving" if solving_started is not None else "generating",
            pending=StepStatus(
                started=T0, elapsed=None if generating_started is None else 0.0
            ),
            generating=StepStatus(
                started=None if generating_started is None else at(generating_started),
                elapsed=generating_took,
            ),
            solving=StepStatus(
                started=None if solving_started is None else at(solving_started)
            ),
        ),
        save=False,
    )


def req(name: str, passed: bool, message: str = "") -> RequirementResult:
    return RequirementResult(name=name, passed=passed, message=message)


def log_line(
    message: str, level: str = "INFO", seconds: float | None = 5.0
) -> dict[str, Any]:
    """One entry of a trial's log, `seconds` after the start (`None` leaves the time out)."""
    entry: dict[str, Any] = {"level": level, "message": message}
    if seconds is not None:
        entry["timestamp"] = at(seconds).timestamp() * 1000
    return entry


def failure_log(trial_num: int, kind: str, message: str) -> list[dict[str, Any]]:
    """What the runner writes when a trial raises: the message, then the traceback ending in the exception."""
    return [
        log_line("starting"),
        log_line(
            f"Trial {trial_num} failed with the following error: {message}\n"
            "Traceback (most recent call last):\n"
            '  File "runner.py", line 600, in run\n'
            "    solve()\n"
            f"{kind}: {message}",
            "ERROR",
            seconds=9,
        ),
    ]


def write_log(job: JobStatus, trial_num: int, entries: list[dict[str, Any]]) -> None:
    """The trial's `mojo.log`, one JSON entry a line as the runner writes it."""
    folder = job.trial_num_to_path(trial_num)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "mojo.log").write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries)
    )


class TestFormattingATime:
    @pytest.mark.parametrize(
        ("seconds", "text"),
        [
            (0.0, "0.00s"),
            (9.5, "9.50s"),
            (59.994, "59.99s"),
            (60.0, "60.00s (1m 0s)"),
            (75.3, "75.30s (1m 15s)"),
            (3600.0, "3600.00s (1h 0m 0s)"),
            (3725.4, "3725.40s (1h 2m 5s)"),
        ],
    )
    def test_a_minute_or_more_also_says_minutes_and_hours(
        self, seconds: float, text: str
    ) -> None:
        assert fmt_duration(seconds) == text


class TestTrialNumbers:
    @pytest.mark.parametrize(
        ("nums", "text"),
        [
            ([], "none"),
            ([4], "4"),
            ([0, 1, 2, 3], "0-3"),
            ([5, 0, 1, 9, 10, 11, 3], "0-1, 3, 5, 9-11"),
        ],
    )
    def test_runs_become_ranges_in_order(self, nums: list[int], text: str) -> None:
        assert job_report.trial_numbers(nums) == text

    def test_a_long_list_is_cut_and_says_how_many_more(self) -> None:
        assert (
            job_report.trial_numbers(range(0, 200, 2), limit=3) == "0, 2, 4 and 97 more"
        )

    def test_a_dict_of_trials_gives_its_keys(self) -> None:
        assert job_report.trial_numbers({3: "a", 1: "b"}) == "1, 3"


class TestWhichTrialsAreRunning:
    """A running trial has started a step and has not finished; one only waiting for a worker has started nothing."""

    def test_a_trial_in_its_first_step_is_generating(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)
        begin(job, 0, generating_started=10)

        [row] = running_trials(job, at(25))

        assert (row.trial_num, row.step) == (0, "generating")
        assert row.step_seconds == 15
        assert row.running_seconds == 15

    def test_a_trial_in_its_second_step_is_solving_for_as_long_as_that_step(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 3)
        begin(job, 0, generating_started=0, generating_took=4, solving_started=4)

        [row] = running_trials(job, at(10))

        assert row.step == "solving"
        assert row.step_seconds == 6
        assert row.running_seconds == 10

    def test_a_trial_between_its_steps_is_about_to_solve(self, tmp_path: Path) -> None:
        """Generating is done, solving has not begun: it is not waiting, and its time since generating ended is the time in between."""
        job = new_job(tmp_path, 3)
        begin(job, 0, generating_started=0, generating_took=4)

        [row] = running_trials(job, at(10))

        assert row.step == "starting to solve"
        assert row.step_seconds == 6
        assert row.running_seconds == 10

    def test_a_trial_nothing_has_picked_up_is_not_running(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)
        begin(job, 0)

        assert running_trials(job, at(10)) == []

    def test_a_trial_that_finished_is_not_running(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)
        finish(job, 0, 5.0)

        assert running_trials(job, at(10)) == []

    def test_the_longest_running_comes_first_and_ties_go_by_number(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 4)
        begin(job, 0, generating_started=20)
        begin(job, 1, generating_started=5)
        begin(job, 2, generating_started=20)
        begin(job, 3, generating_started=12)

        rows = running_trials(job, at(30))

        assert [r.trial_num for r in rows] == [1, 3, 0, 2]

    def test_a_clock_before_the_start_never_gives_a_negative_time(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 1)
        begin(job, 0, generating_started=50)

        [row] = running_trials(job, at(10))

        assert row.step_seconds == 0
        assert row.running_seconds == 0


class TestRunning:
    def test_it_lists_each_running_trial_with_its_step_and_times(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 6)
        finish(job, 0, 3.0)
        begin(job, 1, generating_started=0, generating_took=4, solving_started=4)
        begin(job, 2, generating_started=100)

        text = describe_running(job, at(130))

        assert text.splitlines() == [
            "Running now: 2 of 6 trials (3 waiting to start, 1 finished). Longest running first:",
            "  Trial 1: solving for 126.00s (2m 6s), running 130.00s (2m 10s) in all",
            "  Trial 2: generating for 30.00s, running 30.00s in all",
        ]

    def test_waiting_trials_do_not_count_as_running(self, tmp_path: Path) -> None:
        """`n_remaining` includes the running ones, so the waiting count is that less those running."""
        job = new_job(tmp_path, 5)
        begin(job, 0, generating_started=0)
        begin(job, 1)

        assert "(4 waiting to start, 0 finished)" in describe_running(job, at(5))

    def test_a_long_list_is_cut_with_how_many_more(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 30)
        for n in range(25):
            begin(job, n, generating_started=n)

        text = describe_running(job, at(100)).splitlines()

        assert len(text) == 1 + 20 + 1
        assert text[-1] == "  and 5 more"

    def test_when_nothing_is_running_it_says_where_the_job_stands(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 3)
        finish(job, 0, 2.0)

        text = describe_running(job, at(10))

        assert text.startswith("No trial is running right now. 2 waiting to start")
        assert "1 of 3 finished" in text
        assert "between trials, or may have stopped" in text

    def test_when_the_job_is_complete_it_says_so(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 2.0)
        finish(job, 1, 2.0)

        text = describe_running(job, at(10))

        assert "0 waiting to start and 2 of 2 finished" in text
        assert "The job is complete." in text


class TestSummary:
    def test_it_counts_running_and_waiting_apart(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 10)
        finish(job, 0, 2.0)
        finish(job, 1, 3.0, Completion.FAILURE)
        finish(job, 2, 1.0, Completion.ERROR)
        begin(job, 3, generating_started=0)

        text = describe_summary(job, at(5)).splitlines()

        assert "Total trials: 10" in text
        assert "Completed: 3 (1 succeeded, 1 failed requirements, 1 errored)" in text
        assert "Running now: 1" in text
        assert "Waiting to start: 6" in text
        assert "Progress: 30.0%" in text
        assert "Complete: False" in text

    def test_the_rates_are_given_once_a_trial_has_finished(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 4)
        finish(job, 0, 2.0)
        finish(job, 1, 3.0, Completion.FAILURE)

        text = describe_summary(job, at(5))

        assert "Success rate: 50.0%" in text
        assert "Requirement failure rate: 50.0%" in text
        assert "Error rate: 0.0%" in text

    def test_it_has_no_rates_before_anything_finished(self, tmp_path: Path) -> None:
        text = describe_summary(new_job(tmp_path, 4), at(5))

        assert "rate" not in text
        assert "Completed: 0 (0 succeeded, 0 failed requirements, 0 errored)" in text


class TestBreakdown:
    def test_each_state_lists_its_trial_numbers(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 9)
        for n in (0, 1, 2, 4):
            finish(job, n, 1.0)
        finish(job, 3, 1.0, Completion.FAILURE)
        finish(job, 5, 1.0, Completion.ERROR)
        begin(job, 6, generating_started=0)

        assert describe_breakdown(job, at(5)).splitlines() == [
            "Succeeded (4): 0-2, 4",
            "Failed requirements (1): 3",
            "Errored (1): 5",
            "Running (1): 6",
            "Waiting to start (2): 7-8",
        ]

    def test_a_running_trial_is_not_also_waiting(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)
        begin(job, 0, generating_started=0)

        lines = describe_breakdown(job, at(5)).splitlines()

        assert "Running (1): 0" in lines
        assert "Waiting to start (2): 1-2" in lines


class TestRanking:
    @pytest.fixture
    def job(self, tmp_path: Path) -> JobStatus:
        job = new_job(tmp_path, 7)
        finish(job, 0, 4.0)
        finish(job, 1, 9.5, Completion.ERROR)
        finish(job, 2, 1.25, Completion.FAILURE)
        finish(job, 3, 7.0)
        finish(job, 4, 99.0, Completion.TERMINATED)
        begin(job, 5, generating_started=0)
        return job

    def test_the_longest_come_first_with_their_time_and_ending(
        self, job: JobStatus
    ) -> None:
        text = describe_ranking(job, 3, True)

        assert text.splitlines() == [
            "Longest 3 of 4 completed trials:",
            "  Trial 4: 99.00s (1m 39s) (terminated)",
            "  Trial 3: 7.00s (success)",
            "  Trial 0: 4.00s (success)",
        ]

    def test_the_shortest_can_be_asked_for_instead(self, job: JobStatus) -> None:
        assert describe_ranking(job, 1, False).splitlines() == [
            "Shortest 1 of 4 completed trials:",
            "  Trial 2: 1.25s (failure)",
        ]

    def test_an_errored_trial_is_not_in_the_default_ranking(
        self, job: JobStatus
    ) -> None:
        """The job's own average leaves errored trials out, because a crash's time says nothing about how long a run takes, so a ranking that put one first would name the wrong slowest trial."""
        assert "Trial 1" not in describe_ranking(job, 20, True)

    def test_a_trial_still_running_is_never_ranked(self, tmp_path: Path) -> None:
        """A running trial has some time recorded but has not taken that long yet."""
        job = new_job(tmp_path, 2)
        finish(job, 0, 3.0)
        job.update_trial(
            TrialStatus(
                trial_num=1,
                solving=StepStatus(started=T0, elapsed=99.0),
            ),
            save=False,
        )

        assert describe_ranking(job, 5, True).splitlines() == [
            "Longest 1 of 1 completed trials:",
            "  Trial 0: 3.00s (success)",
        ]

    @pytest.mark.parametrize(
        ("outcome", "label", "trials"),
        [
            ("success", "successful", [3, 0]),
            ("failure", "requirement-failing", [4, 2]),
            ("error", "errored", [1]),
        ],
    )
    def test_the_outcome_picks_which_trials_are_ranked(
        self,
        job: JobStatus,
        outcome: job_report.Outcome,
        label: str,
        trials: list[int],
    ) -> None:
        text = describe_ranking(job, 20, True, outcome).splitlines()

        assert text[0] == f"Longest {len(trials)} of {len(trials)} {label} trials:"
        assert [line.split(":")[0].strip() for line in text[1:]] == [
            f"Trial {n}" for n in trials
        ]

    def test_an_errored_trial_is_ranked_when_it_is_asked_for(
        self, job: JobStatus
    ) -> None:
        assert describe_ranking(job, 5, True, "error").splitlines()[1] == (
            "  Trial 1: 9.50s (error)"
        )

    def test_ties_are_listed_by_trial_number_either_way(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 2.0)
        finish(job, 1, 2.0)

        assert [
            line.split(":")[0]
            for line in describe_ranking(job, 2, False).splitlines()[1:]
        ] == [
            "  Trial 0",
            "  Trial 1",
        ]
        assert [
            line.split(":")[0]
            for line in describe_ranking(job, 2, True).splitlines()[1:]
        ] == [
            "  Trial 1",
            "  Trial 0",
        ]

    def test_a_long_list_is_cut_at_the_limit_and_a_short_one_at_one(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 30)
        for n in range(30):
            finish(job, n, float(n))

        assert len(describe_ranking(job, 100, True).splitlines()) == 1 + 20
        assert len(describe_ranking(job, 0, True).splitlines()) == 1 + 1

    @pytest.mark.parametrize(
        ("outcome", "label"),
        [
            ("completed", "completed"),
            ("success", "successful"),
            ("failure", "requirement-failing"),
            ("error", "errored"),
        ],
    )
    def test_it_says_so_when_none_of_that_kind_has_finished(
        self, tmp_path: Path, outcome: job_report.Outcome, label: str
    ) -> None:
        job = new_job(tmp_path, 3)
        begin(job, 0, generating_started=0)

        assert describe_ranking(job, 5, True, outcome) == (
            f"No {label} trial has finished yet, so there are no times to rank."
        )


class TestDurationStatistics:
    @pytest.fixture
    def job(self, tmp_path: Path) -> JobStatus:
        job = new_job(tmp_path, 8)
        for n, seconds in enumerate([2.0, 4.0, 6.0, 8.0]):
            finish(job, n, seconds, generating=1.0)
        finish(job, 4, 10.0, Completion.FAILURE, generating=1.0)
        finish(job, 5, 500.0, Completion.ERROR)
        job.elapsed = timedelta(seconds=120)
        return job

    def test_the_spread_covers_completed_trials_and_leaves_errored_ones_out(
        self, job: JobStatus
    ) -> None:
        lines = describe_duration_statistics(job).splitlines()

        assert lines[0].startswith("5 completed trials")
        assert lines[1] == (
            "  fastest 3.00s, median 7.00s, mean 7.00s, 90th percentile 11.00s, slowest 11.00s"
        )

    def test_it_gives_each_ending_its_own_mean_and_slowest(
        self, job: JobStatus
    ) -> None:
        text = describe_duration_statistics(job)

        assert "  success: 4 trials, mean 6.00s, slowest 9.00s" in text
        assert "  failure: 1 trials, mean 11.00s, slowest 11.00s" in text
        assert "terminated" not in text

    def test_it_says_where_the_time_goes_by_step(self, job: JobStatus) -> None:
        text = describe_duration_statistics(job)

        assert (
            "time in each step, all trials together: generating 5.00s (1%), solving 530.00s (8m 50s) (99%)"
            in text
        )

    def test_it_gives_how_fast_trials_are_finishing(self, job: JobStatus) -> None:
        assert (
            "finishing 3.0 trials per minute over the 120.00s (2m 0s) the job has run, with 2 processes"
            in describe_duration_statistics(job)
        )

    def test_the_throughput_is_left_out_when_no_time_has_passed(
        self, job: JobStatus
    ) -> None:
        job.elapsed = timedelta(0)

        assert "per minute" not in describe_duration_statistics(job)

    def test_a_single_trial_is_its_own_spread(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)
        finish(job, 0, 2.5)

        assert (
            "fastest 2.50s, median 2.50s, mean 2.50s, 90th percentile 2.50s, slowest 2.50s"
            in describe_duration_statistics(job)
        )

    def test_it_says_so_when_nothing_has_completed(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)
        finish(job, 0, 4.0, Completion.ERROR)

        assert describe_duration_statistics(job) == (
            "No trial has completed yet, so there are no times to summarize."
        )

    @pytest.mark.parametrize(
        ("fraction", "expected"),
        [(0.0, 1.0), (0.5, 5.0), (0.9, 9.0), (0.95, 10.0), (1.0, 10.0)],
    )
    def test_a_quantile_is_the_nearest_rank(
        self, fraction: float, expected: float
    ) -> None:
        values = [float(n) for n in range(1, 11)]

        assert job_report._quantile(values, fraction) == expected


class TestErrorLine:
    """What a trial's log says went wrong, from the traceback the runner logs when a trial raises."""

    def test_it_is_the_last_line_of_the_last_traceback(self) -> None:
        assert error_line(failure_log(1, "ValueError", "bad mass")) == (
            "ValueError: bad mass"
        )

    def test_the_last_traceback_wins_over_an_earlier_one(self) -> None:
        entries = [
            *failure_log(1, "KeyError", "first"),
            *failure_log(1, "ValueError", "second"),
        ]

        assert error_line(entries) == "ValueError: second"

    def test_a_chained_exception_gives_the_last_one_raised(self) -> None:
        message = (
            "Trial 1 failed\nTraceback (most recent call last):\n  File x\nKeyError: 'a'\n\n"
            "During handling of the above exception, another exception occurred:\n\n"
            "Traceback (most recent call last):\n  File y\nRuntimeError: wrapped"
        )

        assert error_line([log_line(message, "ERROR")]) == "RuntimeError: wrapped"

    def test_without_a_traceback_it_is_the_first_line_of_the_last_error_entry(
        self,
    ) -> None:
        entries = [
            log_line("old problem", "ERROR"),
            log_line("fine"),
            log_line("\nsolver diverged\nmore detail", "ERROR"),
            log_line("shutting down", "WARNING"),
        ]

        assert error_line(entries) == "solver diverged"

    def test_a_log_without_an_error_gives_none(self) -> None:
        assert error_line([log_line("fine"), log_line("hmm", "WARNING")]) is None

    def test_an_entry_with_an_unknown_level_is_not_an_error(self) -> None:
        assert error_line([log_line("loose text", "Invalid Level")]) is None

    def test_an_empty_log_gives_none(self) -> None:
        assert error_line([]) is None

    def test_a_long_line_is_cut(self) -> None:
        line = error_line(failure_log(1, "ValueError", "x" * 500))

        assert line is not None
        assert len(line) == 160


class TestReadingATrialLog:
    def test_the_entries_are_read_from_the_trials_own_folder(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 3)
        write_log(job, 1, [log_line("hello")])

        entries = trial_log(job, 1)

        assert entries is not None
        assert [e["message"] for e in entries] == ["hello"]

    def test_a_trial_with_no_log_gives_none(self, tmp_path: Path) -> None:
        assert trial_log(new_job(tmp_path, 3), 2) is None

    def test_a_log_that_cannot_be_read_gives_none(self, tmp_path: Path) -> None:
        """A folder named like a log is found as one and fails to open."""
        job = new_job(tmp_path, 3)
        (job.trial_num_to_path(0) / "broken.log").mkdir(parents=True)

        assert trial_log(job, 0) is None


class TestErrored:
    def test_trials_are_grouped_by_what_their_logs_say_with_the_step_each_broke_in(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 8)
        for n, stage in ((1, "solving"), (3, "generating"), (4, "solving")):
            job.update_trial(
                TrialStatus(
                    trial_num=n,
                    completion=Completion.ERROR,
                    generating=StepStatus(started=T0),
                    solving=StepStatus(started=T0 if stage == "solving" else None),
                ),
                save=False,
            )
            write_log(job, n, failure_log(n, "ValueError", "bad mass"))
        job.update_trial(
            TrialStatus(
                trial_num=5,
                completion=Completion.ERROR,
                generating=StepStatus(started=T0),
            ),
            save=False,
        )
        write_log(job, 5, failure_log(5, "RuntimeError", "diverged"))

        assert describe_errored(job).splitlines() == [
            "4 trials errored: 1, 3-5.",
            "What the logs say went wrong, most common first:",
            "  ValueError: bad mass: trials 1, 3-4, broke while generating or solving",
            "  RuntimeError: diverged: trial 5, broke while generating",
            "get_trial_log gives one trial's whole log, with the traceback.",
        ]

    def test_a_trial_with_no_log_or_no_error_in_it_is_listed_apart(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 6)
        for n in (0, 1, 2):
            finish(job, n, 1.0, Completion.ERROR)
        write_log(job, 1, [log_line("fine")])
        write_log(job, 2, failure_log(2, "OSError", "disk full"))

        lines = describe_errored(job).splitlines()

        assert "  OSError: disk full: trial 2, broke while solving" in lines
        assert "  No error in the log of trial 1." in lines
        assert "  No log file for trial 0." in lines

    def test_a_trial_that_did_not_error_is_not_read(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)
        finish(job, 0, 1.0, Completion.ERROR)
        finish(job, 1, 1.0, Completion.FAILURE)
        write_log(job, 0, failure_log(0, "ValueError", "boom"))
        write_log(job, 1, failure_log(1, "KeyError", "not me"))

        text = describe_errored(job)

        assert "boom" in text
        assert "not me" not in text

    def test_only_the_first_logs_are_read_and_it_says_so(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 60)
        for n in range(55):
            finish(job, n, 1.0, Completion.ERROR)
            write_log(job, n, failure_log(n, "ValueError", "same"))

        text = describe_errored(job)

        assert text.startswith("55 trials errored: 0-49 and 5 more.")
        assert "ValueError: same: trials 0-49," in text
        assert "  Only the first 50 logs were read." in text

    def test_it_says_so_when_none_errored(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 1.0, Completion.FAILURE)

        assert describe_errored(job) == "No trial has errored."


class TestRequirements:
    @pytest.fixture
    def job(self, tmp_path: Path) -> JobStatus:
        job = new_job(tmp_path, 6)
        finish(
            job,
            0,
            1.0,
            requirements=[req("touchdown_speed", True), req("fuel_left", True)],
        )
        finish(
            job,
            1,
            1.0,
            Completion.FAILURE,
            requirements=[
                req("touchdown_speed", False, "speed 4.2 over the 3.0 limit"),
                req("fuel_left", True),
            ],
        )
        finish(
            job,
            2,
            1.0,
            Completion.FAILURE,
            requirements=[
                req("touchdown_speed", False, "speed 4.2 over the 3.0 limit"),
                req("fuel_left", False, "empty"),
            ],
        )
        finish(
            job,
            4,
            1.0,
            Completion.FAILURE,
            requirements=[
                req("touchdown_speed", False, "speed 5.0\n  over the 3.0 limit")
            ],
        )
        return job

    def test_every_requirement_is_listed_most_failures_first(
        self, job: JobStatus
    ) -> None:
        assert describe_requirements(job).splitlines() == [
            "Requirements, most failures first:",
            "  touchdown_speed: failed in 3 of 4 trials (pass rate 25.0%)",
            "  fuel_left: failed in 1 of 3 trials (pass rate 66.7%)",
        ]

    def test_ties_are_listed_by_name(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 1.0, requirements=[req("b", True), req("a", True)])

        assert [
            line.split(":")[0] for line in describe_requirements(job).splitlines()[1:]
        ] == [
            "  a",
            "  b",
        ]

    def test_a_named_requirement_gives_the_trials_that_missed_it_and_why(
        self, job: JobStatus
    ) -> None:
        assert describe_requirements(job, "touchdown_speed").splitlines() == [
            "touchdown_speed: failed in 3 of 4 trials (pass rate 25.0%).",
            "Failed in trials: 1-2, 4.",
            "Reasons given:",
            "  speed 4.2 over the 3.0 limit (2 trials)",
            "  speed 5.0 over the 3.0 limit",
        ]

    def test_a_part_of_the_name_is_enough_when_it_is_the_only_match(
        self, job: JobStatus
    ) -> None:
        assert describe_requirements(job, "FUEL").startswith(
            "fuel_left: failed in 1 of 3 trials"
        )

    def test_the_exact_name_wins_over_a_longer_one_that_contains_it(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 3)
        finish(
            job,
            0,
            1.0,
            Completion.FAILURE,
            requirements=[req("speed", False, "slow"), req("speed_max", True)],
        )

        assert describe_requirements(job, "speed").startswith(
            "speed: failed in 1 of 1 trials"
        )

    def test_a_name_that_matches_two_is_refused_with_the_names(
        self, job: JobStatus
    ) -> None:
        """Both names contain `_`, so picking one would answer about a requirement the user may not mean."""
        text = describe_requirements(job, "_")

        assert text == (
            "No requirement is named '_'. The requirements are: fuel_left, touchdown_speed."
        )

    def test_an_unknown_name_is_refused_with_the_names(self, job: JobStatus) -> None:
        assert describe_requirements(job, "altitude") == (
            "No requirement is named 'altitude'. The requirements are: fuel_left, touchdown_speed."
        )

    def test_a_requirement_nobody_missed_has_no_failure_list(
        self, job: JobStatus
    ) -> None:
        job = new_job(job.workdir, 2)
        finish(job, 0, 1.0, requirements=[req("ok", True)])

        assert describe_requirements(job, "ok") == (
            "ok: failed in 0 of 1 trials (pass rate 100.0%)."
        )

    def test_a_failure_with_no_message_says_so(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 1.0, Completion.FAILURE, requirements=[req("r", False, "")])

        assert "  (no message)" in describe_requirements(job, "r")

    def test_a_long_reason_is_cut(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        finish(
            job, 0, 1.0, Completion.FAILURE, requirements=[req("r", False, "x" * 500)]
        )

        reason = describe_requirements(job, "r").splitlines()[-1]

        assert reason == "  " + "x" * 160

    def test_only_the_most_common_reasons_are_listed(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 10)
        for n in range(8):
            finish(
                job,
                n,
                1.0,
                Completion.FAILURE,
                requirements=[req("r", False, f"reason {n}")],
            )

        reasons = describe_requirements(job, "r").split("Reasons given:\n")[1]

        assert len(reasons.splitlines()) == 5

    def test_it_says_so_when_there_are_no_results(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 1.0)

        for name in ("", "anything"):
            assert describe_requirements(job, name) == (
                "No requirement results yet: none were registered, or no trial has finished."
            )


class TestTrialsThatMissed:
    """The numbers of the trials a requirement failed, for versus mode to pin without the model retyping them."""

    @pytest.fixture
    def job(self, tmp_path: Path) -> JobStatus:
        job = new_job(tmp_path, 6)
        finish(job, 0, 1.0, requirements=[req("touchdown_speed", True)])
        finish(job, 1, 1.0, Completion.FAILURE, [req("touchdown_speed", False)])
        finish(
            job,
            2,
            1.0,
            Completion.FAILURE,
            [req("touchdown_speed", False), req("landing_position_error", False)],
        )
        finish(job, 3, 1.0, Completion.ERROR)
        return job

    def test_a_requirement_gives_the_trials_that_missed_it(
        self, job: JobStatus
    ) -> None:
        assert job_report.trials_that_missed(job, "touchdown_speed") == [1, 2]
        assert job_report.trials_that_missed(job, "landing_position_error") == [2]

    def test_a_part_of_one_name_is_enough(self, job: JobStatus) -> None:
        assert job_report.trials_that_missed(job, "speed") == [1, 2]

    def test_any_gives_the_trials_that_missed_a_requirement_and_error_the_ones_that_crashed(
        self, job: JobStatus
    ) -> None:
        assert job_report.trials_that_missed(job, "any") == [1, 2]
        assert job_report.trials_that_missed(job, "error") == [3]

    def test_error_is_not_taken_for_the_one_requirement_with_error_in_its_name(
        self, job: JobStatus
    ) -> None:
        """`landing_position_error` contains `error`, and a user asking for the trials that errored did not mean it."""
        assert job_report.trials_that_missed(job, "error") != [2]

    def test_a_requirement_with_exactly_that_name_wins_over_the_special_word(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 3)
        finish(job, 0, 1.0, Completion.FAILURE, [req("any", False)])
        finish(job, 1, 1.0, Completion.FAILURE, [req("other", False)])

        assert job_report.trials_that_missed(job, "any") == [0]

    def test_a_name_no_requirement_has_is_answered_with_the_ones_that_exist(
        self, job: JobStatus
    ) -> None:
        text = job_report.trials_that_missed(job, "fuel")

        assert isinstance(text, str)
        assert "touchdown_speed" in text

    def test_a_requirement_nobody_missed_gives_no_trials(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 1.0, requirements=[req("touchdown_speed", True)])

        assert job_report.trials_that_missed(job, "touchdown_speed") == []

    def test_without_requirement_results_a_name_says_so_but_any_still_works(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 1.0, Completion.ERROR)

        assert "No requirement results" in str(
            job_report.trials_that_missed(job, "speed")
        )
        assert job_report.trials_that_missed(job, "error") == [0]


class TestConfiguration:
    def test_it_says_how_the_job_was_started(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)
        job.args_used = [1, "fast"]
        job.kwargs_used = {"gain": 2.5}
        job.generator = ("make", tmp_path / "gen.py", 12)

        lines = describe_configuration(job).splitlines()

        assert (
            "Job type: monte_carlo" in lines or "Job type: JobType.MONTE_CARLO" in lines
        )
        assert "Started by " + job.started_by + " at 2026-01-01T12:00:00+00:00" in lines
        assert "Execution mode: local" in lines
        assert "Parallel processes: 2" in lines
        assert "Seed: 7" in lines
        assert f"Working folder: {tmp_path}" in lines
        assert f"Generator: make ({tmp_path / 'gen.py'}:12)" in lines
        assert "Runtime: runtime" in lines
        assert "Arguments (--arg): [1, 'fast']" in lines
        assert "Keyword arguments (--kwarg): {'gain': 2.5}" in lines

    def test_a_missing_seed_and_no_arguments_say_so(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)
        job.seed = None

        text = describe_configuration(job)

        assert "Seed: none given" in text
        assert "Arguments (--arg): none" in text
        assert "Keyword arguments (--kwarg): none" in text

    def test_a_slurm_job_gives_its_id(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)
        job.execution_mode = ExecutionMode.SLURM
        job.slurm_job_id = "424242"

        assert "Execution mode: slurm (SLURM job 424242)" in describe_configuration(job)

    def test_only_an_optimization_names_its_objective(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)
        assert "Objective" not in describe_configuration(job)

        job.job_type = JobType.OPTIMIZE
        job.objective = ("score", None, None)

        assert "Objective: score" in describe_configuration(job).splitlines()


class TestTrial:
    def test_a_finished_trial_gives_its_steps_total_and_requirements(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 3)
        finish(
            job,
            1,
            4.0,
            Completion.FAILURE,
            generating=1.5,
            requirements=[
                req("a", True),
                req("b", False, "too\nfast"),
                req("c", False, ""),
            ],
        )

        assert describe_trial(job, 1, at(10)).splitlines() == [
            "Trial 1: failure (step: solving)",
            "  pending: 0.00s",
            "  generating: 1.50s",
            "  solving: 4.00s",
            "  total time: 5.50s",
            "  requirements:",
            "    passed a",
            "    FAILED b: too fast",
            "    FAILED c",
        ]

    def test_a_running_trial_says_how_long_it_has_been_at_it(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 3)
        begin(job, 0, generating_started=0, generating_took=4, solving_started=4)

        lines = describe_trial(job, 0, at(10)).splitlines()

        assert lines[0] == "Trial 0: incomplete (step: solving)"
        assert "  generating: 4.00s" in lines
        assert "  solving: in progress" in lines
        assert "  running for 10.00s so far, in solving for 6.00s" in lines

    def test_an_errored_trial_gives_where_it_broke_and_what_its_log_says(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 3)
        job.update_trial(
            TrialStatus(
                trial_num=0,
                completion=Completion.ERROR,
                step="generating",
                generating=StepStatus(started=T0),
            ),
            save=False,
        )
        write_log(job, 0, failure_log(0, "ValueError", "bad mass"))

        assert "  broke while generating: ValueError: bad mass" in (
            describe_trial(job, 0, at(5))
        )

    def test_an_errored_trial_with_no_log_says_so_and_points_at_the_log_tool(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 3)
        finish(job, 0, 1.0, Completion.ERROR)

        assert (
            "  broke while solving (no cause found in its log; get_trial_log shows the log)"
            in describe_trial(job, 0, at(5))
        )

    def test_a_trial_that_did_not_error_does_not_read_its_log(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 3)
        finish(job, 0, 1.0, Completion.FAILURE)
        write_log(job, 0, failure_log(0, "ValueError", "not shown"))

        assert "not shown" not in describe_trial(job, 0, at(5))

    def test_a_trial_the_job_does_not_have_is_refused_with_the_range(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 3)

        assert describe_trial(job, 9, at(0)) == (
            "This job has no trial 9; its trials are numbered 0 to 2."
        )

    def test_a_trial_without_a_status_says_it_has_not_been_picked_up(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 3)

        assert describe_trial(job, 2, at(0)) == (
            "Trial 2 has no status yet: it has not been picked up."
        )

    def test_a_job_with_no_trials_does_not_fail(self, tmp_path: Path) -> None:
        assert describe_trial(new_job(tmp_path, 0), 0, at(0)) == (
            "This job has no trial 0; its trials are numbered 0 to 0."
        )


class TestTheClock:
    def test_now_is_the_current_time_with_a_time_zone(self) -> None:
        before = datetime.now(UTC)

        stamp = job_report.now()

        assert stamp.tzinfo is not None
        assert before <= stamp <= datetime.now(UTC)


class TestRankingEveryFinishedTrial:
    @pytest.fixture
    def job(self, tmp_path: Path) -> JobStatus:
        job = new_job(tmp_path, 6)
        finish(job, 0, 4.0)
        finish(job, 1, 9.5, Completion.ERROR)
        finish(job, 2, 1.25, Completion.FAILURE)
        finish(job, 3, 99.0, Completion.TERMINATED)
        begin(job, 4, generating_started=0)
        return job

    def test_any_includes_the_errored_trials(self, job: JobStatus) -> None:
        assert describe_ranking(job, 20, True, "any").splitlines() == [
            "Longest 4 of 4 trials:",
            "  Trial 3: 99.00s (1m 39s) (terminated)",
            "  Trial 1: 9.50s (error)",
            "  Trial 0: 4.00s (success)",
            "  Trial 2: 1.25s (failure)",
        ]

    def test_a_terminated_trial_counts_as_a_requirement_failure(
        self, job: JobStatus
    ) -> None:
        assert describe_ranking(job, 20, True, "failure").splitlines()[0] == (
            "Longest 2 of 2 requirement-failing trials:"
        )

    def test_it_says_so_when_nothing_has_finished(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)

        assert describe_ranking(job, 5, True, "any") == (
            "No trial has finished yet, so there are no times to rank."
        )


class TestRecent:
    @pytest.fixture
    def job(self, tmp_path: Path) -> JobStatus:
        job = new_job(tmp_path, 8)
        finish(job, 0, 5.0)
        finish(
            job,
            1,
            20.0,
            Completion.FAILURE,
            requirements=[req("speed", False), req("fuel", False), req("ok", True)],
        )
        finish(job, 2, 30.0, Completion.ERROR)
        finish(job, 3, 40.0)
        begin(job, 4, generating_started=0)
        write_log(job, 2, failure_log(2, "ValueError", "bad mass"))
        return job

    def test_the_newest_come_first_with_when_they_finished_and_how_it_went(
        self, job: JobStatus
    ) -> None:
        assert describe_recent(job, at(100), 3).splitlines() == [
            "Most recent 3 of 4 trials, newest first:",
            "  Trial 3: success, finished 60.00s (1m 0s) ago, took 40.00s",
            "  Trial 2: error, finished 70.00s (1m 10s) ago, took 30.00s, ValueError: bad mass",
            "  Trial 1: failure, finished 80.00s (1m 20s) ago, took 20.00s, missed speed, fuel",
        ]

    def test_a_running_trial_is_not_listed(self, job: JobStatus) -> None:
        assert "Trial 4" not in describe_recent(job, at(100), 20)

    def test_the_outcome_picks_which_finished_trials(self, job: JobStatus) -> None:
        assert describe_recent(job, at(100), 5, "error").splitlines() == [
            "Most recent 1 of 1 errored trials, newest first:",
            "  Trial 2: error, finished 70.00s (1m 10s) ago, took 30.00s, ValueError: bad mass",
        ]

    def test_an_errored_trial_with_no_log_says_so(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 3.0, Completion.ERROR)

        assert describe_recent(job, at(10)).endswith(", no cause found in its log")

    def test_a_failure_that_names_no_requirement_has_no_missed_list(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 3.0, Completion.TERMINATED)

        assert "missed" not in describe_recent(job, at(10))

    def test_a_long_list_of_missed_requirements_is_cut(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        finish(
            job,
            0,
            3.0,
            Completion.FAILURE,
            requirements=[req(name, False) for name in "abcde"],
        )

        assert describe_recent(job, at(10)).endswith(", missed a, b, c and 2 more")

    def test_a_long_list_is_cut_at_the_limit_and_a_short_one_at_one(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 30)
        for n in range(25):
            finish(job, n, float(n + 1))

        assert len(describe_recent(job, at(100), 100).splitlines()) == 1 + 20
        assert len(describe_recent(job, at(100), 0).splitlines()) == 1 + 1

    def test_a_clock_before_the_finish_never_gives_a_negative_time(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 50.0)

        assert "finished 0.00s ago" in describe_recent(job, at(10))

    @pytest.mark.parametrize(
        ("outcome", "text"),
        [
            ("any", "No trial has finished yet."),
            ("error", "No errored trial has finished yet."),
            ("success", "No successful trial has finished yet."),
        ],
    )
    def test_it_says_so_when_none_have_finished(
        self, tmp_path: Path, outcome: job_report.Outcome, text: str
    ) -> None:
        job = new_job(tmp_path, 3)
        begin(job, 0, generating_started=0)

        assert describe_recent(job, at(10), 5, outcome) == text


class TestTimeline:
    @pytest.fixture
    def job(self, tmp_path: Path) -> JobStatus:
        """Four trials that finished 5, 15, 75 and 80 seconds into the job, which is 80 seconds long: eight slices of 10 seconds."""
        job = new_job(tmp_path, 6)
        finish(job, 0, 5.0)
        finish(job, 1, 15.0)
        finish(job, 2, 75.0, Completion.FAILURE)
        finish(job, 3, 80.0, Completion.ERROR)
        return job

    def test_each_slice_says_how_many_finished_and_how_they_ended(
        self, job: JobStatus
    ) -> None:
        assert describe_timeline(job, at(200)).splitlines()[:10] == [
            "4 trials finished in the 80.00s (1m 20s) the job has run, in 8 slices of 10s:",
            "  +0s to +10s: 1 finished (1 succeeded), mean 5.00s",
            "  +10s to +20s: 1 finished (1 succeeded), mean 15.00s",
            "  +20s to +30s: none finished",
            "  +30s to +40s: none finished",
            "  +40s to +50s: none finished",
            "  +50s to +1m 0s: none finished",
            "  +1m 0s to +1m 10s: none finished",
            "  +1m 10s to +1m 20s: 2 finished (0 succeeded, 1 failed requirements, 1 errored), mean 75.00s (1m 15s)",
            "The first errored trial to finish was trial 3, at +1m 20s.",
        ]

    def test_an_idle_job_says_how_long_ago_the_last_trial_finished(
        self, job: JobStatus
    ) -> None:
        text = describe_timeline(job, at(200))

        assert text.splitlines()[-1] == (
            "Nothing is running, and the last trial finished 120.00s (2m 0s) ago."
        )

    def test_the_job_runs_to_the_clock_while_a_trial_is_running(
        self, job: JobStatus
    ) -> None:
        begin(job, 4, generating_started=70)

        lines = describe_timeline(job, at(80)).splitlines()

        assert lines[0].startswith("4 trials finished in the 80.00s (1m 20s)")
        assert not any("Nothing is running" in line for line in lines)

    def test_a_trial_that_finished_before_the_job_started_is_in_the_first_slice(
        self, tmp_path: Path
    ) -> None:
        """A resumed job starts after the trials it carried over ended. Counting one of those from the end of the list put it in the last slice."""
        job = new_job(tmp_path, 4)
        job.start_time = at(50)
        finish(job, 0, 45.0)
        finish(job, 1, 90.0)

        lines = describe_timeline(job, at(500)).splitlines()

        assert lines[1] == "  +0s to +5s: 1 finished (1 succeeded), mean 45.00s"
        assert (
            lines[8] == "  +35s to +40s: 1 finished (1 succeeded), mean 90.00s (1m 30s)"
        )

    def test_a_finished_job_has_no_idle_note(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 5.0)
        finish(job, 1, 9.0)

        assert "Nothing is running" not in describe_timeline(job, at(500))

    def test_a_slice_with_only_errors_has_no_mean(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 4)
        finish(job, 0, 10.0, Completion.ERROR)

        text = describe_timeline(job, at(500))

        assert "1 finished (0 succeeded, 1 errored)" in text
        assert "mean" not in text

    def test_trials_that_finish_at_the_start_fall_in_one_slice(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 2)
        finish(job, 0, 0.0)

        text = describe_timeline(job, at(500))

        assert "in 1 slices of 1s:" in text
        assert "  +0s to +1s: 1 finished (1 succeeded)" in text

    def test_it_says_so_when_nothing_has_finished(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 3)
        begin(job, 0, generating_started=0)

        assert describe_timeline(job, at(10)) == (
            "No trial has finished yet, so there is no timeline."
        )


class TestTrialLog:
    @pytest.fixture
    def job(self, tmp_path: Path) -> JobStatus:
        job = new_job(tmp_path, 4)
        finish(job, 1, 5.0, Completion.ERROR)
        write_log(job, 1, failure_log(1, "ValueError", "bad mass"))
        return job

    def test_each_entry_has_its_time_level_and_message(self, job: JobStatus) -> None:
        assert describe_trial_log(job, 1).splitlines() == [
            "Last 2 of 2 log entries of trial 1, oldest first:",
            "  12:00:05 INFO     starting",
            "  12:00:09 ERROR    Trial 1 failed with the following error: bad mass",
            "      Traceback (most recent call last):",
            '        File "runner.py", line 600, in run',
            "          solve()",
            "      ValueError: bad mass",
        ]

    def test_a_level_keeps_that_level_and_worse(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        write_log(
            job,
            0,
            [
                log_line("info"),
                log_line("warn", "WARNING"),
                log_line("err", "ERROR"),
                log_line("crit", "CRITICAL"),
                log_line("loose", "Invalid Level"),
            ],
        )

        warnings = describe_trial_log(job, 0, level="warning").splitlines()
        errors = describe_trial_log(job, 0, level="error").splitlines()

        assert warnings[0] == (
            "Last 3 of 3 warning-or-worse log entries of trial 0, oldest first:"
        )
        assert [line.split()[-1] for line in warnings[1:]] == ["warn", "err", "crit"]
        assert [line.split()[-1] for line in errors[1:]] == ["err", "crit"]
        assert len(describe_trial_log(job, 0).splitlines()) == 1 + 5

    def test_it_says_so_when_no_entry_is_at_that_level(self, job: JobStatus) -> None:
        write_log(job, 2, [log_line("fine"), log_line("fine too")])

        assert describe_trial_log(job, 2, level="error") == (
            "The log of trial 2 has no error entries (2 entries in all)."
        )

    def test_the_last_entries_are_shown_and_the_count_is_capped(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 2)
        write_log(job, 0, [log_line(f"m{n}") for n in range(40)])

        three = describe_trial_log(job, 0, count=3).splitlines()

        assert three[0] == "Last 3 of 40 log entries of trial 0, oldest first:"
        assert [line.split()[-1] for line in three[1:]] == ["m37", "m38", "m39"]
        assert len(describe_trial_log(job, 0, count=100).splitlines()) == 1 + 30
        assert len(describe_trial_log(job, 0, count=0).splitlines()) == 1 + 1

    def test_a_long_traceback_keeps_its_first_line_and_its_last_few(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 2)
        message = "\n".join(f"line {n}" for n in range(20))
        write_log(job, 0, [log_line(message, "ERROR")])

        lines = describe_trial_log(job, 0).splitlines()

        assert [line.strip() for line in lines[1:]] == [
            "12:00:05 ERROR    line 0",
            "... 15 lines left out ...",
            "line 16",
            "line 17",
            "line 18",
            "line 19",
        ]

    def test_a_long_line_is_cut(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 2)
        write_log(job, 0, [log_line("y" * 1000)])

        assert (
            describe_trial_log(job, 0).splitlines()[1].endswith("INFO     " + "y" * 300)
        )

    def test_a_long_log_drops_its_oldest_entries_to_stay_short(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 2)
        write_log(job, 0, [log_line(f"{n:02d}" + "z" * 298) for n in range(30)])

        text = describe_trial_log(job, 0, count=30)

        header = text.splitlines()[0]
        shown = int(header.split()[1])
        assert 1 <= shown < 30
        assert header.endswith("of 30 log entries of trial 0, oldest first:")
        assert "29" + "z" * 298 in text
        assert "00" + "z" * 298 not in text
        assert text.splitlines()[-1] == (
            "(older entries were left out to keep this short)"
        )

    def test_an_entry_with_no_time_or_a_bad_one_shows_dashes(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 2)
        write_log(
            job,
            0,
            [
                log_line("none", seconds=None),
                {"level": "INFO", "message": "huge", "timestamp": 1e30},
                {"level": "INFO", "message": "text", "timestamp": "soon"},
            ],
        )

        lines = describe_trial_log(job, 0).splitlines()[1:]

        assert all(line.startswith("  --:--:-- INFO") for line in lines)

    def test_an_empty_log_says_so(self, job: JobStatus) -> None:
        write_log(job, 3, [])

        assert describe_trial_log(job, 3) == "The log of trial 3 has no entries."

    def test_a_trial_with_no_log_file_says_so(self, job: JobStatus) -> None:
        assert describe_trial_log(job, 0) == "Trial 0 has no log file."

    def test_a_trial_the_job_does_not_have_is_refused(self, job: JobStatus) -> None:
        assert describe_trial_log(job, 9) == (
            "This job has no trial 9; its trials are numbered 0 to 3."
        )


class TestComparison:
    @pytest.fixture
    def job(self, tmp_path: Path) -> JobStatus:
        job = new_job(tmp_path, 10)
        finish(
            job,
            3,
            4.0,
            generating=1.0,
            requirements=[req("speed", True), req("fuel", True)],
        )
        finish(
            job,
            7,
            9.5,
            Completion.FAILURE,
            generating=1.0,
            requirements=[req("speed", False, "too fast"), req("fuel", True)],
        )
        return job

    def test_trials_are_set_side_by_side(self, job: JobStatus) -> None:
        assert describe_comparison(job, [3, 7], at(20)).splitlines() == [
            "Comparing trials 3, 7:",
            "  outcome: trial 3 success, trial 7 failure",
            "  total time: trial 3 5.00s, trial 7 10.50s",
            "  pending: trial 3 0.00s, trial 7 0.00s",
            "  generating: trial 3 1.00s, trial 7 1.00s",
            "  solving: trial 3 4.00s, trial 7 9.50s",
            "  trial 7 took 5.50s longer than trial 3 (2.1x)",
            "  requirements that differ:",
            "    speed: trial 3 passed, trial 7 FAILED (too fast)",
            "  requirements that are the same in every trial: fuel (passed)",
        ]

    def test_the_order_asked_for_is_kept_and_a_repeat_is_dropped(
        self, job: JobStatus
    ) -> None:
        lines = describe_comparison(job, [7, 3, 7], at(20)).splitlines()

        assert lines[0] == "Comparing trials 7, 3:"
        assert lines[1] == "  outcome: trial 7 failure, trial 3 success"

    def test_a_running_trial_shows_its_time_so_far_and_is_left_out_of_the_spread(
        self, job: JobStatus
    ) -> None:
        begin(job, 4, generating_started=0, generating_took=2.0, solving_started=2)

        lines = describe_comparison(job, [3, 4], at(10)).splitlines()

        assert "  outcome: trial 3 success, trial 4 incomplete (solving)" in lines
        assert "  total time: trial 3 5.00s, trial 4 10.00s so far" in lines
        assert not any("longer than" in line for line in lines)

    def test_equal_times_have_no_spread_line(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 4)
        finish(job, 0, 2.0)
        finish(job, 1, 2.0)

        assert "longer than" not in describe_comparison(job, [0, 1], at(5))

    def test_a_trial_that_took_no_time_has_no_ratio(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 4)
        finish(job, 0, 0.0)
        finish(job, 1, 2.0)

        assert "longer than" not in describe_comparison(job, [0, 1], at(5))

    def test_a_requirement_only_one_trial_has_is_not_checked_in_the_other(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 4)
        finish(job, 0, 2.0, requirements=[req("a", True)])
        finish(job, 1, 2.0)

        text = describe_comparison(job, [0, 1], at(5))

        assert "    a: trial 0 passed, trial 1 not checked" in text

    def test_a_requirement_that_failed_in_every_trial_is_the_same_in_each(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 4)
        for n in (0, 1):
            finish(
                job, n, 2.0, Completion.FAILURE, requirements=[req("a", False, f"m{n}")]
            )

        text = describe_comparison(job, [0, 1], at(5))

        assert "  requirements that are the same in every trial: a (FAILED)" in text
        assert "requirements that differ" not in text

    def test_trials_with_no_requirements_say_so(self, tmp_path: Path) -> None:
        job = new_job(tmp_path, 4)
        finish(job, 0, 2.0)
        finish(job, 1, 3.0)

        assert "  requirements: none recorded" in describe_comparison(
            job, [0, 1], at(5)
        )

    def test_an_errored_trial_gives_what_its_log_says_or_that_there_is_none(
        self, tmp_path: Path
    ) -> None:
        job = new_job(tmp_path, 4)
        finish(job, 0, 2.0, Completion.ERROR)
        finish(job, 1, 3.0, Completion.ERROR)
        finish(job, 2, 3.0)
        write_log(job, 0, failure_log(0, "ValueError", "bad mass"))

        lines = describe_comparison(job, [0, 1, 2], at(5)).splitlines()

        assert "  trial 0 errored: ValueError: bad mass" in lines
        assert "  trial 1 errored: no cause found in its log" in lines
        assert not any("trial 2 errored" in line for line in lines)

    def test_one_trial_is_not_a_comparison(self, job: JobStatus) -> None:
        for named in ([3], [3, 3], []):
            assert describe_comparison(job, named, at(5)) == (
                "Name at least two different trials to compare, such as [3, 7]."
            )

    def test_too_many_trials_are_refused(self, job: JobStatus) -> None:
        assert describe_comparison(job, list(range(7)), at(5)) == (
            "Compare at most 6 trials at once; 7 were named."
        )

    def test_a_trial_the_job_lacks_or_has_not_started_is_refused_by_name(
        self, job: JobStatus
    ) -> None:
        assert describe_comparison(job, [3, 99, 8], at(5)).splitlines() == [
            "This job has no trial 99; its trials are numbered 0 to 9.",
            "Trial 8 has no status yet: it has not been picked up.",
        ]
