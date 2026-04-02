from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import duckdb
import mujoco
import numpy as np
import polars as pl

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

    springs: dict[
        Literal["pz", "mz"],
        tuple[mojo.Site, mojo.Site, mojo.NamedValue, mojo.NamedValue],
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
                pos=mojo.Pos(pos=np.array([0.4, 0, mult * 0.5])),
                rgba=mojo.utils.Color.RED_500.rgba,
            )
        )
        box2.sites.append(
            tip := mojo.SiteSphere(
                name=mojo.SiteName(f"{loc}_spring_tip_site"),
                size=0.1,
                pos=mojo.Pos(pos=np.array([-0.4, 0, mult * 0.5])),
                rgba=mojo.utils.Color.BLUE_500.rgba,
            )
        )

        # perform random draws
        stiffness = mojo_model.sample_dist(
            mojo.TruncatedNormalDistribution(
                name=mojo.DistName(f"{loc}_stiffness"),
                nominal=50,
                mu=50,
                sigma=15,
                low=0,
            )
        ).squeeze()
        stroke = mojo_model.sample_dist(
            mojo.TruncatedNormalDistribution(
                name=mojo.DistName(f"{loc}_stroke"),
                nominal=0.25,
                mu=0.25,
                sigma=0.1,
                low=0.2,
                high=0.3,
            )
        ).squeeze()

        self.springs.update({loc: (base, tip, stiffness, stroke)})

    def add_spring_force(self, loc: Literal["pz", "mz"], rm: rt.RuntimeManager):
        assert rm.results_manager is not None
        base, tip, stiffness, stroke = self.springs[loc]

        spring_force = rt.PointToPointForce.stroke_compression_spring(
            name=f"{loc}_spring",
            action_site=base,  # red box
            xtion_site=tip,  # blue box
            stiffness=float(stiffness),
            max_stroke=float(stroke),
            preload=25 if loc == "pz" else 24,
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
                    texrepeat=np.array((1, 1)),
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
                size=np.array([0, 0, 0.1]),
                pos=mojo.Pos(pos=np.array((0, 0, -5))),
                material=grid_mat.name,
                contype=0,
                conaffinity=0,
            ),
        ]
    )
    mojo_model.mjcf.options = [
        mojo.Option(
            timestep=0.001,
            gravity=np.array((0, 0, 0)),
        )
    ]
    mojo_model.mjcf.visuals = [
        mojo.Visual(
            map=mojo.VisualMap(force=100),
            scale=mojo.VisualScale(forcewidth=0.1),
        )
    ]

    # create two boxes with sites for the springs
    mojo_model.mjcf.worldbody.bodies.extend(
        [  # Box 1
            box1 := mojo.Body(
                name=mojo.BodyName("box1"),
                pos=mojo.Pos(pos=np.array([-0.5, 0, 0])),
                freejoints=[mojo.FreeJoint()],
                geoms=[
                    mojo.GeomBox(
                        name=mojo.GeomName("g1"),
                        size=np.array([0.5, 0.5, 0.5]),
                        rgba=mojo.utils.Color.ROSE_500.with_alpha(0.5),
                        contype=0,
                        conaffinity=0,
                    )
                ],
                cameras=[
                    mojo.Camera(
                        name=BOX_CAMERA_NAME,
                        pos=mojo.Pos(pos=np.array((0.4, 0, 0))),
                        orientation=mojo.Euler(euler=np.array((90, -90, 0))),
                        fovy=120,
                    ),
                ],
            ),
            # Box 2
            box2 := mojo.Body(
                name=mojo.BodyName("box2"),
                pos=mojo.Pos(pos=np.array([0.5, 0, 0])),
                freejoints=[mojo.FreeJoint()],
                geoms=[
                    mojo.GeomBox(
                        name=mojo.GeomName("g2"),
                        size=np.array([0.5, 0.5, 0.5]),
                        rgba=mojo.utils.Color.CYAN_500.with_alpha(0.5),
                        contype=0,
                        conaffinity=0,
                    )
                ],
            ),
        ]
    )

    mojo_model.mjcf.worldbody.cameras = [
        mojo.Camera(
            name=FIXED_CAMERA_NAME,
            pos=mojo.Pos(pos=np.array((0, -10, 0))),
            orientation=mojo.Euler(euler=np.array((90, 0, 0))),
            fovy=30,
        ),
        mojo.Camera(
            name=TRACKING_CAMERA_NAME,
            pos=mojo.Pos(pos=np.array((0, -10, 0))),
            fovy=30,
            mode=mojo.TrackingMode.TARGETBODY,
            target=box2.name,
        ),
    ]

    # add handoff data
    handoff = Handoff()
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
):
    """Executes the spring repulsion simulation."""
    # Identify our sites from the generated model
    # Note: We can find them by name in the worldbody
    assert mojo_model.mjcf.worldbody is not None
    assert isinstance(mojo_model._user_data, Handoff)

    with runtime_manager as rm:
        assert rm.results_manager is not None
        rm.results_manager.record_decimation = 1

        if mojo_model.is_nominal:
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

        # Run for 2 seconds
        while mj_data.time < 2.0:
            rm.step(mj_model, mj_data)

    return f"Trial {mojo_model.trial_num} complete."


