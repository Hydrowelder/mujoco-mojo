from pathlib import Path

import duckdb
import mujoco
import numpy as np

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

logger = mojo.utils.get_logger(__name__)

FIXED_CAMERA_NAME = mojo.CameraName("static")
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
        # add box colors
        mojo.Asset(
            materials=[
                box_mat_1 := mojo.Material(
                    name=mojo.MaterialName("box_mat_1"),
                    rgba=mojo.utils.Color.CYAN_500.rgba,
                ),
                box_mat_2 := mojo.Material(
                    name=mojo.MaterialName("box_mat_2"),
                    rgba=mojo.utils.Color.ROSE_500.rgba,
                ),
            ]
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

    # 2. Sample initial separation from a distribution
    mojo_model.sample_dist(
        mojo.TruncatedNormalDistribution(
            name=mojo.DistName("stiffness"), nominal=100, mu=100, sigma=30
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
                material=box_mat_1.name,
                contype=0,
                conaffinity=0,
            )
        ],
        sites=[
            mojo.SiteSphere(
                name=mojo.SiteName("s1"),
                size=0.1,
                pos=mojo.Pos(pos=np.array([-0.49, 0, 0])),
            )
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
                material=box_mat_2.name,
                contype=0,
                conaffinity=0,
            )
        ],
        sites=[
            mojo.SiteSphere(
                name=mojo.SiteName("s2"),
                size=0.1,
                pos=mojo.Pos(pos=np.array([0.49, 0, 0])),
                rgba=mojo.utils.Color.WHITE.invisible,
            )
        ],
        cameras=[
            mojo.Camera(
                name=TRACKING_CAMERA_NAME,
                pos=mojo.Pos(pos=np.array((-0.49, 0, 0))),
                fovy=30,
                mode=mojo.TrackingMode.TARGETBODY,
                target=box1.name,
            ),
        ],
    )

    mojo_model.mjcf.worldbody.bodies.extend([box1, box2])

    mojo_model.mjcf.worldbody.cameras = [
        mojo.Camera(
            name=FIXED_CAMERA_NAME,
            pos=mojo.Pos(pos=np.array((0, 0, 10))),
            fovy=60,
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
    s1 = next(
        s for b in mojo_model.mjcf.worldbody.bodies for s in b.sites if s.name == "s1"
    )
    s2 = next(
        s for b in mojo_model.mjcf.worldbody.bodies for s in b.sites if s.name == "s2"
    )

    with runtime_manager as rm:
        assert rm.results_manager is not None
        rm.results_manager.record_decimation = 100  # only record every 100 steps

        if mojo_model.is_nominal:
            rt.VideoRecorder(
                path=Path("fixed_camera.mp4"), camera_name=FIXED_CAMERA_NAME
            ).setup(mj_model).register_to_rm(rm)

            rt.VideoRecorder(
                path=Path("tracking_camera.mp4"), camera_name=TRACKING_CAMERA_NAME
            ).setup(mj_model).register_to_rm(rm)

        # Create a compression-only spring (Bumper)
        # Rest length is 0.5. If boxes are closer, they push away.
        bumper = rt.PointToPointForce.compression_spring(
            name="box_bumper",
            action_site=s1,
            xtion_site=s2,
            stiffness=float(mojo_model.named["stiffness"]),
            damping=10.0,
            rest_length=0.5,
        ).register_to_rm(rm)

        # Request standard telemetry for the boxes
        s1.request(rm.results_manager)
        s2.request(rm.results_manager)
        bumper.request(rm.results_manager)
        for b in mojo_model.mjcf.worldbody.bodies:
            b.request(rm.results_manager)

        # record t = 0
        rm.results_manager.record(mj_model, mj_data)

        # Run for 2 seconds
        while mj_data.time < 2.0:
            rm.step(mj_model, mj_data)

    return f"Trial {mojo_model.trial_num} complete."


def post_process(workdir: Path):
    tn = 0
    db_path = workdir / "trials" / f"trial_{tn}" / "telemetry.duckdb"
    conn = duckdb.connect(db_path)

    df = conn.execute("SELECT * FROM result").pl()
    # _df["box_bumper"]

    print(df)
    print(df["box_bumper_force_m"])
    print(df.columns)
    # breakpoint()


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
