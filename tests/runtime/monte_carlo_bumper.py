from pathlib import Path

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


def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Generates two boxes at varying distances."""
    # Download this skybox from here: https://www.david-gable.com/work/photography/Space/Star-Skybox/p1/
    skybox_folder = (mojo.DepPath() / "textures" / "stars").resolve()

    # 1. Setup Assets
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

    # 2. Sample initial separation from a distribution
    mojo_model.sample_dist(
        mojo.TruncatedNormalDistribution(
            name=mojo.DistName("pz_stiffness"), nominal=50, mu=50, sigma=15, low=0
        )
    ).squeeze()
    mojo_model.sample_dist(
        mojo.TruncatedNormalDistribution(
            name=mojo.DistName("mz_stiffness"), nominal=50, mu=50, sigma=15, low=0
        )
    ).squeeze()
    mojo_model.sample_dist(
        mojo.TruncatedNormalDistribution(
            name=mojo.DistName("pz_stroke"),
            nominal=0.25,
            mu=0.25,
            sigma=0.1,
            low=0.2,
            high=0.3,
        )
    ).squeeze()
    mojo_model.sample_dist(
        mojo.TruncatedNormalDistribution(
            name=mojo.DistName("mz_stroke"),
            nominal=0.25,
            mu=0.25,
            sigma=0.1,
            low=0.2,
            high=0.3,
        )
    ).squeeze()

    # 3. Create two boxes with sites for the spring
    # Box 1 at origin
    box1 = mojo.Body(
        name=mojo.BodyName("box1"),
        pos=mojo.Pos(pos=np.array([0.5, 0, 0])),
        freejoints=[mojo.FreeJoint()],
        geoms=[
            mojo.GeomBox(
                name=mojo.GeomName("g1"),
                size=np.array([0.5, 0.5, 0.5]),
                rgba=mojo.utils.Color.CYAN_500.with_alpha(0.5),
                contype=0,
                conaffinity=0,
            )
        ],
        sites=[
            mojo.SiteSphere(
                name=mojo.SiteName("pz_spring_tip_site"),
                size=0.1,
                pos=mojo.Pos(pos=np.array([-0.4, 0, 0.5])),
                rgba=mojo.utils.Color.BLUE_500.rgba,
            ),
            mojo.SiteSphere(
                name=mojo.SiteName("mz_spring_tip_site"),
                size=0.1,
                pos=mojo.Pos(pos=np.array([-0.4, 0, -0.5])),
                rgba=mojo.utils.Color.BLUE_500.rgba,
            ),
        ],
    )

    # Box 2
    box2 = mojo.Body(
        name=mojo.BodyName("box2"),
        pos=mojo.Pos(pos=np.array([-0.5, 0, 0])),
        freejoints=[mojo.FreeJoint()],
        geoms=[
            mojo.GeomBox(
                name=mojo.GeomName("g2"),
                size=np.array([0.5, 0.5, 0.5]),
                rgba=mojo.utils.Color.ROSE_500.with_alpha(0.5),
                contype=0,
                conaffinity=0,
            )
        ],
        sites=[
            mojo.SiteSphere(
                name=mojo.SiteName("pz_spring_base_site"),
                size=0.1,
                pos=mojo.Pos(pos=np.array([0.4, 0, 0.5])),
                rgba=mojo.utils.Color.RED_500.with_alpha(0.2),
            ),
            mojo.SiteSphere(
                name=mojo.SiteName("mz_spring_base_site"),
                size=0.1,
                pos=mojo.Pos(pos=np.array([0.4, 0, -0.5])),
                rgba=mojo.utils.Color.RED_500.with_alpha(0.2),
            ),
        ],
        cameras=[
            mojo.Camera(
                name=BOX_CAMERA_NAME,
                pos=mojo.Pos(pos=np.array((0.4, 0, 0))),
                orientation=mojo.Euler(euler=np.array((90, -90, 0))),
                fovy=120,
            ),
        ],
    )

    mojo_model.mjcf.worldbody.bodies.extend([box1, box2])

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
            target=box1.name,
        ),
    ]
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
    pz_spring_tip = next(
        s
        for b in mojo_model.mjcf.worldbody.bodies
        for s in b.sites
        if s.name == "pz_spring_tip_site"
    )
    pz_spring_base = next(
        s
        for b in mojo_model.mjcf.worldbody.bodies
        for s in b.sites
        if s.name == "pz_spring_base_site"
    )
    mz_spring_tip = next(
        s
        for b in mojo_model.mjcf.worldbody.bodies
        for s in b.sites
        if s.name == "mz_spring_tip_site"
    )
    mz_spring_base = next(
        s
        for b in mojo_model.mjcf.worldbody.bodies
        for s in b.sites
        if s.name == "mz_spring_base_site"
    )

    with runtime_manager as rm:
        assert rm.results_manager is not None
        rm.results_manager.record_decimation = 1

        if mojo_model.is_nominal:
            rt.VideoRecorder(
                path=Path("fixed_camera.mp4"),
                camera_name=FIXED_CAMERA_NAME,
                show_force=True,
            ).setup(mj_model).register_to_rm(rm)

            rt.VideoRecorder(
                path=Path("tracking_camera.mp4"),
                camera_name=TRACKING_CAMERA_NAME,
                show_force=True,
            ).setup(mj_model).register_to_rm(rm)

            rt.VideoRecorder(
                path=Path("box_camera.mp4"),
                camera_name=BOX_CAMERA_NAME,
                show_force=False,
            ).setup(mj_model).register_to_rm(rm)

        # Create a compression-only spring (Bumper)
        # Rest length is 0.5. If boxes are closer, they push away.
        pz_bumper = rt.PointToPointForce.stroke_compression_spring(
            name="pz_box_bumper",
            action_site=pz_spring_base,  # red box
            xtion_site=pz_spring_tip,  # blue box
            stiffness=float(mojo_model.named["pz_stiffness"]),
            max_stroke=float(mojo_model.named["pz_stroke"]),
            preload=25,
        ).register_to_rm(rm)
        mz_bumper = rt.PointToPointForce.stroke_compression_spring(
            name="mz_box_bumper",
            action_site=mz_spring_base,  # red box
            xtion_site=mz_spring_tip,  # blue box
            stiffness=float(mojo_model.named["mz_stiffness"]),
            max_stroke=float(mojo_model.named["mz_stroke"]),
            preload=24,
        ).register_to_rm(rm)

        # Request standard telemetry for the boxes
        pz_spring_tip.request(rm.results_manager)
        pz_spring_base.request(rm.results_manager)
        mz_spring_tip.request(rm.results_manager)
        mz_spring_base.request(rm.results_manager)
        pz_bumper.request(rm.results_manager)
        mz_bumper.request(rm.results_manager)
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
    df = df.with_columns(
        dist=(
            (pl.col("pz_spring_tip_site_xpos_x") - pl.col("pz_spring_base_site_xpos_x"))
            ** 2
            + (
                pl.col("pz_spring_tip_site_xpos_y")
                - pl.col("pz_spring_base_site_xpos_y")
            )
            ** 2
            + (
                pl.col("pz_spring_tip_site_xpos_z")
                - pl.col("pz_spring_base_site_xpos_z")
            )
            ** 2
        ).sqrt()
    )
    r0 = df["dist"][0]
    df = df.with_columns(stroke=pl.col("dist") - r0)

    def plot_spring_force():
        active_df = df.filter(pl.col("stroke") <= 0.5)
        # breakpoint()

        plt.figure(figsize=(10, 6))
        plt.plot(
            active_df["stroke"],
            active_df["pz_box_bumper_force_m"],
            label="Spring Force",
            color=mojo.utils.Color.CYAN_500,
            linewidth=2,
        )

        # Formatting
        plt.title(f"Force vs. Stroke (Trial {tn})", fontsize=14)
        plt.xlabel("Stroke [m] (extension > 0, compression < 0)", fontsize=12)
        plt.ylabel("Force Magnitude [N]", fontsize=12)
        plt.grid(True, linestyle="--", alpha=0.7)
        plt.legend()
        plt.tight_layout()

        # Save the plot
        plot_path = workdir / "force_stroke_plot.png"
        plt.savefig(plot_path)

    plot_spring_force()


if __name__ == "__main__":
    from pathlib import Path

    mojo.utils.setup_logger()

    workdir = Path(__file__).parent / "mc_bumper_test"
    # Run the Monte Carlo
    runner = mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
        workdir=workdir,
        config=mojo.utils.MonteCarloConfig(n_trial=1, n_proc=1),
    )

    results, had_fails = runner.run(
        resume=False, clean_workdir=True, cleanup_delay=-1, trial_ids=[0]
    )

    if not had_fails and runner.runtime is not None:
        post_process(workdir=workdir)
    print(f"Finished with {had_fails=}")
