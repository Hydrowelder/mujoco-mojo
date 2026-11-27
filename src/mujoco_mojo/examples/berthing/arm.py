"""The robotic arm: a shoulder, two booms, an elbow, a wrist and an end effector at each end. One end is latched onto the station and the other reaches for the visitor."""

from __future__ import annotations

from typing import Literal, Self

import mink
import mujoco
import numpy as np
from pydantic import PrivateAttr

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

from .end_effector import END_EFFECTOR, EndEffector
from .fixture import GrappleFixture
from .shapes import ARM_CONAFFINITY, ARM_CONTYPE, CylinderInput, lying_along
from .visitor import VISITOR

US = mojo.UnitSystem.si()

# housings are colored by the axis they turn about: red X (roll), green Y (pitch), blue Z (yaw)
ROLL_COLOR = mojo.utils.Color.RED_500.rgba
PITCH_COLOR = mojo.utils.Color.GREEN_500.rgba
YAW_COLOR = mojo.utils.Color.BLUE_500.rgba

# settings for `Arm.move_to`
IK_SOLVER = "daqp"  # the backend that solves each step's quadratic program
IK_POSITION_COST = 1.0
IK_ORIENTATION_COST = 1.0
IK_POSTURE_COST = (
    1e-3  # small, so the pull toward home only picks among answers that reach the goal
)
IK_DAMPING = 1e-3  # keeps steps small near a singular pose
KEEP_OUT_DISTANCE = 0.1 * US.m  # how close the arm may come to anything it must not hit
KEEP_OUT_DETECTION = (
    0.4 * US.m
)  # where the avoidance starts to act, wider than the keep-out distance by more than a step can close


# --8<-- [start:inputs]
class CameraInput(mojo.UserData):
    """Where the arm camera sits in the end effector's frame, and how wide it sees."""

    FOVY: float = 70
    """Vertical field of view, in degrees."""

    HEIGHT: float = 0.22 * US.m
    """How far the camera sits off the end effector's axis, clear of its radius."""

    SETBACK: float = 0.1 * US.m
    """How far the camera sits behind the tip."""


class ServoInput(mojo.UserData):
    """The position servo on every joint."""

    KP: float = 2e5 * US["N*m/rad"]
    """Position gain, in torque per radian of error."""

    KV: float = 1e5 * US["N*m*s/rad"]
    """Velocity gain, in torque per radian per second, which damps the joint."""

    ARMATURE: float = 10 * US["kg*m**2"]
    """Armature of every joint, which keeps the lightest ones well behaved under high gains."""

    RANGE_DEG: float = 180
    """Largest angle a servo can be commanded to, in degrees either way."""

    SLEW_RATE_DEG: float = 8
    """Fastest a commanded angle may change, in degrees per second."""


class HomeInput(mojo.UserData):
    """The angle of each joint when the model is built, in degrees. The arm is built bent like this, so every joint angle is measured from this home pose, and a servo commanded to zero holds it."""

    SHOULDER_ROLL: float = VISITOR.AZIMUTH_DEG - 70
    """Shoulder roll, which turns the plane the arm bends in."""

    SHOULDER_YAW: float = 0
    """Shoulder yaw."""

    SHOULDER_PITCH: float = 20
    """Shoulder pitch, which tilts the first boom away from straight out of the station."""

    ELBOW_PITCH: float = 130
    """Elbow pitch, which folds the second boom back toward the first."""

    WRIST_PITCH: float = -35
    """Wrist pitch."""

    WRIST_YAW: float = 0
    """Wrist yaw."""

    WRIST_ROLL: float = 0
    """Wrist roll."""


