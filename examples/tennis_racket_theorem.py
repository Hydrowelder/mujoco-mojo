"""
This file generates an example model of the [tennis racket theorem](https://en.wikipedia.org/wiki/Tennis_racket_theorem).

"""

from pathlib import Path

import mujoco
import numpy as np

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

logger = mojo.utils.get_logger(__name__)


class Handoff(mojo.UserData):
    racket: mojo.Body


def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Generates the tennis racket model with distinct inertial properties."""
    # Assets for visualization
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

    # Setup world and options
    mojo_model.mjcf.options = [
        mojo.Option(
            integrator=mojo.Integrator.RK4,
            timestep=0.001,
            gravity=np.asarray((0, 0, 0)),
        )
    ]

    mojo_model.mjcf.worldbody = mojo.WorldBody(
        geoms=[
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

    # Major dimensions
    total_racket_length = 70.0
    total_handle_length = 30.0
    total_head_width = 27.0
    total_head_thickness = 1.0
    handle_radius = 1.5

    # Derived values
    handle_half_length = total_handle_length / 2.0
    total_head_length = total_racket_length - total_handle_length
    head_half_length = total_head_length / 2.0
    head_half_width = total_head_width / 2.0
    head_half_thickness = total_head_thickness / 2.0

    # Inertias
    I_minor = 700.0  # Around the handle (X)
    I_inter = 2000.0  # Flip axis (Y)
    I_major = 2400.0  # Swing axis (Z)

    mojo_model.mjcf.worldbody.bodies = [
        # Define the racket
        racket := mojo.Body(
            name=mojo.BodyName("racket"),
            freejoints=[mojo.FreeJoint()],
            # Distinct moments of inertia
            inertial=mojo.Inertial(
                pos=mojo.Pos(pos=np.array((0, 0, 0))),
                mass=1,
                diaginertia=np.array([I_minor, I_inter, I_major]),
            ),
            # Add a graphic for the racket
            geoms=[
                mojo.GeomCylinder(
                    name=mojo.GeomName("handle"),
                    size=np.array([handle_radius, handle_half_length]),
                    pose=mojo.PoseEuler(
                        pos=np.array([-handle_half_length, 0, 0]),
                        euler=np.array([0, 90, 0]),
                    ),
                    rgba=mojo.utils.Color.WHITE.rgba,
                ),
                mojo.GeomEllipsoid(
                    name=mojo.GeomName("red_half"),
                    size=np.array(
                        [head_half_length, head_half_width, head_half_thickness]
                    ),
                    pose=mojo.PoseQuat(
                        pos=np.array([head_half_length, 0, head_half_thickness])
                    ),
                    rgba=mojo.utils.Color.RED_500.rgba,
                ),
                mojo.GeomEllipsoid(
                    name=mojo.GeomName("blue_half"),
                    size=np.array(
                        [head_half_length, head_half_width, head_half_thickness]
                    ),
                    pose=mojo.PoseQuat(
                        pos=np.array([head_half_length, 0, -head_half_thickness])
                    ),
                    rgba=mojo.utils.Color.BLUE_500.rgba,
                ),
            ],
        )
    ]

    mojo_model.user_data = Handoff(racket=racket)
    return mojo_model


def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    mj_model: mujoco.MjModel,
    mj_data: mujoco.MjData,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    """Applies perturbation and runs the physics."""
    assert mojo_model.mjcf.worldbody
    handoff = mojo_model.get_user_data(Handoff)

    handoff.racket.set_initial_velocity(
        mj_model,
        mj_data,
        angular_velocity=np.asarray([0.1, 4.0, 0.0]),
        angle=mojo.Angle.RADIAN,
    )

    # Define a custom signal sampler
    def sample_nutation(mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """Adds the [nutation angle](https://en.wikipedia.org/wiki/Nutation) as an output signal."""
        assert runtime_manager.signal_manager

        # Get the angular momentum vector and magnitude
        L = handoff.racket.rt_ang_mom(mj_model, mj_data)
        L_mag = np.linalg.norm(L)

        if L_mag > 1e-9:
            # Get the handle axis in the world frame
            R = handoff.racket.rt_xmat(mj_model, mj_data)
            handle_axis = R[:, 0]

            # Calculate the angle (theta) between L and the handle axis
            # cos(theta) = (L * handle) / (|L| * |handle|)
            dot_product = np.dot(L, handle_axis) / L_mag
            nutation_rad = np.acos(np.clip(dot_product, -1, 1))
            nutation_deg = np.degrees(nutation_rad)

            # Post to the signal manager
            # It will be logged to "Bodies/racket:nutation_deg" ("category/subgroup:attr")
            runtime_manager.signal_manager.post(
                value=float(nutation_deg),
                category=mojo.RequestCategory.BODIES,
                subgroup=f"{handoff.racket.name}",
                attr="nutation_deg",
            )

    with runtime_manager as rm:
        # Request telemetry to monitor the tumbling
        if rm.signal_manager:
            rm.signal_manager.register_sampler(sample_nutation)
            for b in mojo_model.mjcf.worldbody.walk_bodies():
                b.request(rm.signal_manager)

        # Run to observe multiple flips
        while mj_data.time < 10.0:
            rm.step(mj_model, mj_data)

    return mojo_model


if __name__ == "__main__":
    mojo.utils.setup_logger()

    runner = mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
        workdir=Path(__file__).parent / "tennis_racket_theorem_study",
        config=mojo.utils.MonteCarloConfig(n_trial=1, n_proc=1, resume=False),
    )

    runner.run(clean_workdir=True, cleanup_delay=0)
