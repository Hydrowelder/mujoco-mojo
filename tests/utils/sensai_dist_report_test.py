import json
import math
from pathlib import Path

import pytest

from mujoco_mojo import MojoModel
from mujoco_mojo.stochas import (
    CategoricalDistribution,
    DistName,
    NormalDistribution,
    UniformDistribution,
)
from mujoco_mojo.utils.defaults import (
    NAMED_VALUES_FNAME,
    STOCHAS_DIR_NAME,
    STOCHAS_DISTS_FNAME,
)
from mujoco_mojo.utils.sensai.tools.dist_report import (
    describe_distributions,
    describe_input_outliers,
    describe_trial_inputs,
    find_outliers,
    trials_beyond,
)
from mujoco_mojo.utils.statusing import ExecutionMode, JobStatus, JobType

# mass is normal, mu 10 and sigma 1, so its z-scores are easy to read; drift is
# uniform on 0 to 1, which has no standard deviation
DRAWS: dict[int, dict[str, float | str]] = {
    0: {"mass": 10.0, "drift": 0.5, "mode": "slow"},
    1: {"mass": 12.5, "drift": 0.1, "mode": "fast"},
    2: {"mass": 7.4, "drift": 0.999, "mode": "slow"},
    3: {"mass": 10.5, "drift": 0.3, "mode": "slow"},
    4: {"mass": 13.1, "drift": 0.6, "mode": "fast"},
}
# trial 5 exists but saved nothing, as a trial that has not started
N_TRIALS = 6


def make_job(workdir: Path) -> JobStatus:
    return JobStatus(
        job_type=JobType.MONTE_CARLO,
        execution_mode=ExecutionMode.LOCAL,
        workdir=workdir,
        n_proc=1,
        padding_style="02",
        seed=0,
        generator=("generate", None, None),
        runtime=("runtime", None, None),
        objective=("objective", None, None),
        trial_nums=list(range(N_TRIALS)),
    )


@pytest.fixture
def job(tmp_path: Path) -> JobStatus:
    model = MojoModel()
    model.sample_dist(
        NormalDistribution(
            name=DistName("mass"),
            nominal=10.0,
            mu=10.0,
            sigma=1.0,
            category="body",
            comment="Mass of the box",
        )
    )
    model.sample_dist(
        UniformDistribution(
            name=DistName("drift"), nominal=0.5, low=0.0, high=1.0, category="env"
        )
    )
    model.sample_dist(
        CategoricalDistribution(
            name=DistName("mode"), nominal="slow", choices={"slow": 0.5, "fast": 0.5}
        )
    )
    dists = tmp_path / STOCHAS_DIR_NAME
    dists.mkdir()
    (dists / STOCHAS_DISTS_FNAME).write_text(model.dists.model_dump_json())

    job = make_job(tmp_path)
    for trial, draws in DRAWS.items():
        folder = job.trial_num_to_path(trial)
        folder.mkdir(parents=True)
        (folder / NAMED_VALUES_FNAME).write_text(
            json.dumps(
                {
                    name: {
                        "stored_value": [value] if isinstance(value, float) else value
                    }
                    for name, value in draws.items()
                }
            )
        )
    job.trial_num_to_path(5).mkdir(parents=True)
    return job


class TestDistributions:
    def test_each_is_described_with_its_type_unit_nominal_parameters_and_metadata(
        self, job: JobStatus
    ) -> None:
        text = describe_distributions(job)

        assert "3 input distribution(s)" in text
        mass = next(line for line in text.splitlines() if "mass (" in line)
        assert "(normal)" in mass
        assert "category body" in mass
        assert "nominal 10" in mass
        assert "mu=10" in mass
        assert "sigma=1" in mass
        assert "Mass of the box" in mass
        drift = next(line for line in text.splitlines() if "drift (" in line)
        assert "(uniform)" in drift
        assert "low=0" in drift
        assert "high=1" in drift
        mode = next(line for line in text.splitlines() if "mode (" in line)
        assert "nominal slow" in mode
        assert "choices=slow: 0.5, fast: 0.5" in mode

    def test_a_job_with_none_says_so(self, tmp_path: Path) -> None:
        assert "no input distributions" in describe_distributions(make_job(tmp_path))

    def test_a_file_that_cannot_be_read_is_reported_not_raised(
        self, tmp_path: Path
    ) -> None:
        folder = tmp_path / STOCHAS_DIR_NAME
        folder.mkdir()
        (folder / STOCHAS_DISTS_FNAME).write_text("not json")

        assert "could not be read" in describe_distributions(make_job(tmp_path))


