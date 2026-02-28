from pathlib import Path

import mujoco_mojo as mojo

SEED = 42


def generate(
    trial_num: int,
    overrides: mojo.NamedValueDict = mojo.NamedValueDict(),
) -> mojo.MojoModel:
    mojo_model = mojo.MojoModel(
        mjcf=mojo.mjcf.Mujoco(model=mojo.ModelName(f"monte_carlo_test_{trial_num}")),
        values=mojo.Values(seed=SEED, trial_num=trial_num),
    )

    _normal_draw = mojo.NormalDistribution(
        name=mojo.DistName("normal_draw"),
        mu=5,
        sigma=10,
        seed=SEED,
    ).update_dicts(
        dist_dict=mojo_model.values.dists, named_value_dict=mojo_model.values.named
    )

    breakpoint()
    mojo_model.values.named.model_dump_json()
    mojo_model.model_dump_json()
    return mojo_model


def test_monte_carlo():
    mojo.utils.MojoRunner(
        generator=generate,
        runtime=None,
        workdir=Path(__file__).parent / "mc_test",
        config=mojo.utils.MonteCarloConfig(n_trial=10, n_proc=1),
    ).run()


if __name__ == "__main__":
    generate(trial_num=0)
    # test_monte_carlo()
