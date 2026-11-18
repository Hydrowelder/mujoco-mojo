"""
The jobs that the Dojo documentation screenshots show, so that every screenshot comes from a job with the same trials, signals, failures and error each time.

`scripts/gen_dojo_screenshots.py` runs this file in a child process to fill a work directory, then points a Dojo at it. It can also be run by hand to look at the jobs yourself:

    python scripts/dojo_screenshots_job.py monte-carlo ./shots-mc
    python scripts/dojo_screenshots_job.py optimize ./shots-opt
    mujoco-mojo dojo ./shots-mc

The Monte Carlo job is the docs' own example (`docs/user-guides/workflow/monte_carlo_example.py`: two boxes joined by springs) with three additions so the Monitor and the Mosaic have something to show in every state: trials 3 and 8 fail a requirement, trial 6 raises an error halfway through its run, and a live requirement records its verdicts as a signal. The optimization job is the docs' optimization example (`docs/user-guides/features/optimization_example.py`) with fewer trials, which fills the Morph tab.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from typing import Literal

DOCS_EXAMPLES = Path(__file__).parents[1] / "docs" / "user-guides"

# the examples are plain scripts in the docs, not an installed package, so their folders go on the path to import them
sys.path.insert(0, str(DOCS_EXAMPLES / "workflow"))
sys.path.insert(0, str(DOCS_EXAMPLES / "features"))

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

base = importlib.import_module("monte_carlo_example")
optimization = importlib.import_module("optimization_example")

N_TRIAL = 12
"""Trials in the Monte Carlo job: the nominal trial `trial_00` and eleven sampled ones."""

N_OPTIMIZATION_TRIAL = 30
"""Trials in the optimization job, enough for the optimization history to show a trend."""

FAILING_TRIALS = frozenset({3, 8})
"""The trials that fail the requirement, so the failed list and the yellow tiles are not empty."""

ERROR_TRIAL = 6
"""The trial that raises an error halfway through its run, which is what an errored tile and the Errors card show."""

SEED = 42


def trial_number(mojo_model: mojo.MojoModel) -> int:
    """The number of the trial being run, read from the name of its folder (`trial_07` is 7)."""
    return int(mojo_model.trial_dir.name.rsplit("_", 1)[1])


def generate(
    mojo_model: mojo.MojoModel, *args: object, **kwargs: object
) -> mojo.MojoModel:
    """The docs example's model: two boxes and the springs between them, without the skybox when its images are not there."""
    model = base.generate(mojo_model, *args, **kwargs)
    assert isinstance(model, mojo.MojoModel)
    # the example's skybox reads `textures/stars` from the working directory, and those images are not part of the repository, so a run from anywhere else would fail on the missing files
    if not (Path.cwd() / "textures" / "stars").is_dir():
        model.mjcf.assets = [
            asset
            for asset in model.mjcf.assets
            if not any(
                texture.type == mojo.TextureType.SKYBOX for texture in asset.textures
            )
        ]
    return model


def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args: object,
    **kwargs: object,
) -> mojo.MojoModel:
    """The docs example's run, with two requirements and one trial that breaks halfway through."""
    trial = trial_number(mojo_model)

    def stays_in_family(
        mojo_model: mojo.MojoModel,
        state: mojo.MjState,
        df: mojo.utils.MojoDataFrame | None,
    ) -> tuple[bool, str]:
        """Fails the trials in `FAILING_TRIALS`, whatever their data holds, so the failures are the same on every machine."""
        passed = trial not in FAILING_TRIALS
        return passed, "within limits" if passed else "peak force over the limit"

    def always_passes(
        mojo_model: mojo.MojoModel,
        state: mojo.MjState,
        df: mojo.utils.MojoDataFrame | None,
    ) -> tuple[bool, str]:
        """A live check, which is what puts a `PASS`/`FAIL` signal next to the telemetry."""
        return True, "ok"

    runtime_manager.add_requirement(stays_in_family, name="peak_force_in_limits")
    runtime_manager.add_requirement(always_passes, name="boxes_stay_apart", every=100)

    with runtime_manager as rm:
        handoff = mojo_model.get_user_data(base.Handoff)
        assert mojo_model.mjcf.worldbody

        if (
            mojo_model.is_nominal
        ):  # only the first trial is recorded, which is what the Animation panel plays
            rt.VideoRecorder(
                path=mojo_model.trial_dir / "runtime-anim.gif",
                camera_name=base.FIXED_CAMERA_NAME,
                show_loads=True,
            ).setup(state).register_to_rm()

        handoff.add_spring_force("pz")
        handoff.add_spring_force("mz")

        if rm.signal_manager:
            rm.signal_manager.record_decimation = 10
            for b in mojo_model.mjcf.worldbody.walk_bodies():
                b.request(
                    channels=[
                        "ke_total",
                        "ke_trans",
                        "ke_rot",
                        "xpos",
                        "xvelp",
                        "xvelr",
                    ]
                )
            handoff.box1_rot.request()

        while state.data.time < 2.0:
            rm.step(state)
            if trial == ERROR_TRIAL and state.data.time > 1.0:
                raise RuntimeError("simulated sensor fault at t=1.0 s")

    return mojo_model


def run_monte_carlo(workdir: Path) -> None:
    """Runs the Monte Carlo job into `workdir`, replacing what is there."""
    mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
        workdir=workdir,
        config=mojo.utils.MonteCarloConfig(n_trial=N_TRIAL, n_proc=1, resume=False),
        seed=SEED,
    ).run(clean_workdir=True)


def run_optimization(workdir: Path) -> None:
    """Runs the optimization job into `workdir`, with its study database where the Morph tab reads it."""
    mojo.utils.MojoRunner(
        generator=optimization.generate,
        runtime=optimization.runtime,
        objective=optimization.objective,
        workdir=workdir,
        config=mojo.utils.OptimizerConfig(
            n_trial=N_OPTIMIZATION_TRIAL,
            n_proc=4,
            direction=mojo.Direction.MINIMIZE,
            sampler=mojo.Sampler.TPE,
            storage=f"sqlite:///{workdir / 'study.db'}",
            resume=False,
        ),
        seed=SEED,
    ).run(clean_workdir=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run a job for the Dojo screenshots.")
    parser.add_argument("kind", choices=["monte-carlo", "optimize"])
    parser.add_argument("workdir", type=Path)
    args = parser.parse_args(argv)

    mojo.utils.setup_logger()
    kind: Literal["monte-carlo", "optimize"] = args.kind
    workdir = args.workdir.resolve()
    if kind == "monte-carlo":
        run_monte_carlo(workdir)
    else:
        run_optimization(workdir)


if __name__ == "__main__":
    main()
