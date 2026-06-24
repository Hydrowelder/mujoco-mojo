from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import Field

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

logger = mojo.utils.get_logger(__name__)


class Handoff(mojo.UserData):
    """
    User-defined interconnect between the generator and runtime function. Encapsulates MJCF elements for seamless reference in the physics loop.
    """

    box1: mojo.Body
    box2: mojo.Body
    box1_rot: mojo.AnySite
    springs: dict[
        Literal["pz", "mz"],
        tuple[mojo.AnySite, mojo.AnySite, float, float, float],
    ] = Field(default_factory=dict)

    def define_spring(
        self,
        loc: Literal["pz", "mz"],
        box1: mojo.Body,
        box2: mojo.Body,
        mojo_model: mojo.MojoModel,
    ):
        mult = 1 if loc == "pz" else -1

        # Add attachment sites to the bodies
        box1.sites.append(
            base := mojo.SiteSphere(
                name=mojo.SiteName(f"{loc}_spring_base_site"),
                size=0.1,
                pose=mojo.PoseQuat(pos=np.asarray([0.4, 0, mult * 0.5])),
                rgba=mojo.utils.Color.RED_500.rgba,
            )
        )
        box2.sites.append(
            tip := mojo.SiteSphere(
                name=mojo.SiteName(f"{loc}_spring_tip_site"),
                size=0.1,
                pose=mojo.PoseQuat(pos=np.asarray([-0.4, 0, mult * 0.5])),
                rgba=mojo.utils.Color.BLUE_500.rgba,
            )
        )

        # OPTIMIZATION: Define design variables for the search space
        stiffness = mojo_model.sample_design(
            mojo.DesignFloat(
                name=mojo.ValueName(f"{loc}_stiffness"),
                stored_value=100.0,  # this will act as the default value for trial 0
                low=50.0,
                high=200.0,
            )
        )

        stroke = mojo_model.sample_design(
            mojo.DesignFloat(
                name=mojo.ValueName(f"{loc}_stroke"),
                stored_value=(nom := 1.0),
                low=nom * 0.8,
                high=nom * 1.2,
            )
        )

        preload = mojo_model.sample_design(
            mojo.DesignFloat(
                name=mojo.ValueName(f"{loc}_preload"),
                stored_value=(nom := 1000.0 if loc == "pz" else 750.0),
                low=nom * 0.8,
                high=nom * 1.2,
            )
        )

        self.springs.update({loc: (base, tip, stiffness, stroke, preload)})

    def add_spring_force(self, loc: Literal["pz", "mz"]):
        base, tip, stiffness, stroke, preload = self.springs[loc]

        spring_force = rt.PointToPointForce.stroke_compression_spring(
            name=f"{loc}_spring",
            action_site=base,
            xtion_site=tip,
            stiffness=stiffness,
            max_stroke=stroke,
            preload=preload,
        ).register_to_rm()

        # Request high-fidelity telemetry for these components
        base.request()
        tip.request()
        spring_force.request()


def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Assembles the world and identifies optimization design variables."""
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

    # Environment Setup
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
        mojo.Option(timestep=0.001, gravity=np.asarray((0, 0, 0)))
    ]

    # Body Definition
    mojo_model.mjcf.worldbody.bodies.extend(
        [
            box1 := mojo.Body(
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
            ),
            box2 := mojo.Body(
                name=mojo.BodyName("box2"),
                pose=mojo.PoseQuat(pos=np.asarray([0.5, 0, 0])),
                freejoints=[mojo.FreeJoint()],
                geoms=[
                    mojo.GeomBox(
                        name=mojo.GeomName("g2"),
                        size=np.asarray([0.5, 0.5, 0.5]),
                        rgba=mojo.utils.Color.CYAN_500.with_alpha(0.5),
                    )
                ],
            ),
        ]
    )

    box1.sites.append(
        box1_rot_site := mojo.SiteSphere(
            name=mojo.SiteName("box1_rot_site"),
            size=0.2,
            pose=mojo.PoseEuler(euler=np.asarray((45, 45, 45))),
            rgba=mojo.utils.Color.FUCHSIA_500.rgba,
        )
    )

    # Handoff
    handoff = Handoff(box1=box1, box2=box2, box1_rot=box1_rot_site)
    mojo_model.user_data = handoff
    handoff.define_spring("pz", box1, box2, mojo_model)
    handoff.define_spring("mz", box1, box2, mojo_model)

    return mojo_model


def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    """Executes the physics loop and flushes telemetry."""
    with runtime_manager as rm:
        handoff = mojo_model.get_user_data(Handoff)
        assert mojo_model.mjcf.worldbody

        # Apply forces defined during generation
        handoff.add_spring_force("pz")
        handoff.add_spring_force("mz")

        if rm.signal_manager:
            for b in mojo_model.mjcf.worldbody.walk_bodies():
                b.request()
            handoff.box1_rot.request()

        while state.data.time < 2.0:
            rm.step(state)

    return mojo_model


def objective(
    mojo_model: mojo.MojoModel,
    telemetry: Path,
    state: mojo.MjState,
) -> float:
    """
    Score the trial: Low relative angular velocity (stability) weighted against high translational kinetic energy.
    """
    handoff = mojo_model.get_user_data(Handoff)

    w1 = handoff.box1.rt_ang_vel(state)
    w2 = handoff.box2.rt_ang_vel(state)
    omega_score = float(np.linalg.norm(w1 - w2))

    ke1 = handoff.box1.rt_trans_ke(state)
    ke2 = handoff.box2.rt_trans_ke(state)
    total_ke = ke1 + ke2
    ke_score = 1 / (total_ke + 1e-6)

    # J = 10*Omega + 1*KE_inv
    return (10.0 * omega_score) + (1.0 * ke_score)


# --- Entry Point ---
if __name__ == "__main__":
    workdir = Path("./optimization_study").resolve()
    runner = mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
        objective=objective,
        workdir=workdir,
        config=mojo.utils.OptimizerConfig(
            n_trial=200,
            n_proc=4,
            direction="minimize",
            sampler="tpe",
            storage=f"sqlite:///{workdir / 'study.db'}",
            resume=True,
        ),
        seed=42,
    )

    logger.info("Starting Optimization Study...")
    runner.run()
