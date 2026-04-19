from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import mujoco
import numpy as np
import optuna

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

logger = mojo.utils.get_logger(__name__)

FIXED_CAMERA_NAME = mojo.CameraName("static")
BOX_CAMERA_NAME = mojo.CameraName("box_camera")
TRACKING_CAMERA_NAME = mojo.CameraName("tracker_cam")


@dataclass
class Handoff:
    """
    This class exists to serve as a user defined interconnect between the generator and runtime function.

    It is here to allow encapsulation for defining MJCF elements, while retaining the simple ability to later use those definitions in the runtime.
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

        # perform random draws
        stiffness = mojo_model.design_float(
            name=f"{loc}_stiffness",
            default=100,
            low=50,
            high=200,
        )

        stroke = mojo_model.design_float(
            name=f"{loc}_stroke",
            default=(nom := 1),
            low=nom * 0.8,
            high=nom * 1.2,
        )

        preload = mojo_model.design_float(
            name=f"{loc}_preload",
            default=(nom := 1000 if loc == "pz" else 750),
            low=nom * 0.8,
            high=nom * 1.2,
        )

        self.springs.update({loc: (base, tip, stiffness, stroke, preload)})

    def add_spring_force(self, loc: Literal["pz", "mz"], rm: rt.RuntimeManager):
        assert rm.results_manager is not None
        base, tip, stiffness, stroke, preload = self.springs[loc]

        spring_force = rt.PointToPointForce.stroke_compression_spring(
            name=f"{loc}_spring",
            action_site=base,  # red box
            xtion_site=tip,  # blue box
            stiffness=stiffness,
            max_stroke=stroke,
            preload=preload,
        ).register_to_rm(rm)

        base.request(rm.results_manager)
        tip.request(rm.results_manager)
        spring_force.request(rm.results_manager)


def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Generates two boxes at varying distances."""
    # Download this skybox from here: https://www.david-gable.com/work/photography/Space/Star-Skybox/p1/
    skybox_folder = (mojo.DepPath() / "textures" / "stars").resolve()

    # configure simulation
    mojo_model.mjcf.assets = [
        # add a checkerboard
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

    # add a skybox
    if mojo_model.is_nominal:
        mojo_model.mjcf.assets.append(
            mojo.Asset(
                textures=[
                    mojo.Texture(
                        name=mojo.TextureName("skybox_texture_colors"),
                        type=mojo.TextureType.SKYBOX,
                        fileback=skybox_folder / "nz.png",
                        filedown=skybox_folder / "ny.png",
                        filefront=skybox_folder / "pz.png",
                        fileleft=skybox_folder / "nx.png",
                        fileright=skybox_folder / "px.png",
                        fileup=skybox_folder / "py.png",
                    )
                ]
            ),
        )

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
            timestep=0.001,
            gravity=np.asarray((0, 0, 0)),
        )
    ]
    mojo_model.mjcf.visuals = [
        mojo.Visual(
            map=mojo.VisualMap(force=4),
            scale=mojo.VisualScale(forcewidth=0.1),
        )
    ]

    # create two boxes with sites for the springs
    mojo_model.mjcf.worldbody.bodies.extend(
        [  # Box 1
            box1 := mojo.Body(
                name=mojo.BodyName("box1"),
                pose=mojo.PoseQuat(pos=np.asarray([-0.5, 0, 0])),
                freejoints=[mojo.FreeJoint()],
                geoms=[
                    mojo.GeomBox(
                        name=mojo.GeomName("g1"),
                        size=np.asarray([0.5, 0.5, 0.5]),
                        rgba=mojo.utils.Color.ROSE_500.with_alpha(0.5),
                        contype=0,
                        conaffinity=0,
                    )
                ],
                cameras=[
                    mojo.Camera(
                        name=BOX_CAMERA_NAME,
                        pose=mojo.PoseEuler(
                            pos=np.asarray((0.4, 0, 0)),
                            euler=np.asarray(
                                (90, -90, 0),
                            ),
                        ),
                        fovy=120,
                    ),
                ],
            ),
            # Box 2
            box2 := mojo.Body(
                name=mojo.BodyName("box2"),
                pose=mojo.PoseQuat(pos=np.asarray([0.5, 0, 0])),
                freejoints=[mojo.FreeJoint()],
                geoms=[
                    mojo.GeomBox(
                        name=mojo.GeomName("g2"),
                        size=np.asarray([0.5, 0.5, 0.5]),
                        # rgba=mojo.utils.Color.CYAN_500.with_alpha(0.5),
                        rgba=mojo.utils.Color.CYAN_500.with_alpha(0.5),
                        contype=0,
                        conaffinity=0,
                    )
                ],
            ),
        ]
    )

    box1.sites.append(
        box1_rot_site := mojo.SiteSphere(
            name=mojo.SiteName("box1_rot_site"),
            size=0.2,
            pose=mojo.PoseEuler(
                euler=np.asarray((45, 45, 45)),
                angle=mojo.Angle.DEGREE,
                eulerseq=mojo.EulerSeq.xyz,
            ),
            rgba=mojo.utils.Color.FUCHSIA_500.rgba,
        )
    )

    mojo_model.mjcf.worldbody.cameras = [
        mojo.Camera(
            name=FIXED_CAMERA_NAME,
            pose=mojo.PoseEuler(
                pos=np.asarray((0, -10, 0)),
                euler=np.asarray((90, 0, 0)),
            ),
            fovy=30,
        ),
        mojo.Camera(
            name=TRACKING_CAMERA_NAME,
            pose=mojo.PoseQuat(
                pos=np.asarray((0, -10, 0)),
            ),
            fovy=30,
            mode=mojo.TrackingMode.TARGETBODY,
            target=box2.name,
        ),
    ]

    # add handoff data
    handoff = Handoff(box1=box1, box2=box2, box1_rot=box1_rot_site)
    mojo_model._user_data = handoff
    handoff.define_spring("pz", box1, box2, mojo_model)
    handoff.define_spring("mz", box1, box2, mojo_model)

    return mojo_model


