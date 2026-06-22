"""Tests for MojoRunner distribution table output."""

import os
from pathlib import Path
from unittest import mock

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


def test_force_remove_dir_skips_locked_dojo_script(tmp_path: Path) -> None:
    """A `dojo.sh` still locked by a running dojo session is left in place rather than aborting the whole cleanup."""
    (tmp_path / "dojo.sh").write_text("exec mujoco-mojo dojo .")
    (tmp_path / "other.txt").write_text("x")
    trial_dir = tmp_path / "trials" / "trial_000"
    trial_dir.mkdir(parents=True)
    (trial_dir / "result.json").write_text("{}")

    real_unlink = os.unlink

    def fake_unlink(path, *args, **kwargs):
        if Path(path).name == "dojo.sh":
            raise PermissionError(13, "file is in use by another process")
        return real_unlink(path, *args, **kwargs)

    with mock.patch("os.unlink", side_effect=fake_unlink):
        MojoRunner.force_remove_dir(countdown_from=-1, path=tmp_path)

    assert (tmp_path / "dojo.sh").exists()
    assert not (tmp_path / "other.txt").exists()
    assert not trial_dir.exists()


def test_force_remove_dir_reraises_for_unrelated_locked_file(tmp_path: Path) -> None:
    """A lock on a file other than the top-level dojo.sh still escalates to the rm -rf fallback."""
    (tmp_path / "dojo.sh").write_text("exec mujoco-mojo dojo .")
    (tmp_path / "other.txt").write_text("x")

    real_unlink = os.unlink

    def fake_unlink(path, *args, **kwargs):
        if Path(path).name == "other.txt":
            raise PermissionError(13, "simulated unrelated lock")
        return real_unlink(path, *args, **kwargs)

    with (
        mock.patch("os.unlink", side_effect=fake_unlink),
        mock.patch("subprocess.run") as run_mock,
    ):
        run_mock.return_value = mock.Mock(returncode=0)
        MojoRunner.force_remove_dir(countdown_from=-1, path=tmp_path)

    run_mock.assert_called_once_with(["rm", "-rf", str(tmp_path.resolve())], check=True)