class ArmInput(mojo.UserData):
    """Dimensions and masses of the arm's parts, from the station out. The roll, yaw and pitch housings are the same at both ends."""

    roll: CylinderInput = CylinderInput(
        RADIUS=0.3 * US.m, LENGTH=0.4 * US.m, MASS=100 * US.kg
    )
    """The roll housing, a drum along the arm from the joint outward."""

    yaw: CylinderInput = CylinderInput(
        RADIUS=0.22 * US.m, LENGTH=0.5 * US.m, MASS=60 * US.kg
    )
    """The yaw housing, a cylinder along the yaw axis, centered on the joint."""

    pitch: CylinderInput = CylinderInput(
        RADIUS=0.22 * US.m, LENGTH=0.5 * US.m, MASS=60 * US.kg
    )
    """The pitch housing, a cylinder along the pitch axis, centered on the joint."""

    boom_1: CylinderInput = CylinderInput(
        RADIUS=0.12 * US.m, LENGTH=3.0 * US.m, MASS=150 * US.kg
    )
    """The first boom, from the shoulder to the elbow."""

    elbow: CylinderInput = CylinderInput(
        RADIUS=0.2 * US.m, LENGTH=0.4 * US.m, MASS=40 * US.kg
    )
    """The elbow housing, a cylinder along the elbow's axis, centered on the joint."""

    boom_2: CylinderInput = CylinderInput(
        RADIUS=0.12 * US.m, LENGTH=3.0 * US.m, MASS=120 * US.kg
    )
    """The second boom, from the elbow to the wrist."""

    camera: CameraInput = CameraInput()
    """The camera on the free end effector."""

    servo: ServoInput = ServoInput()
    """The servo on each joint."""

    home: HomeInput = HomeInput()
    """The pose the arm starts in."""


ARM = ArmInput()
# --8<-- [end:inputs]


# start poses the arm was tested from, and every one berths: set `ARM.home = HOME_POSES["straight"]` before `generate` to try one
HOME_POSES: dict[str, HomeInput] = {
    "default": HomeInput(),
    "straight": HomeInput(SHOULDER_PITCH=0, ELBOW_PITCH=0, WRIST_PITCH=0),
    "elbow_back": HomeInput(SHOULDER_PITCH=-40, ELBOW_PITCH=-100, WRIST_PITCH=40),
    "folded": HomeInput(SHOULDER_PITCH=30, ELBOW_PITCH=165, WRIST_PITCH=-60),
    # drawn at random in degrees from seeds 1 to 6, rounded to a tenth
    "random_1": HomeInput(
        SHOULDER_ROLL=4.3,
        SHOULDER_YAW=54.1,
        SHOULDER_PITCH=-64.1,
        ELBOW_PITCH=134.6,
        WRIST_PITCH=-33.9,
        WRIST_YAW=-9.2,
        WRIST_ROLL=118.0,
    ),
    "random_2": HomeInput(
        SHOULDER_ROLL=-85.8,
        SHOULDER_YAW=-24.2,
        SHOULDER_PITCH=56.6,
        ELBOW_PITCH=-122.4,
        WRIST_PITCH=18.0,
        WRIST_YAW=27.4,
        WRIST_ROLL=-112.4,
    ),
    "random_3": HomeInput(
        SHOULDER_ROLL=-149.2,
        SHOULDER_YAW=-31.6,
        SHOULDER_PITCH=54.2,
        ELBOW_PITCH=24.6,
        WRIST_PITCH=-73.1,
        WRIST_YAW=-8.0,
        WRIST_ROLL=-7.5,
    ),
    "random_4": HomeInput(
        SHOULDER_ROLL=159.5,
        SHOULDER_YAW=1.4,
        SHOULDER_PITCH=85.7,
        ELBOW_PITCH=-125.7,
        WRIST_PITCH=19.3,
        WRIST_YAW=-14.8,
        WRIST_ROLL=108.7,
    ),
    "random_5": HomeInput(
        SHOULDER_ROLL=109.8,
        SHOULDER_YAW=37.0,
        SHOULDER_PITCH=2.8,
        ELBOW_PITCH=-64.3,
        WRIST_PITCH=-80.3,
        WRIST_YAW=-14.0,
        WRIST_ROLL=-32.9,
    ),
    "random_6": HomeInput(
        SHOULDER_ROLL=13.7,
        SHOULDER_YAW=-18.8,
        SHOULDER_PITCH=-23.6,
        ELBOW_PITCH=-37.7,
        WRIST_PITCH=87.7,
        WRIST_YAW=15.9,
        WRIST_ROLL=62.8,
    ),
}


