r"""
```bash
mujoco-mojo run \
    --generator mujoco-mojo.tests.monte_carlo_test.monte_carlo.Experiment.generate \
    --runtime mujoco-mojo.tests.monte_carlo_test.monte_carlo.Experiment.runtime \
    --workdir mujoco-mojo/tests/monte_carlo_test/mc_test/ \
    --no-resume \
    monte-carlo \
    --n-trial 10 \
    --n-proc 1
```
"""

import time
from dataclasses import dataclass
from pathlib import Path

import mujoco_mojo as mojo
from mujoco_mojo.utils.logging import get_logger

SEED = 42

logger = get_logger(__name__)


def generate(
    trial_num: int,
    overrides: mojo.NamedValueDict = mojo.NamedValueDict(),
    *args,
    **kwargs,
) -> mojo.MojoModel:
    # print(f"generating nothing {trial_num}!")
    # print(f"Args used: {args}!")
    # print(f"Kwargs used: {kwargs}!")
    logger.info(f"generating nothing {trial_num}!")

    if not trial_num % 5:
        raise ValueError("askflaskfhl")
    mojo_model = mojo.MojoModel(
        mjcf=mojo.mjcf.Mujoco(model=mojo.ModelName(f"monte_carlo_test_{trial_num}")),
        values=mojo.Values(seed=SEED, trial_num=trial_num),
    )
    time.sleep(1)
    # _normal_draw = ( # BUG currently broken due to numpy serialization
    #     (
    #         mojo.NormalDistribution(
    #             name=mojo.DistName("normal_draw"),
    #             mu=5,
    #             sigma=10,
    #             seed=SEED,
    #         )
    #     )
    #     .with_seed(SEED)
    #     .with_trial_num(trial_num)
    #     .update_dicts(
    #         dist_dict=mojo_model.values.dists, named_value_dict=mojo_model.values.named
    #     )
    # )

    # BUG this works since this isnt numpy
    nv = mojo.NamedValue[float](name=mojo.ValueName("value"))
    nv.value = 12.3
    mojo_model.values.named.update(nv)

    return mojo_model


def runtime(mojo_model: mojo.MojoModel, *args, **kwargs):
    # print("running nothing!")
    if mojo_model.values.trial_num == 7:
        raise ValueError("blah blah blah")
    time.sleep(3)

    return None


@dataclass
class Experiment:
    @staticmethod
    def generate(
        trial_num: int,
        overrides: mojo.NamedValueDict = mojo.NamedValueDict(),
        *args,
        **kwargs,
    ) -> mojo.MojoModel:
        return generate(trial_num, overrides, *args, **kwargs)

    @staticmethod
    def runtime(mojo_model: mojo.MojoModel, *args, **kwargs):
        return runtime(mojo_model, *args, **kwargs)


def test_monte_carlo():
    mojo.utils.MojoRunner(
        generator=Experiment.generate,
        runtime=Experiment.runtime,
        workdir=Path(__file__).parent / "mc_test",
        config=mojo.utils.MonteCarloConfig(n_trial=10, n_proc=1),
    ).run(resume=False)

    # mojo.utils.MojoRunner(
    #     generator=generate,
    #     runtime=runtime,
    #     workdir=Path(__file__).parent / "mc_test",
    #     config=mojo.utils.MonteCarloConfig(n_trial=10, n_proc=1),
    # ).run(resume=False)


if __name__ == "__main__":
    # generate(trial_num=0)
    test_monte_carlo()