def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    mj_model: mujoco.MjModel,
    mj_data: mujoco.MjData,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    """Executes the spring repulsion simulation."""
    # Identify our sites from the generated model
    # Note: We can find them by name in the worldbody
    assert mojo_model.mjcf.worldbody is not None
    assert isinstance(mojo_model._user_data, Handoff)

    with runtime_manager as rm:
        assert rm.results_manager is not None
        rm.results_manager.record_decimation = 1

        if mojo_model.is_nominal and False:
            rt.VideoRecorder(
                path=Path("fixed_camera.mp4"),
                camera_name=FIXED_CAMERA_NAME,
                show_loads=True,
                show_net_force=True,
            ).setup(mj_model).register_to_rm(rm)

            rt.VideoRecorder(
                path=Path("tracking_camera.mp4"),
                camera_name=TRACKING_CAMERA_NAME,
                show_loads=True,
            ).setup(mj_model).register_to_rm(rm)

            rt.VideoRecorder(
                path=Path("box_camera.mp4"),
                camera_name=BOX_CAMERA_NAME,
                show_net_force=False,
            ).setup(mj_model).register_to_rm(rm)

        # Create compression springs
        mojo_model._user_data.add_spring_force("pz", rm)
        mojo_model._user_data.add_spring_force("mz", rm)

        for b in mojo_model.mjcf.worldbody.bodies:
            b.request(rm.results_manager)

        mojo_model._user_data.box1_rot.request(rm.results_manager)

        # Run for 2 seconds
        while mj_data.time < 2.0:
            rm.step(mj_model, mj_data)

    return mojo_model


def objective(
    mojo_model: mojo.MojoModel,
    telemetry: Path,
    mj_model: mujoco.MjModel,
    mj_data: mujoco.MjData,
) -> float:
    """Optimize the relative angular velocity to be low but the translational kinetic energy to be high."""
    assert isinstance(mojo_model._user_data, Handoff)
    handoff = mojo_model._user_data

    w1 = handoff.box1.rt_ang_vel(mj_model, mj_data)
    w2 = handoff.box2.rt_ang_vel(mj_model, mj_data)
    omega_score = float(np.linalg.norm(w1 - w2))

    ke1 = handoff.box1.rt_trans_ke(mj_model, mj_data)
    ke2 = handoff.box2.rt_trans_ke(mj_model, mj_data)
    total_ke = ke1 + ke2
    ke_score = 1 / (total_ke + 1e-6)  # add to prevent divide by zero

    STABILITY_WEIGHT = 10.0
    ENERGY_WEIGHT = 1.0

    return (STABILITY_WEIGHT * omega_score) + (ENERGY_WEIGHT * ke_score)


WORKDIR = (Path(__file__).parent / "mc_bumper_optimize").resolve()


def run_dashboard():
    import optuna_dashboard

    storage_url = f"sqlite:///{WORKDIR / 'study.db'}"

    print("--- Launching Mojo Dojo Post-Processor ---")
    print(f"Database: {storage_url}")
    print("Access locally at: http://localhost:8081")

    # We host on 0.0.0.0 so the SSH tunnel can grab it
    optuna_dashboard.run_server(storage_url, host="0.0.0.0", port=8002)


def run_study():
    mojo.utils.setup_logger()
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    runner = mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
        objective=objective,
        workdir=WORKDIR,
        config=mojo.utils.OptimizerConfig(
            n_trial=20,
            n_proc=4,
            study_name="stabilize_box",
            direction="minimize",
            sampler="tpe",
            storage=f"sqlite:///{WORKDIR / 'study.db'}",
        ),
        seed=42,
    )

    logger.info("Starting Optimization Study...")
    had_fails = runner.run(resume=False, clean_workdir=True, cleanup_delay=-1)
    print(f"Optimization finished with {had_fails=}. Results saved to {WORKDIR}.")


if __name__ == "__main__":
    # run_dashboard()
    run_study()
