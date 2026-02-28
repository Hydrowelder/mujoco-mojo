import time
from pathlib import Path

import mujoco_mojo as mojo

SEED = 42


def generate(
    trial_num: int,
    overrides: mojo.NamedValueDict = mojo.NamedValueDict(),
) -> mojo.MojoModel:
    print(f"generating nothing {trial_num}!")
    # if trial_num % 2:
    #     raise ValueError("askflaskfhl")
    mojo_model = mojo.MojoModel(
        mjcf=mojo.mjcf.Mujoco(model=mojo.ModelName(f"monte_carlo_test_{trial_num}")),
        values=mojo.Values(seed=SEED, trial_num=trial_num),
    )
    time.sleep(0.01)
    # _normal_draw = (
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

    # breakpoint()
    # mojo_model.values.named.model_dump_json()
    # mojo_model.model_dump_json()
    return mojo_model


def runtime(mojo: mojo.MojoModel):
    print("running nothing!")
    # raise ValueError("blah blah blah")
    time.sleep(0.01)
    return None


def test_monte_carlo():
    mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
        workdir=Path(__file__).parent / "mc_test",
        config=mojo.utils.MonteCarloConfig(n_trial=10, n_proc=1),
    ).run(resume=False)


if __name__ == "__main__":
    # generate(trial_num=0)
    test_monte_carlo()
