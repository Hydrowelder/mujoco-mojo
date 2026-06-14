import numpy as np

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

logger = mojo.utils.get_logger(__name__)

MESHES_DIR = mojo.DepPath(__file__).parent.parent.parent / "meshes"

# ── tune these to compare contact algorithms and compliance ───────────────────
ALGORITHM = mojo.ProximityType.VERTEX_TO_FACE
# ALGORITHM = mojo.ProximityType.CONVEX_HULL       # fast, convex approximation
# ALGORITHM = mojo.ProximityType.SPHERE_TO_SPHERE  # broadphase only, least precise
# ALGORITHM = mojo.ProximityType.FACE_TO_FACE      # most precise, slowest

STIFFNESS = 30_000.0  # N/m — spring constant k in F = k*delta + c*v_close
DAMPING = 300.0  # N·s/m — damping c, only on closing contact
CLEARANCE = 0.01  # m — contact zone begins this far before surface contact

SIM_DURATION = 0.5  # seconds
TIMESTEP = 0.002  # seconds
# ─────────────────────────────────────────────────────────────────────────────


class Handoff(mojo.UserData):
    ball_geom: mojo.GeomMesh
    cup_geom: mojo.GeomMesh


def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    ball_mesh = mojo.Mesh(
        name=mojo.MeshName("ball_mesh"),
        file=MESHES_DIR / "ball.stl",
        scale=np.ones(3) * 0.5,
    )
    cup_mesh = mojo.Mesh(
        name=mojo.MeshName("cup_mesh"),
        file=MESHES_DIR / "cup.stl",
    )
    ball_mesh_name = ball_mesh.name
    cup_mesh_name = cup_mesh.name
    assert ball_mesh_name and cup_mesh_name

    mojo_model.mjcf.assets = [
        mojo.Asset(meshes=[ball_mesh, cup_mesh]),
    ]

    mojo_model.mjcf.options = [
        mojo.Option(
            timestep=TIMESTEP,
            gravity=np.array([0.0, 0.0, -9.81]),
        )
    ]

    # cup is fixed to world (no joint)
    cup_geom = mojo.GeomMesh(
        name=mojo.GeomName("cup_geom"),
        mesh=cup_mesh_name,
        rgba=mojo.utils.Color.CYAN_500.with_alpha(0.4),
        contype=0,
        conaffinity=0,
    )
    cup_body = mojo.Body(
        name=mojo.BodyName("cup"),
        pose=mojo.PoseQuat(pos=np.array([0.0, 0.0, 0.0])),
        geoms=[cup_geom],
    )

    # ball starts above the cup with a free joint
    ball_geom = mojo.GeomMesh(
        name=mojo.GeomName("ball_geom"),
        mesh=ball_mesh_name,
        rgba=mojo.utils.Color.ROSE_500.rgba,
        contype=1,
        conaffinity=1,
    )
    ball_body = mojo.Body(
        name=mojo.BodyName("ball"),
        pose=mojo.PoseQuat(pos=np.array([0.0, 0.0, 0.8])),
        freejoints=[mojo.FreeJoint()],
        geoms=[ball_geom],
    )

    # ground plane catches the ball if it misses or bounces out
    floor = mojo.GeomPlane(
        name=mojo.GeomName("floor"),
        size=np.array([5.0, 5.0, 0.1]),
        pose=mojo.PoseQuat(pos=np.array([0.0, 0.0, -0.5])),
        rgba=mojo.utils.Color.SLATE_700.with_alpha(0.3),
        contype=1,
        conaffinity=1,
    )

    mojo_model.mjcf.worldbody = mojo.WorldBody(
        geoms=[floor],
        bodies=[cup_body, ball_body],
        cameras=[
            mojo.Camera(
                name=mojo.CameraName("overview"),
                projection=mojo.CameraProjection.ORTHOGRAPHIC,
                pose=mojo.PoseEuler(
                    pos=np.array([0.0, -1.0, 0.5]),
                    euler=np.array([90.0, 0.0, 0.0]),
                ),
                fovy=5,
            ),
        ],
    )

    mojo_model.user_data = Handoff(ball_geom=ball_geom, cup_geom=cup_geom)
    return mojo_model


def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    handoff = mojo_model.get_user_data(Handoff)

    prox = mojo.utils.Proximity(
        geom_1=handoff.ball_geom,
        geom_2=handoff.cup_geom,
        dist_max=1.5,
        algorithm=ALGORITHM,
    ).register_to_rm(runtime_manager)

    with runtime_manager as rm:
        rt.VideoRecorder(
            path=mojo_model.trial_dir / "overview.mp4",
            camera_name=mojo.CameraName("overview"),
            show_loads=True,
            show_proximities=True,
        ).setup(state).register_to_rm(rm)

        if rm.signal_manager:
            prox.request(rm.signal_manager, channels=["dist", "prox_type"])
            handoff.ball_geom.request(rm.signal_manager)

        while state.data.time < SIM_DURATION:
            rm.step(state)

    return mojo_model