class TestOneTrial:
    def test_a_number_is_shown_with_its_distance_from_the_mean_and_its_percentile(
        self, job: JobStatus
    ) -> None:
        text = describe_trial_inputs(job, 1)

        mass = next(line for line in text.splitlines() if "mass:" in line)
        assert "12.5" in mass
        assert "+2.50 standard deviations from the mean" in mass
        assert "percentile 99.4" in mass

    def test_a_distribution_with_no_standard_deviation_shows_only_its_percentile(
        self, job: JobStatus
    ) -> None:
        drift = next(
            line
            for line in describe_trial_inputs(job, 1).splitlines()
            if "drift:" in line
        )

        assert "standard deviations" not in drift
        assert "percentile 10" in drift

    def test_a_label_is_shown_as_it_is(self, job: JobStatus) -> None:
        mode = next(
            line
            for line in describe_trial_inputs(job, 1).splitlines()
            if "mode:" in line
        )

        assert mode.strip() == "mode: fast"

    def test_a_trial_that_is_not_in_the_job_is_named_with_the_ones_that_are(
        self, job: JobStatus
    ) -> None:
        assert (
            describe_trial_inputs(job, 9)
            == "There is no trial 9 in this job. Its trials are 0-5."
        )

    def test_a_trial_that_saved_nothing_says_so(self, job: JobStatus) -> None:
        assert "saved no sampled values" in describe_trial_inputs(job, 5)


class TestOutliers:
    def test_the_trials_beyond_a_distance_are_found_by_their_z_score(
        self, job: JobStatus
    ) -> None:
        assert trials_beyond(job, "mass", 2.0) == [1, 2, 4]
        assert trials_beyond(job, "mass", 3.0) == [4]
        assert trials_beyond(job, "mass", 5.0) == []

    def test_a_part_of_the_name_is_enough_when_it_is_only_one_input(
        self, job: JobStatus
    ) -> None:
        assert trials_beyond(job, "MAS", 2.0) == [1, 2, 4]

    def test_an_input_that_is_not_there_is_refused_with_the_names_that_are(
        self, job: JobStatus
    ) -> None:
        refused = trials_beyond(job, "wind", 2.0)

        assert isinstance(refused, str)
        assert "No input is named 'wind'" in refused
        assert "mass, drift, mode" in refused

    def test_a_distribution_with_no_standard_deviation_uses_the_equivalent_on_a_normal_curve(
        self, job: JobStatus
    ) -> None:
        found = find_outliers(job, "drift", 3.0)

        assert not isinstance(found, str)
        assert not found.exact
        # 0.999 is the 99.9th percentile, 3.09 on a normal curve; 0.1 is -1.28
        assert [d.trial for d in found.beyond] == [2]
        assert found.beyond[0].sigmas == pytest.approx(3.09, abs=0.01)

    def test_a_normal_one_is_exact(self, job: JobStatus) -> None:
        found = find_outliers(job, "mass", 2.0)

        assert not isinstance(found, str)
        assert found.exact
        assert found.beyond[-1].sigmas == pytest.approx(3.1)

    def test_only_the_trials_that_saved_a_number_are_counted(
        self, job: JobStatus
    ) -> None:
        found = find_outliers(job, "mass", 2.0)

        assert not isinstance(found, str)
        # trial 5 saved nothing
        assert found.drawn == 5

    def test_an_input_drawn_as_a_label_has_no_distance(self, job: JobStatus) -> None:
        refused = trials_beyond(job, "mode", 2.0)

        assert isinstance(refused, str)
        assert "No trial has a number saved for 'mode'" in refused

    @pytest.mark.parametrize("bad", [0, -1, math.nan, math.inf])
    def test_a_distance_that_is_not_above_zero_is_refused(
        self, job: JobStatus, bad: float
    ) -> None:
        refused = trials_beyond(job, "mass", bad)

        assert isinstance(refused, str)
        assert "above 0" in refused

    def test_the_description_lists_the_most_extreme_first_and_all_the_numbers(
        self, job: JobStatus
    ) -> None:
        text = describe_input_outliers(job, "mass", 2.0)

        assert "3 of 5 trials drew it 2 or more standard deviations" in text
        assert text.index("trial 4:") < text.index("trial 2:") < text.index("trial 1:")
        assert "+3.10" in text
        assert "-2.60" in text
        assert "All of them: 1-2, 4." in text

    def test_the_description_says_when_the_distance_is_an_equivalent(
        self, job: JobStatus
    ) -> None:
        assert "not measured by a z-score" in describe_input_outliers(job, "drift", 2.0)
        assert "not measured by a z-score" not in describe_input_outliers(
            job, "mass", 2.0
        )

    def test_the_description_cuts_a_long_list_but_still_gives_every_number(
        self, job: JobStatus
    ) -> None:
        text = describe_input_outliers(job, "mass", 2.0, count=1)

        assert "trial 4:" in text
        assert "trial 2:" not in text
        assert "All of them: 1-2, 4." in text

    def test_no_trial_beyond_the_distance_says_so_and_lists_nothing(
        self, job: JobStatus
    ) -> None:
        text = describe_input_outliers(job, "mass", 5.0)

        assert "0 of 5 trials" in text
        assert "trial " not in text.split("mean.", 1)[1]