def post_process(workdir: Path):
    import matplotlib.pyplot as plt

    tn = 0
    db_path = workdir / "trials" / f"trial_{tn}" / "telemetry.duckdb"
    conn = duckdb.connect(db_path)

    df = conn.execute("SELECT * FROM result").pl()

    # calculate distances and strokes for both springs
    for loc in ["pz", "mz"]:
        t_name = f"{loc}_spring_tip_site"
        b_name = f"{loc}_spring_base_site"

        # Unique column names for this location
        dist_col = f"{loc}_dist"
        stroke_col = f"{loc}_stroke"

        df = df.with_columns(
            **{
                dist_col: (
                    (pl.col(f"{t_name}_xpos_x") - pl.col(f"{b_name}_xpos_x")).pow(2)
                    + (pl.col(f"{t_name}_xpos_y") - pl.col(f"{b_name}_xpos_y")).pow(2)
                    + (pl.col(f"{t_name}_xpos_z") - pl.col(f"{b_name}_xpos_z")).pow(2)
                ).sqrt()
            }
        )

        # Calculate stroke relative to start of trial
        r0 = df[dist_col][0]
        df = df.with_columns(**{stroke_col: pl.col(dist_col) - r0})

    # plotting
    plt.figure(figsize=(10, 6))

    styles = {
        "pz": {"color": mojo.utils.Color.CYAN_500, "label": "PZ Spring"},
        "mz": {"color": mojo.utils.Color.ROSE_500, "label": "MZ Spring"},
    }

    for loc in ["pz", "mz"]:
        stroke_col = f"{loc}_stroke"
        # Match name from add_spring_force: f"{loc}_spring"
        force_col = f"{loc}_spring_force_m"

        # Filter for active stroke range (before separation)
        active_df = df.filter(pl.col(stroke_col) <= 0.5)

        plt.plot(
            active_df[stroke_col],
            active_df[force_col],
            label=styles[loc]["label"],
            color=styles[loc]["color"],
            linewidth=2,
            alpha=0.8,
        )

    # formatting
    plt.title(f"Force vs. Stroke Comparison (Trial {tn})", fontsize=14)
    plt.xlabel("Stroke [m] (extension > 0)", fontsize=12)
    plt.ylabel("Force Magnitude [N]", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.legend()
    plt.tight_layout()

    # cleanup
    plot_path = workdir / "force_stroke_plot.png"
    plt.savefig(plot_path)
    plt.close()


if __name__ == "__main__":
    from pathlib import Path

    mojo.utils.setup_logger()

    workdir = Path(__file__).parent / "mc_bumper_test_2"
    # Run the Monte Carlo
    runner = mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
        workdir=workdir,
        config=mojo.utils.MonteCarloConfig(n_trial=1, n_proc=1),
    )

    # results, had_fails = runner.run(
    #     resume=False, clean_workdir=True, cleanup_delay=-1, trial_ids=[0]
    # )
    results, had_fails = runner.run(resume=False, clean_workdir=True, cleanup_delay=-1)

    if not had_fails and runner.runtime is not None:
        post_process(workdir=workdir)
    print(f"Finished with {had_fails=}")
