from pathlib import Path

import mujoco
import numpy as np

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

logger = mojo.utils.get_logger(__name__)


def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Generates the MJCF model and samples distributions."""
    # Configure simulation assets
    mojo_model.mjcf.assets = [
        mojo.Asset(
            textures=[
                grid_tex := mojo.TextureBuiltIn(
                    name=mojo.TextureName("grid_tex"),
                    type=mojo.TextureType.D2,
                    builtin=mojo.TextureBuiltInType.CHECKER,
                    width=512,
                    height=512,
                    rgb1=mojo.utils.Color.SLATE_600.rgb,
                    rgb2=mojo.utils.Color.SLATE_800.rgb,
                )
            ],
            materials=[
                grid_mat := mojo.Material(
                    name=mojo.MaterialName("grid_mat"),
                    texture=grid_tex.name,
                    texrepeat=np.asarray((1, 1)),
                )
            ],
        ),
    ]

    mojo_model.mjcf.worldbody = mojo.WorldBody(
        geoms=[]
        if mojo_model.is_nominal
        else [
            mojo.GeomPlane(
                name=mojo.GeomName("floor"),
                size=np.asarray([0, 0, 0.1]),
                pose=mojo.PoseQuat(pos=np.asarray((0, 0, -5))),
                material=grid_mat.name,
                contype=0,
                conaffinity=0,
            ),
        ]
    )

    mojo_model.mjcf.options = [
        mojo.Option(
            integrator=mojo.Integrator.RK4,
            timestep=0.001,
            gravity=np.asarray((0, 0, 0)),
        )
    ]

    # Create two boxes using the walrus operator for immediate referencing
    mojo_model.mjcf.worldbody.bodies.extend(
        [
            _box1 := mojo.Body(
                name=mojo.BodyName("box1"),
                pose=mojo.PoseQuat(pos=np.asarray([-0.5, 0, 0])),
                freejoints=[mojo.FreeJoint()],
                geoms=[
                    mojo.GeomBox(
                        name=mojo.GeomName("g1"),
                        size=np.asarray([0.5, 0.5, 0.5]),
                        rgba=mojo.utils.Color.ROSE_500.with_alpha(0.5),
                    )
                ],
            )
        ]
    )

    return mojo_model


def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    mj_model: mujoco.MjModel,
    mj_data: mujoco.MjData,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    """Executes the physics simulation."""
    with runtime_manager as rm:
        assert mojo_model.mjcf.worldbody
        assert rm.signal_manager

        # Request telemetry for bodies and sites
        for b in mojo_model.mjcf.worldbody.walk_bodies():
            b.request(
                rm.signal_manager,
                attrs=["ke_total", "ke_rot", "xpos", "xvelp", "xvelr"],
            )

        # Step until 2.0 seconds
        while mj_data.time < 2.0:
            rm.step(mj_model, mj_data)

    return mojo_model


if __name__ == "__main__":
    mojo.utils.setup_logger()
    workdir = Path(__file__).parent / "experiment_workspace"

    runner = mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
        workdir=workdir,
        config=mojo.utils.MonteCarloConfig(n_trial=1, n_proc=1),
    )

    runner.run(clean_workdir=True)
