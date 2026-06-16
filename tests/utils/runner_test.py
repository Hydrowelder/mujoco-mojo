"""Tests for MojoRunner distribution table output."""

from pathlib import Path

import mujoco_mojo as mojo
import pytest

from mujoco_mojo.utils.runner import MojoRunner, MonteCarloConfig


def _dist_generator(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Generator that registers two distributions across two categories."""
    mojo_model.sample_dist(
        mojo.NormalDistribution(
            name=mojo.DistName("link_mass"),
            mu=1.5,
            sigma=0.1,
            category="link_props",
            units="kg",
        )
    )
    mojo_model.sample_dist(
        mojo.UniformDistribution(
            name=mojo.DistName("friction"),
            low=0.2,
            high=0.4,
            category="contact",
        )
    )
    return mojo_model


def _failing_generator(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    raise RuntimeError("intentional failure")


def test_run_monte_carlo_writes_stochas_tables(tmp_path: Path) -> None:
    """Distribution tables land at workdir/stochas after a successful run."""
    runner = MojoRunner(
        generator=_dist_generator,
        workdir=tmp_path,
        config=MonteCarloConfig(n_trial=1, n_proc=1),
    )
    runner.run()

    assert (tmp_path / "stochas" / "link_props" / "normal.csv").exists()
    assert (tmp_path / "stochas" / "contact" / "uniform.csv").exists()


def test_stochas_csv_header_and_content(tmp_path: Path) -> None:
    """CSV header reflects distribution parameters; first data row matches the registered dist."""
    runner = MojoRunner(
        generator=_dist_generator,
        workdir=tmp_path,
        config=MonteCarloConfig(n_trial=1, n_proc=1),
    )
    runner.run()

    lines = (
        (tmp_path / "stochas" / "link_props" / "normal.csv").read_text().splitlines()
    )
    assert lines[0] == "Name,Units,mu,sigma"
    name, units, mu, sigma = lines[1].split(",")
    assert name == "link_mass"
    assert units == "kg"
    assert float(mu) == pytest.approx(1.5)
    assert float(sigma) == pytest.approx(0.1)


def test_stochas_dir_absent_when_all_trials_fail(tmp_path: Path) -> None:
    """No stochas directory is created when every trial fails."""
    runner = MojoRunner(
        generator=_failing_generator,
        workdir=tmp_path,
        config=MonteCarloConfig(n_trial=2, n_proc=1),
    )
    runner.run()

    assert not (tmp_path / "stochas").exists()