# --8<-- [start:helpers]
# the housings are built once and used at both ends, so the ends cannot differ
def roll_housing(name: str) -> mojo.GeomCylinder:
    """A roll housing: a drum from the joint along the arm."""
    return mojo.GeomCylinder(
        name=mojo.GeomName(name),
        size=ARM.roll.RADIUS,
        fromto=np.array((0, 0, 0, ARM.roll.LENGTH, 0, 0)),
        mass=ARM.roll.MASS,
        rgba=ROLL_COLOR,
        contype=ARM_CONTYPE,
        conaffinity=ARM_CONAFFINITY,
    )


def yaw_housing(name: str) -> mojo.GeomCylinder:
    """A yaw housing: a cylinder along Z, centered on the joint."""
    return mojo.GeomCylinder(
        name=mojo.GeomName(name),
        size=ARM.yaw.RADIUS,
        fromto=np.array((0, 0, -ARM.yaw.LENGTH / 2, 0, 0, ARM.yaw.LENGTH / 2)),
        mass=ARM.yaw.MASS,
        rgba=YAW_COLOR,
        contype=ARM_CONTYPE,
        conaffinity=ARM_CONAFFINITY,
    )


def pitch_housing(name: str) -> mojo.GeomCylinder:
    """A pitch housing: a cylinder along Y, centered on the joint."""
    return mojo.GeomCylinder(
        name=mojo.GeomName(name),
        size=ARM.pitch.RADIUS,
        fromto=np.array((0, -ARM.pitch.LENGTH / 2, 0, 0, ARM.pitch.LENGTH / 2, 0)),
        mass=ARM.pitch.MASS,
        rgba=PITCH_COLOR,
        contype=ARM_CONTYPE,
        conaffinity=ARM_CONAFFINITY,
    )


def hinge(name: str, axis: tuple[float, float, float]) -> mojo.Joint:
    """A hinge joint about `axis`, with the arm's armature."""
    return mojo.Joint(
        name=mojo.JointName(name),
        type=mojo.JointType.HINGE,
        axis=np.array(axis),
        armature=ARM.servo.ARMATURE,
        limited=mojo.JointLimited.TRUE,
        # in degrees, the unit MuJoCo's compiler reads by default
        range=np.array((-ARM.servo.RANGE_DEG, ARM.servo.RANGE_DEG)),
    )


def out_of_station(pos: mojo.Vec3) -> mojo.PoseEuler:
    """A pose at `pos` in the station fixture's frame whose X axis points out of the station."""
    # the fixture's X axis points into the station, so this is half a turn about Y
    return mojo.PoseEuler(euler=np.array((0, 180, 0)), angle=mojo.Angle.DEGREE, pos=pos)


def turned(
    pos: mojo.Vec3, axis: Literal["x", "y", "z"], degrees: float
) -> mojo.PoseEuler:
    """The pose of a joint's body at `pos` when the joint is at its home angle: turned `degrees` about its own `axis`."""
    euler = np.zeros(3)
    euler["xyz".index(axis)] = degrees
    return mojo.PoseEuler(euler=euler, angle=mojo.Angle.DEGREE, pos=pos)


# --8<-- [end:helpers]


