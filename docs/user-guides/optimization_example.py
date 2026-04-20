from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import mujoco
import numpy as np

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

logger = mojo.utils.get_logger(__name__)


@dataclass
class Handoff:
    """
    User-defined interconnect between the generator and runtime function. Encapsulates MJCF elements for seamless reference in the physics loop.
    """

    box1: mojo.Body
    box2: mojo.Body
    box1_rot: mojo.AnySite
    springs: dict[
        Literal["pz", "mz"],
        tuple[mojo.AnySite, mojo.AnySite, float, float, float],
    ] = field(default_factory=dict)

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
        stiffness = mojo_model.design_float(
            name=f"{loc}_stiffness",
            default=100.0,
            low=50.0,
            high=200.0,
        )

        stroke = mojo_model.design_float(
            name=f"{loc}_stroke",
            default=(nom := 1.0),
            low=nom * 0.8,
            high=nom * 1.2,
        )

        preload = mojo_model.design_float(
            name=f"{loc}_preload",
            default=(nom := 1000.0 if loc == "pz" else 750.0),
            low=nom * 0.8,
            high=nom * 1.2,
        )

        self.springs.update({loc: (base, tip, stiffness, stroke, preload)})

    def add_spring_force(self, loc: Literal["pz", "mz"], rm: rt.RuntimeManager):
        assert rm.results_manager is not None
        base, tip, stiffness, stroke, preload = self.springs[loc]

        spring_force = rt.PointToPointForce.stroke_compression_spring(
            name=f"{loc}_spring",
            action_site=base,
            xtion_site=tip,
            stiffness=stiffness,
            max_stroke=stroke,
            preload=preload,
        ).register_to_rm(rm)

        # Request high-fidelity telemetry for these components
        base.request(rm.results_manager)
        tip.request(rm.results_manager)
        spring_force.request(rm.results_manager)


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
    mojo_model._user_data = handoff
    handoff.define_spring("pz", box1, box2, mojo_model)
    handoff.define_spring("mz", box1, box2, mojo_model)

    return mojo_model


def runtime(
    mojo_model, runtime_manager, mj_model, mj_data, *args, **kwargs
) -> mojo.MojoModel:
    """Executes the physics loop and flushes telemetry."""
    assert isinstance(mojo_model._user_data, Handoff)

    with runtime_manager as rm:
        rm.results_manager.record_decimation = 1

        # Apply forces defined during generation
        mojo_model._user_data.add_spring_force("pz", rm)
        mojo_model._user_data.add_spring_force("mz", rm)

        for b in mojo_model.mjcf.worldbody.bodies:
            b.request(rm.results_manager)
        mojo_model._user_data.box1_rot.request(rm.results_manager)

        while mj_data.time < 2.0:
            rm.step(mj_model, mj_data)

    return mojo_model


# --8<-- [start:score]
# --8<-- [start:score-handle]
def objective(
    mojo_model: mojo.MojoModel,
    telemetry: Path,
    mj_model: mujoco.MjModel,
    mj_data: mujoco.MjData,
) -> float:
    # --8<-- [end:score-handle]
    """
    Score the trial: Low relative angular velocity (stability) weighted against high translational kinetic energy.
    """
    assert isinstance(mojo_model._user_data, Handoff)
    handoff = mojo_model._user_data

    w1 = handoff.box1.rt_ang_vel(mj_model, mj_data)
    w2 = handoff.box2.rt_ang_vel(mj_model, mj_data)
    omega_score = float(np.linalg.norm(w1 - w2))

    ke1 = handoff.box1.rt_trans_ke(mj_model, mj_data)
    ke2 = handoff.box2.rt_trans_ke(mj_model, mj_data)
    total_ke = ke1 + ke2
    ke_score = 1 / (total_ke + 1e-6)

    # J = 10*Omega + 1*KE_inv
    return (10.0 * omega_score) + (1.0 * ke_score)


# --8<-- [end:score]

# --- Entry Point ---
if __name__ == "__main__":
    workdir = Path("./opt_study").resolve()
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
