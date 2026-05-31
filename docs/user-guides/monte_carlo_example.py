# --8<-- [start:imports]
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import Field

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

logger = mojo.utils.get_logger(__name__)
# --8<-- [end:imports]

# --8<-- [start:handoff]
FIXED_CAMERA_NAME = mojo.CameraName("static")


class Handoff(mojo.UserData):
    """
    User-defined interconnect between the generator and runtime function.
    Retains MJCF definitions for use in the physics loop.
    """

    box1_rot: mojo.AnySite
    springs: dict[
        Literal["pz", "mz"],
        tuple[mojo.AnySite, mojo.AnySite, mojo.NamedValue, mojo.NamedValue],
    ] = Field(default_factory=dict)

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

        # --8<-- [start:sampling]
        # Perform random draws tied to the model seed
        stiffness = mojo_model.sample_dist(
            mojo.TruncatedNormalDistribution(
                name=mojo.DistName(f"{loc}_stiffness"),
                nominal=100,
                mu=100,
                sigma=20,
                low=0,
            )
        ).squeeze()

        stroke = mojo_model.sample_dist(
            mojo.TruncatedNormalDistribution(
                name=mojo.DistName(f"{loc}_stroke"),
                nominal=(nom := 1),
                mu=nom,
                sigma=nom * 0.1,
                low=nom * 0.8,
                high=nom * 1.2,
            )
        ).squeeze()
        # --8<-- [end:sampling]

        self.springs.update({loc: (base, tip, stiffness, stroke)})

    def add_spring_force(self, loc: Literal["pz", "mz"], rm: rt.RuntimeManager):
        assert rm.signal_manager is not None
        base, tip, stiffness, stroke = self.springs[loc]

        # --8<-- [start:forces]
        spring_force = rt.PointToPointForce.stroke_compression_spring(
            name=f"{loc}_spring",
            action_site=base,
            xtion_site=tip,
            stiffness=float(stiffness),
            max_stroke=float(stroke),
            preload=1000 if loc == "pz" else 750,
        ).register_to_rm(rm)

        base.request(rm.signal_manager)
        tip.request(rm.signal_manager)
        spring_force.request(rm.signal_manager)
        # --8<-- [end:forces]


# --8<-- [end:handoff]


# --8<-- [start:generate]
# --8<-- [start:generate-handle]
def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Generates the MJCF model and samples distributions."""
    # --8<-- [end:generate-handle]
    skybox_folder = (mojo.DepPath() / "textures" / "stars").resolve()

    # --8<-- [start:assets]
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

    # Handle skybox if in nominal mode
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
    # --8<-- [end:assets]

    # --8<-- [start:worldbody]
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
    # --8<-- [end:worldbody]

    mojo_model.mjcf.options = [
        mojo.Option(timestep=0.001, gravity=np.asarray((0, 0, 0)))
    ]
    mojo_model.mjcf.visuals = [
        mojo.Visual(
            map=mojo.VisualMap(force=4),
            scale=mojo.VisualScale(forcewidth=0.1),
        )
    ]

    mojo_model.mjcf.worldbody.cameras = [
        mojo.Camera(
            name=FIXED_CAMERA_NAME,
            pose=mojo.PoseEuler(
                pos=np.asarray((0, -10, 0)),
                euler=np.asarray((90, 0, 0)),
            ),
            fovy=30,
        ),
    ]

    # --8<-- [start:bodies]
    # Create two boxes using the walrus operator for immediate referencing
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
    # --8<-- [end:bodies]

    box1.sites.append(
        box1_rot_site := mojo.SiteSphere(
            name=mojo.SiteName("box1_rot_site"),
            size=0.2,
            pose=mojo.PoseEuler(euler=np.asarray((45, 45, 45))),
            rgba=mojo.utils.Color.FUCHSIA_500.rgba,
        )
    )

    # --8<-- [start:generate-finalizing]
    # Pack and execute handoff
    handoff = Handoff(box1_rot=box1_rot_site)
    mojo_model.user_data = handoff
    handoff.define_spring("pz", box1, box2, mojo_model)
    handoff.define_spring("mz", box1, box2, mojo_model)

    return mojo_model


# --8<-- [end:generate-finalizing]

# --8<-- [end:generate]


# --8<-- [start:runtime]
# --8<-- [start:runtime-handle]
def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    """Executes the physics simulation."""
    # --8<-- [end:runtime-handle]

    with runtime_manager as rm:
        handoff = mojo_model.get_user_data(Handoff)
        assert mojo_model.mjcf.worldbody

        # --8<-- [start:video]
        if mojo_model.is_nominal:  # Only record the first trial
            rt.VideoRecorder(
                path=Path("runtime-anim.gif"),
                camera_name=FIXED_CAMERA_NAME,
                show_loads=True,
            ).setup(state).register_to_rm(rm)
        # --8<-- [end:video]

        # Register forces from our handoff data
        handoff.add_spring_force("pz", rm)
        handoff.add_spring_force("mz", rm)

        # --8<-- [start:requests]
        # Request telemetry for bodies and sites
        if rm.signal_manager:
            rm.signal_manager.record_decimation = 10  # Only record every 10 steps
            for b in mojo_model.mjcf.worldbody.walk_bodies():
                b.request(
                    rm.signal_manager,
                    attrs=["ke_total", "ke_rot", "xpos", "xvelp", "xvelr"],
                )
            handoff.box1_rot.request(rm.signal_manager)
        # --8<-- [end:requests]

        # --8<-- [start:stepping]
        # Step until 2.0 seconds
        while state.data.time < 2.0:
            rm.step(state)
        # --8<-- [end:stepping]

    return mojo_model


# --8<-- [end:runtime]

# --8<-- [start:main]
if __name__ == "__main__":
    mojo.utils.setup_logger()
    workdir = Path(__file__).parent / "monte_carlo_study"

    runner = mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
        workdir=workdir,
        config=mojo.utils.MonteCarloConfig(n_trial=10, n_proc=1),
    )

    runner.run(clean_workdir=True)
# --8<-- [end:main]
