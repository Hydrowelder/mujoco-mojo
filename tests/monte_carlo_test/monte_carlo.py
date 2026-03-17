import time
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

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


def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    # print(f"generating nothing {trial_num}!")
    # print(f"Args used: {args}!")
    # print(f"Kwargs used: {kwargs}!")
    logger.info(f"generating nothing {mojo_model.trial_num}!")

    cached_method()
    if not mojo_model.trial_num % 5:
        raise ValueError("askflaskfhl")

    mojo_model.mjcf.assets = [
        mojo.Asset(
            textures=[
                texture := mojo.Texture(
                    name=mojo.TextureName("a_texture"),
                    file=mojo.DepPath(__file__).parent / "asset_image.png",
                ),
            ],
            materials=[
                material := mojo.Material(
                    name=mojo.MaterialName("nickleback"), texture=texture.name
                )
            ],
        )
    ]

    body = mojo.Body(
        geoms=[
            mojo.GeomBox(
                material=material.name,
                size=np.array([1, 1, 1]),
            )
        ]
    )
    mojo_model.mjcf.model = mojo.ModelName(f"monte_carlo_test_{mojo_model.trial_num}")
    mojo_model.mjcf.worldbody = mojo.WorldBody(bodies=[body])

    time.sleep(1)
    _normal_draw = mojo_model.sample_dist(
        mojo.NormalDistribution(
            name=mojo.DistName("normal_draw"),
            nominal=5,
            mu=5,
            sigma=10,
        )
    )

    return mojo_model


def runtime(mojo_model: mojo.MojoModel, *args, **kwargs):
    # print("running nothing!")
    if mojo_model.trial_num == 7:
        raise ValueError("blah blah blah")
    time.sleep(2e-8)

    # initialize managers

    # enter runtime loop
    # defines some forces and outputs

    # exit runtime loop
    # dump duckdb to workdir (or maybe the results manager should be returned by this function and the dumping is handled by the process which called this method)

    return None


@dataclass
class Experiment:
    @staticmethod
    def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
        return generate(mojo_model, *args, **kwargs)

    @staticmethod
    def runtime(mojo_model: mojo.MojoModel, *args, **kwargs) -> None:
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