# --8<-- [start:arm]
class Arm(mojo.UserData):
    """The arm, built in its home pose, so every joint angle is measured from home. In its own frame it points along +X, out of the station."""

    body: mojo.Body
    """The first body, which the shoulder roll turns, at the root of the base end effector."""

    shoulder_roll: mojo.Joint
    """The shoulder roll joint."""

    shoulder_yaw: mojo.Joint
    """The shoulder yaw joint."""

    shoulder_pitch: mojo.Joint
    """The shoulder pitch joint."""

    elbow_pitch: mojo.Joint
    """The elbow pitch joint."""

    boom_1: mojo.GeomMesh
    """The first boom's volume."""

    boom_2: mojo.GeomMesh
    """The second boom's volume."""

    wrist_pitch: mojo.Joint
    """The wrist pitch joint."""

    wrist_yaw: mojo.Joint
    """The wrist yaw joint."""

    wrist_roll: mojo.Joint
    """The wrist roll joint."""

    base_effector: EndEffector
    """The end effector latched onto the station's fixture, with its tip at the fixture's site."""

    free_effector: EndEffector
    """The end effector at the free end."""

    free_end: mojo.Body
    """The last body in the chain, which carries the free end effector. Aiming a camera at it aims at the free end's center of mass."""

    camera: mojo.Camera
    """The camera on the free end effector. Its `name` is what a video recorder needs."""

    servos: list[mojo.ActuatorPosition]
    """The position servo of each joint, in the order of `joints`. Its control value is the angle to hold, in radians from home."""

    _command: np.ndarray = PrivateAttr(default_factory=lambda: np.zeros(7))
    """The angles the servos are commanded to hold, in radians from home, in the order of `joints`. Runtime state, so not saved with the model."""

    _configuration: mink.Configuration | None = PrivateAttr(default=None)
    """The solver's own copy of the model's configuration, which it moves one step at a time. Made on the first `move_to`."""

    _frame_task: mink.FrameTask | None = PrivateAttr(default=None)
    """Asks the free end effector's site to be at the goal."""

    _tasks: list[mink.Task] = PrivateAttr(default_factory=list)
    """What the solver works toward: the frame task, then the pull toward home."""

    _limits: list[mink.Limit] = PrivateAttr(default_factory=list)
    """What the solver must respect: each joint's range and its speed, and what the arm must keep clear of."""

    _held: list[mink.Task] = PrivateAttr(default_factory=list)
    """What the solver must keep still, which is everything that is not one of the arm's joints."""

    _qpos_address: np.ndarray = PrivateAttr(default_factory=lambda: np.zeros(7, int))
    """Where each joint is in `qpos`."""

    _other_qpos: np.ndarray = PrivateAttr(default_factory=lambda: np.zeros(0, int))
    """Where everything that is not one of the arm's joints is in `qpos`, such as the visitor."""

    _obstacles: list[mojo.GeomMesh] = PrivateAttr(default_factory=list)
    """What the arm must keep clear of, set by `keep_clear_of`."""

    _grapple: mojo.GeomMesh | None = PrivateAttr(default=None)
    """The one thing the free end effector may touch."""

    _waypoint_pos: np.ndarray | None = PrivateAttr(default=None)
    """The goal `carry_to` has moved to so far, in the world."""

    _waypoint_quat: np.ndarray | None = PrivateAttr(default=None)
    """The orientation of that goal, as a quaternion (w, x, y, z)."""

    @property
    def command(self) -> np.ndarray:
        """A copy of the commanded angles."""
        return self._command.copy()

    # --8<-- [start:register]
    def register_servos(self) -> None:
        """Hands each servo to the runtime, which reads its control value from the commanded angles every step. Call it inside the runtime manager's `with` block."""
        for i, servo in enumerate(self.servos):
            rt.ActuatorControl(
                name=f"{servo.name}_command",
                actuator=servo,
                control_func=lambda user_data, state, i=i: float(self._command[i]),
            ).register_to_rm()

    # --8<-- [end:register]

    # --8<-- [start:ik]
    def keep_clear_of(
        self,
        *obstacles: mojo.GeomMesh,
        grapple: mojo.GeomMesh,
    ) -> None:
        """Makes the arm keep clear of `obstacles`, and of `grapple` too, except that the free end effector may touch `grapple`. Call it before the first `move_to`."""
        self._obstacles = list(obstacles)
        self._grapple = grapple

    def _keep_out(self, model: mujoco.MjModel) -> mink.CollisionAvoidanceLimit:
        """The limit that keeps the arm's geoms away from the obstacles."""
        assert self._grapple is not None
        arm = [
            int(g) for g in mink.get_subtree_geom_ids(model, self.body.get_id(model))
        ]
        free_end = self.free_effector.geom.get_id(model)
        obstacles = [obstacle.get_id(model) for obstacle in self._obstacles]
        return mink.CollisionAvoidanceLimit(
            model,
            geom_pairs=[
                (arm, obstacles),
                # the free end effector is meant to meet the grapple fixture, so it is left out
                ([g for g in arm if g != free_end], [self._grapple.get_id(model)]),
            ],
            minimum_distance_from_collisions=KEEP_OUT_DISTANCE,
            collision_detection_distance=KEEP_OUT_DETECTION,
        )

    def _start_ik(self, state: mojo.MjState) -> None:
        """Sets up mink, starting from the state's configuration."""
        model = state.model
        q = state.data.qpos.copy()
        self._qpos_address = np.array([j.qpos_address(state) for j in self.joints])
        dof_address = np.array([j.dof_address(state) for j in self.joints])
        assert self.free_effector.tip.name

        self._configuration = mink.Configuration(model, q)
        self._frame_task = mink.FrameTask(
            frame_name=self.free_effector.tip.name,
            frame_type="site",
            position_cost=IK_POSITION_COST,
            orientation_cost=IK_ORIENTATION_COST,
        )

        # the goal leaves one joint free (the elbow can swivel about the line from shoulder to wrist), so a weak pull toward home picks one answer
        cost = np.zeros(model.nv)
        cost[dof_address] = IK_POSTURE_COST
        posture = mink.PostureTask(model, cost=cost)
        home = q.copy()
        home[self._qpos_address] = 0
        posture.set_target(home)

        self._other_qpos = np.setdiff1d(np.arange(model.nq), self._qpos_address)

        # with nothing holding it, the solver can satisfy a distance limit by moving the visitor away instead of the arm
        others = np.setdiff1d(np.arange(model.nv), dof_address)
        self._held = [mink.DofFreezingTask(model, [int(dof) for dof in others])]

        speeds: dict[str, float] = {}
        for joint in self.joints:
            assert joint.name
            speeds[joint.name] = np.deg2rad(ARM.servo.SLEW_RATE_DEG)
        self._tasks = [self._frame_task, posture]
        self._limits = [
            mink.ConfigurationLimit(model),
            mink.VelocityLimit(model, speeds),
        ]
        if self._obstacles:
            self._limits.append(self._keep_out(model))

    def move_to(self, state: mojo.MjState, tip: mojo.Vec3, frame: mojo.Mat3) -> float:
        """Takes one step toward the end effector's site being at `tip` with orientation `frame`, both fixed in the world. Returns the distance the site still has to go."""
        if self._configuration is None:
            self._start_ik(state)
        assert self._configuration is not None
        assert self._frame_task is not None

        self._frame_task.set_target(
            mink.SE3.from_rotation_and_translation(
                mink.SO3.from_matrix(np.asarray(frame, dtype=float)),
                np.asarray(tip, dtype=float),
            )
        )
        # the visitor moves in the simulation but not in mink's copy, so bring it up to date
        q = self._configuration.q.copy()
        q[self._other_qpos] = state.data.qpos[self._other_qpos]
        self._configuration.update(q)

        timestep = state.model.opt.timestep
        velocity = mink.solve_ik(
            self._configuration,
            self._tasks,
            timestep,
            IK_SOLVER,
            damping=IK_DAMPING,
            limits=self._limits,
            constraints=self._held,
        )
        self._configuration.integrate_inplace(velocity, timestep)
        self._command[:] = self._configuration.q[self._qpos_address]
        return float(np.linalg.norm(self.free_effector.tip.rt_pos(state) - tip))

    # --8<-- [end:ik]

    def carry_to(
        self,
        state: mojo.MjState,
        tip: mojo.Vec3,
        frame: mojo.Mat3,
        speed: float,
    ) -> float:
        """Like `move_to`, but the goal moves to the target in a straight line at `speed`, so the tip does too. Use it to carry something. Returns the distance the tip still has to go."""
        tip_site = self.free_effector.tip
        timestep = state.model.opt.timestep

        if self._waypoint_pos is None or self._waypoint_quat is None:
            self._waypoint_pos = tip_site.rt_pos(state).copy()
            self._waypoint_quat = np.empty(4)
            mujoco.mju_mat2Quat(self._waypoint_quat, tip_site.rt_xmat(state).ravel())

        # the goal moves this fraction of the way to the target, and its orientation turns by the same fraction, so the two arrive together
        to_go = tip - self._waypoint_pos
        distance = float(np.linalg.norm(to_go))
        fraction = 1.0 if distance <= speed * timestep else speed * timestep / distance
        self._waypoint_pos = self._waypoint_pos + fraction * to_go

        target_quat, inverse, difference = np.empty(4), np.empty(4), np.empty(4)
        mujoco.mju_mat2Quat(target_quat, np.asarray(frame, dtype=float).ravel())
        mujoco.mju_negQuat(inverse, self._waypoint_quat)
        mujoco.mju_mulQuat(difference, target_quat, inverse)
        turn = np.empty(3)
        mujoco.mju_quat2Vel(turn, difference, 1.0)
        angle = float(np.linalg.norm(turn))
        if angle > 1e-12:
            step, turned = np.empty(4), np.empty(4)
            mujoco.mju_axisAngle2Quat(step, turn / angle, fraction * angle)
            mujoco.mju_mulQuat(turned, step, self._waypoint_quat)
            self._waypoint_quat = turned / np.linalg.norm(turned)
        waypoint_frame = np.empty(9)
        mujoco.mju_quat2Mat(waypoint_frame, self._waypoint_quat)

        self.move_to(state, self._waypoint_pos, waypoint_frame.reshape(3, 3))
        return float(np.linalg.norm(tip_site.rt_pos(state) - tip))

    # --8<-- [start:approach]
    def approach(
        self, state: mojo.MjState, site: mojo.SiteSphere, standoff: float
    ) -> float:
        """Takes one step toward the tip being `standoff` in front of `site`, facing it. Returns the distance the tip still has to go. `standoff` is measured back along the site's X axis, and facing means the tip's frame matches the site's. The goal follows the site, so it is no use once the tip holds the site: use `move_to` then."""
        frame = site.rt_xmat(state)
        return self.move_to(state, site.rt_pos(state) - standoff * frame[:, 0], frame)

    # --8<-- [end:approach]

    def misalignment(
        self, state: mojo.MjState, site: mojo.SiteSphere
    ) -> tuple[float, float]:
        """How far the tip is from being colinear with `site`: its distance from the site's axis, and the angle between the two X axes, in radians. Being on the axis is not enough, since the tip can be on it and turned."""
        axis = site.rt_xmat(state)[:, 0]
        to_tip = self.free_effector.tip.rt_pos(state) - site.rt_pos(state)
        off_axis = np.linalg.norm(to_tip - (to_tip @ axis) * axis)
        tip_axis = self.free_effector.tip.rt_xmat(state)[:, 0]
        angle = np.arccos(np.clip(tip_axis @ axis, -1.0, 1.0))
        return float(off_axis), float(angle)

    @property
    def joints(self) -> list[mojo.Joint]:
        """The seven joints, from the station out."""
        return [
            self.shoulder_roll,
            self.shoulder_yaw,
            self.shoulder_pitch,
            self.elbow_pitch,
            self.wrist_pitch,
            self.wrist_yaw,
            self.wrist_roll,
        ]

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel, base: GrappleFixture) -> Self:
        """Builds the arm and nests it in the frame of `base`, the station's fixture."""
        mojo_model.mjcf.assets.append(
            mojo.Asset(
                meshes=[
                    boom_1_mesh := ARM.boom_1.mesh("boom_1_mesh"),
                    boom_2_mesh := ARM.boom_2.mesh("boom_2_mesh"),
                ]
            )
        )
        assert boom_1_mesh.name
        assert boom_2_mesh.name

        # laid down along X and moved out by half their length, so each runs from its joint outward
        boom_1 = mojo.GeomMesh(
            name=mojo.GeomName("boom_1_geom"),
            mesh=boom_1_mesh.name,
            pose=lying_along("x", center=np.array((ARM.boom_1.LENGTH / 2, 0, 0))),
            mass=ARM.boom_1.MASS,
            rgba=mojo.utils.Color.SLATE_200.rgba,
            contype=ARM_CONTYPE,
            conaffinity=ARM_CONAFFINITY,
        )
        boom_2 = mojo.GeomMesh(
            name=mojo.GeomName("boom_2_geom"),
            mesh=boom_2_mesh.name,
            pose=lying_along("x", center=np.array((ARM.boom_2.LENGTH / 2, 0, 0))),
            mass=ARM.boom_2.MASS,
            rgba=mojo.utils.Color.SLATE_400.rgba,
            contype=ARM_CONTYPE,
            conaffinity=ARM_CONAFFINITY,
        )

        # the same part as the free end, latched onto the station's fixture: its tip is at the fixture's site, so its root is one length farther out
        root = base.site.pose.pos - np.array((END_EFFECTOR.LENGTH, 0, 0))
        base_effector = EndEffector.new(mojo_model, "base", mojo.PoseQuat(pos=root))
        base.frame.frames.append(base_effector.frame)

        # --8<-- [start:shoulder]
        # one body per joint, from the station out, so each joint turns everything after it
        roll_body = mojo.Body(
            name=mojo.BodyName("shoulder_roll"),
            # turned out of the station, then rolled about its own X axis
            pose=out_of_station(root)
            * turned(np.zeros(3), "x", ARM.home.SHOULDER_ROLL),
            geoms=[roll_housing("shoulder_roll_geom")],
        )
        shoulder_roll = hinge("shoulder_roll", (1, 0, 0))
        roll_body.joints.append(shoulder_roll)

        # the yaw and pitch bodies sit at the shoulder, so all three axes meet there
        yaw_body = mojo.Body(
            name=mojo.BodyName("shoulder_yaw"),
            pose=turned(np.array((ARM.roll.LENGTH, 0, 0)), "z", ARM.home.SHOULDER_YAW),
            geoms=[yaw_housing("shoulder_yaw_geom")],
        )
        shoulder_yaw = hinge("shoulder_yaw", (0, 0, 1))
        yaw_body.joints.append(shoulder_yaw)
        roll_body.bodies.append(yaw_body)

        pitch_body = mojo.Body(
            name=mojo.BodyName("shoulder_pitch"),
            pose=turned(np.zeros(3), "y", ARM.home.SHOULDER_PITCH),
            geoms=[pitch_housing("shoulder_pitch_geom"), boom_1],
        )
        shoulder_pitch = hinge("shoulder_pitch", (0, 1, 0))
        pitch_body.joints.append(shoulder_pitch)
        yaw_body.bodies.append(pitch_body)
        # --8<-- [end:shoulder]

        elbow_body = mojo.Body(
            name=mojo.BodyName("elbow_pitch"),
            pose=turned(np.array((ARM.boom_1.LENGTH, 0, 0)), "y", ARM.home.ELBOW_PITCH),
            geoms=[
                mojo.GeomCylinder(
                    name=mojo.GeomName("elbow_geom"),
                    size=ARM.elbow.RADIUS,
                    fromto=np.array(
                        (0, -ARM.elbow.LENGTH / 2, 0, 0, ARM.elbow.LENGTH / 2, 0)
                    ),
                    mass=ARM.elbow.MASS,
                    rgba=PITCH_COLOR,
                    contype=ARM_CONTYPE,
                    conaffinity=ARM_CONAFFINITY,
                ),
                boom_2,
            ],
        )
        elbow_pitch = hinge("elbow_pitch", (0, 1, 0))
        elbow_body.joints.append(elbow_pitch)
        pitch_body.bodies.append(elbow_body)

        # the wrist's three axes meet at the end of the second boom, with the same housings as the shoulder
        wrist_pitch_body = mojo.Body(
            name=mojo.BodyName("wrist_pitch"),
            pose=turned(np.array((ARM.boom_2.LENGTH, 0, 0)), "y", ARM.home.WRIST_PITCH),
            geoms=[pitch_housing("wrist_pitch_geom")],
        )
        wrist_pitch = hinge("wrist_pitch", (0, 1, 0))
        wrist_pitch_body.joints.append(wrist_pitch)
        elbow_body.bodies.append(wrist_pitch_body)

        wrist_yaw_body = mojo.Body(
            name=mojo.BodyName("wrist_yaw"),
            pose=turned(np.zeros(3), "z", ARM.home.WRIST_YAW),
            geoms=[yaw_housing("wrist_yaw_geom")],
        )
        wrist_yaw = hinge("wrist_yaw", (0, 0, 1))
        wrist_yaw_body.joints.append(wrist_yaw)
        wrist_pitch_body.bodies.append(wrist_yaw_body)

        # the free end effector is mounted at the far end of the roll housing, so the roll turns both
        wrist_roll_body = mojo.Body(
            name=mojo.BodyName("wrist_roll"),
            pose=turned(np.zeros(3), "x", ARM.home.WRIST_ROLL),
            geoms=[roll_housing("wrist_roll_geom")],
        )
        free_effector = EndEffector.new(
            mojo_model, "free", mojo.PoseQuat(pos=np.array((ARM.roll.LENGTH, 0, 0)))
        )
        wrist_roll_body.frames.append(free_effector.frame)

        # --8<-- [start:camera]
        # only the free end has a camera: in the end effector's frame, so the roll turns it, and off the axis, so the end effector stays out of the picture
        eye = np.array((END_EFFECTOR.LENGTH - ARM.camera.SETBACK, 0, ARM.camera.HEIGHT))
        camera = mojo.Camera(
            name=mojo.CameraName("arm_camera"),
            fovy=ARM.camera.FOVY,
            pose=mojo.PoseQuat.look_at(
                target=eye + np.array((1, 0, 0)), eye=eye, roll=-90
            ),
        )
        free_effector.frame.cameras.append(camera)
        # --8<-- [end:camera]
        wrist_roll = hinge("wrist_roll", (1, 0, 0))
        wrist_roll_body.joints.append(wrist_roll)
        wrist_yaw_body.bodies.append(wrist_roll_body)

        # fixed to the station, through its fixture
        base.frame.bodies.append(roll_body)

        arm = cls(
            body=roll_body,
            shoulder_roll=shoulder_roll,
            shoulder_yaw=shoulder_yaw,
            shoulder_pitch=shoulder_pitch,
            elbow_pitch=elbow_pitch,
            boom_1=boom_1,
            boom_2=boom_2,
            wrist_pitch=wrist_pitch,
            wrist_yaw=wrist_yaw,
            wrist_roll=wrist_roll,
            base_effector=base_effector,
            free_effector=free_effector,
            free_end=wrist_roll_body,
            camera=camera,
            servos=[],
        )

        # --8<-- [start:servos]
        limit = np.deg2rad(ARM.servo.RANGE_DEG)
        arm.servos.extend(
            mojo.ActuatorPosition(
                name=mojo.ActuatorName(f"{joint.name}_servo"),
                joint=joint.name,
                kp=ARM.servo.KP,
                kv=ARM.servo.KV,
                ctrlrange=np.array((-limit, limit)),
            )
            for joint in arm.joints
        )
        mojo_model.mjcf.actuators.append(mojo.Actuator(positions=arm.servos))
        # --8<-- [end:servos]

        return arm


# --8<-- [end:arm]
