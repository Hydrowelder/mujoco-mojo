import time
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from numpydantic import NDArray

import mujoco_mojo as mojo
from mujoco_mojo.utils.log import get_logger

SEED = 42

# logger = get_logger("mujoco_mojo")
logger = get_logger(__name__)


@lru_cache
def cached_method(x: str = "asdf"):
    """Memory cached functions do get cached, but only only for each proc used (`--n-proc` 4 will result in this function being called 4 times)."""
    logger.critical("CACHED METHOD CALLED!!")
    return


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

    cached_method()
    if not trial_num % 5:
        raise ValueError("askflaskfhl")

    asset = mojo.mjcf.Asset(
        textures=[
            texture := mojo.mjcf.Texture(
                name=mojo.TextureName("a_texture"),
                file=mojo.DepPath(__file__).parent / "asset_image.png",
            ),
        ],
        materials=[
            material := mojo.mjcf.Material(
                name=mojo.MaterialName("nickleback"), texture=texture.name
            )
        ],
    )
    body = mojo.mjcf.Body(geoms=[mojo.mjcf.GeomBox(material=material.name)])

    mojo_model = mojo.MojoModel(
        mjcf=mojo.mjcf.Mujoco(
            model=mojo.ModelName(f"monte_carlo_test_{trial_num}"),
            assets=[asset],
            worldbody=mojo.mjcf.WorldBody(bodies=[body]),
        ),
        values=mojo.Values(seed=SEED, trial_num=trial_num),
    )
    time.sleep(0.0001)
    _normal_draw = (
        (
            mojo.NormalDistribution(
                name=mojo.DistName("normal_draw"),
                mu=5,
                sigma=10,
                seed=SEED,
            )
        )
        .with_seed(SEED)
        .with_trial_num(trial_num)
        .sample_and_update_dicts(
            dist_dict=mojo_model.values.dists, named_value_dict=mojo_model.values.named
        )
    )

    nv = mojo.NamedValue[NDArray](name=mojo.ValueName("value"))
    nv.value = np.array([12.3])
    mojo_model.values.named.update(nv)

    return mojo_model


def runtime(mojo_model: mojo.MojoModel, *args, **kwargs):
    # print("running nothing!")
    if mojo_model.values.trial_num == 7:
        raise ValueError("blah blah blah")
    time.sleep(0.0002)

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


# def test_monte_carlo():
#     mojo.utils.MojoRunner(
#         generator=Experiment.generate,
#         runtime=Experiment.runtime,
#         workdir=Path(__file__).parent / "mc_test",
#         config=mojo.utils.MonteCarloConfig(n_trial=10, n_proc=1),
#     ).run(resume=False)

# mojo.utils.MojoRunner(
#     generator=generate,
#     runtime=runtime,
#     workdir=Path(__file__).parent / "mc_test",
#     config=mojo.utils.MonteCarloConfig(n_trial=10, n_proc=1),
# ).run(resume=False)


# if __name__ == "__main__":
#     # generate(trial_num=0)
#     test_monte_carlo()
