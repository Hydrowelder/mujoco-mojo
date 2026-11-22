"""The robotic arm, the same from either end: an end effector, a roll, yaw and pitch joint, a boom, the elbow, a boom, a pitch, yaw and roll joint, and an end effector. One end is latched onto the station's grapple fixture, and the other reaches for the visitor."""

from __future__ import annotations

from typing import Literal, Self

import mujoco
import numpy as np
from end_effector import END_EFFECTOR, EndEffector
from fixture import GrappleFixture
from pydantic import PrivateAttr
from shapes import CylinderInput, cylinder_mesh, lying_along
from visitor import VISITOR

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

US = mojo.UnitSystem.si()  # define a unit system used throughout the model

# each joint's housing is colored by the axis it turns about: red for roll (X), green for pitch (Y) and blue for yaw (Z), the colors a viewer draws for those axes
ROLL_COLOR = mojo.utils.Color.RED_500.rgba
PITCH_COLOR = mojo.utils.Color.GREEN_500.rgba
YAW_COLOR = mojo.utils.Color.BLUE_500.rgba

REACH_OPACITY = 0.02

# how `Arm.solve` works: it stops when the tip is this close to the goal (in meters and in radians), gives up after this many iterations, damps its steps so they stay sane near a singular pose, never moves a joint more than this far (in radians) in one iteration, and pulls the joints toward home by this fraction of their angle in the direction that does not move the tip. The pull is what stops the seventh joint drifting, but it also leaves a small error that grows with it (about 2e-5 at this value), so the tolerance has to stay above that
SOLVER_TOLERANCE = 1e-4
SOLVER_ITERATIONS = 100
SOLVER_DAMPING = 0.05
SOLVER_MAX_STEP = 0.2
SOLVER_HOME_PULL = 0.01


# --8<-- [start:inputs]
class CameraInput(mojo.UserData):
    """Where the camera on the free end effector sits, in the end effector's frame, and how wide it sees. It looks along the end effector."""

    FOVY: float = 70
    """Vertical field of view, in degrees."""

    HEIGHT: float = 0.22 * US.m
    """How far the camera sits off the end effector's axis, clear of its radius, so the end effector stays out of the picture."""

    SETBACK: float = 0.1 * US.m
    """How far the camera sits behind the end effector's tip."""


class ServoInput(mojo.UserData):
    """The position servo on every joint, which are all the same."""

    KP: float = 2e5 * US["N*m/rad"]
    """Position gain: the torque for each radian between a joint's angle and the angle commanded."""

    KV: float = 1e5 * US["N*m*s/rad"]
    """Velocity gain: the torque for each radian per second of a joint's motion, which damps it."""

    ARMATURE: float = 10 * US["kg*m**2"]
    """Armature of every joint, the inertia of its motor, which keeps the lightest joints well behaved under high gains."""

    RANGE_DEG: float = 180
    """Largest angle a servo can be commanded to, in degrees either way. It is also the range of a viewer's control sliders."""

    SLEW_RATE_DEG: float = 8
    """Fastest a servo's commanded angle may move, in degrees per second. A step in the command would make a huge torque, so the runtime moves it at this rate instead."""


class HomeInput(mojo.UserData):
    """The angle of each joint when the model is built, in degrees: the home pose. The arm is built bent like this, so every joint's angle is measured from home, a joint at zero is at home, and a servo with a control value of zero holds the arm there. The defaults fold the arm into a V that points at the visitor: the shoulder turns toward it, the first boom tilts up and out, the second comes back down toward it, and the end effector points at its grapple fixture."""

    SHOULDER_ROLL: float = VISITOR.AZIMUTH_DEG
    """Shoulder roll, which turns the plane the arm bends in. It is the visitor's direction from the station, so the arm bends toward the visitor."""

    SHOULDER_YAW: float = 0
    """Shoulder yaw."""

    SHOULDER_PITCH: float = 20
    """Shoulder pitch, which tilts the first boom away from straight out of the station."""

    ELBOW_PITCH: float = 130
    """Elbow pitch, which folds the second boom back toward the first. The bigger it is, the narrower the V."""

    WRIST_PITCH: float = -35
    """Wrist pitch, which turns the end effector, here back up from the second boom so it points at the visitor."""

    WRIST_YAW: float = 0
    """Wrist yaw."""

    WRIST_ROLL: float = 0
    """Wrist roll."""


class ArmInput(mojo.UserData):
    """Dimensions and masses of the arm's parts, from the station out. The end effector is `END_EFFECTOR`, in its own module, since both ends use it. The roll, yaw and pitch housings are the same at both ends of the arm."""

    roll: CylinderInput = CylinderInput(
        RADIUS=0.3 * US.m, LENGTH=0.4 * US.m, MASS=100 * US.kg
    )
    """The roll housing, a drum that runs from the joint out along the arm. The shoulder's runs from the base end effector's root to the shoulder, and the wrist's runs from the wrist to the free end effector's root."""

    yaw: CylinderInput = CylinderInput(
        RADIUS=0.22 * US.m, LENGTH=0.5 * US.m, MASS=60 * US.kg
    )
    """The yaw housing, a cylinder along the yaw axis and centered on the joint."""

    pitch: CylinderInput = CylinderInput(
        RADIUS=0.22 * US.m, LENGTH=0.5 * US.m, MASS=60 * US.kg
    )
    """The pitch housing, a cylinder along the pitch axis and centered on the joint."""

    boom_1: CylinderInput = CylinderInput(
        RADIUS=0.12 * US.m, LENGTH=3.0 * US.m, MASS=150 * US.kg
    )
    """The first boom, from the shoulder to the elbow."""

    elbow: CylinderInput = CylinderInput(
        RADIUS=0.2 * US.m, LENGTH=0.4 * US.m, MASS=40 * US.kg
    )
    """The elbow housing, a cylinder along the elbow's axis and centered on the joint."""

    boom_2: CylinderInput = CylinderInput(
        RADIUS=0.12 * US.m, LENGTH=3.0 * US.m, MASS=120 * US.kg
    )
    """The second boom, from the elbow to the wrist."""

    camera: CameraInput = CameraInput()
    """The camera on the free end effector. The base end effector has none."""

    servo: ServoInput = ServoInput()
    """The servo on each of the seven joints."""

    home: HomeInput = HomeInput()
    """The pose the arm starts in."""

    @property
    def LENGTH(self) -> float:
        """The arm's length from end to end when it is straight: both end effectors, both roll housings and both booms. The free end can get no farther than this from the tip of the base end effector."""
        return (
            2 * END_EFFECTOR.LENGTH
            + 2 * self.roll.LENGTH
            + self.boom_1.LENGTH
            + self.boom_2.LENGTH
        )


ARM = ArmInput()
# --8<-- [end:inputs]


# the three housings are built here, once, and used at both ends of the arm, so the ends cannot differ
def roll_housing(name: str) -> mojo.GeomCylinder:
    """A roll joint's housing, a red drum that runs from the joint out along the arm."""
    return mojo.GeomCylinder(
        name=mojo.GeomName(name),
        size=ARM.roll.RADIUS,
        fromto=np.array((0, 0, 0, ARM.roll.LENGTH, 0, 0)),
        mass=ARM.roll.MASS,
        rgba=ROLL_COLOR,
    )


def yaw_housing(name: str) -> mojo.GeomCylinder:
    """A yaw joint's housing, a blue cylinder along the yaw axis (Z) and centered on the joint."""
    return mojo.GeomCylinder(
        name=mojo.GeomName(name),
        size=ARM.yaw.RADIUS,
        fromto=np.array((0, 0, -ARM.yaw.LENGTH / 2, 0, 0, ARM.yaw.LENGTH / 2)),
        mass=ARM.yaw.MASS,
        rgba=YAW_COLOR,
    )


def pitch_housing(name: str) -> mojo.GeomCylinder:
    """A pitch joint's housing, a green cylinder along the pitch axis (Y) and centered on the joint."""
    return mojo.GeomCylinder(
        name=mojo.GeomName(name),
        size=ARM.pitch.RADIUS,
        fromto=np.array((0, -ARM.pitch.LENGTH / 2, 0, 0, ARM.pitch.LENGTH / 2, 0)),
        mass=ARM.pitch.MASS,
        rgba=PITCH_COLOR,
    )


def hinge(name: str, axis: tuple[float, float, float]) -> mojo.Joint:
    """A hinge joint about `axis`, with the armature every joint of the arm has."""
    return mojo.Joint(
        name=mojo.JointName(name),
        type=mojo.JointType.HINGE,
        axis=np.array(axis),
        armature=ARM.servo.ARMATURE,
    )


def out_of_station(pos: mojo.Vec3) -> mojo.PoseEuler:
    """A pose at `pos`, in the frame of the station's grapple fixture, whose X axis points out of the station. The fixture's own X axis points into the station, so this is half a revolution about Y."""
    return mojo.PoseEuler(euler=np.array((0, 180, 0)), angle=mojo.Angle.DEGREE, pos=pos)


def turned(
    pos: mojo.Vec3, axis: Literal["x", "y", "z"], degrees: float
) -> mojo.PoseEuler:
    """The pose of a joint's body, at `pos`, when the joint is at its home angle: turned `degrees` about its own `axis`. The joint turns about that same axis, so the axis in the body's parent is unchanged, and everything after the joint is carried round with it."""
    euler = np.zeros(3)
    euler["xyz".index(axis)] = degrees
    return mojo.PoseEuler(euler=euler, angle=mojo.Angle.DEGREE, pos=pos)


# --8<-- [start:arm]
class Arm(mojo.UserData):
    """The robotic arm. In its own frame the arm points along +X, which is out of the station, and the roll joints turn about X, the yaw joints about Z and the pitch joints about Y. It is built in its home pose (`HomeInput`), a V that points at the visitor, so every joint's angle is measured from home."""

    body: mojo.Body
    """The arm's first body, the shoulder roll's, which sits at the root of the base end effector."""

    shoulder_roll: mojo.Joint
    """The shoulder's roll joint, about the arm's own axis."""

    shoulder_yaw: mojo.Joint
    """The shoulder's yaw joint."""

    shoulder_pitch: mojo.Joint
    """The shoulder's pitch joint."""

    elbow_pitch: mojo.Joint
    """The elbow's pitch joint, which bends the second boom toward or away from the first."""

    boom_1: mojo.GeomMesh
    """The first boom's volume, from the shoulder to the elbow."""

    boom_2: mojo.GeomMesh
    """The second boom's volume, from the elbow to the wrist."""

    wrist_pitch: mojo.Joint
    """The wrist's pitch joint."""

    wrist_yaw: mojo.Joint
    """The wrist's yaw joint."""

    wrist_roll: mojo.Joint
    """The wrist's roll joint, about the free end effector's own axis."""

    base_effector: EndEffector
    """The end effector at the base, latched onto the station's grapple fixture. Its tip site is at the fixture's site, with the same frame."""

    free_effector: EndEffector
    """The end effector at the free end, which reaches for the visitor's grapple fixture."""

    reach: mojo.GeomMesh
    """The reach envelope, a translucent hemisphere centered on the tip of the base end effector with the arm's full length as its radius. The free end can never get outside it."""

    camera: mojo.Camera
    """The camera on the free end effector, looking along it. Its `name` is what a video recorder needs."""

    servos: list[mojo.ActuatorPosition]
    """The position servo of each joint, in the same order as `joints`. A servo's control value is the angle its joint is commanded to, in radians from home, so zero holds the arm in its home pose."""

    _command: np.ndarray = PrivateAttr(default_factory=lambda: np.zeros(7))
    """The angle each servo is commanded to hold, in radians from home, in the order of `joints`. It is runtime state, so it is not saved with the model, and it starts at zero, which is home."""

    _solution: np.ndarray = PrivateAttr(default_factory=lambda: np.zeros(7))
    """The answer of the last `solve`, in radians from home, which the next one starts from. It starts at zero, which is home."""

    _scratch: mujoco.MjData | None = PrivateAttr(default=None)
    """A private copy of the model's state, which `solve` moves the joints of so the live simulation is never disturbed. It is made the first time it is needed."""

    _qpos_address: np.ndarray = PrivateAttr(default_factory=lambda: np.zeros(7, int))
    """Where each joint's angle is in `qpos`, in the order of `joints`. Found along with `_scratch`."""

    _dof_address: np.ndarray = PrivateAttr(default_factory=lambda: np.zeros(7, int))
    """Where each joint's column is in the Jacobian, in the order of `joints`. Found along with `_scratch`."""

    _tip_id: int = PrivateAttr(default=-1)
    """The free end effector's tip site in the compiled model. Found along with `_scratch`."""

    @property
    def command(self) -> np.ndarray:
        """A copy of the angles the servos are commanded to hold, in radians from home, in the order of `joints`."""
        return self._command.copy()

    def register_servos(self) -> None:
        """Hands each servo to the runtime. Every step the control value of each is read from the commanded angles, so the arm holds whatever it was last commanded to, which at first is home. Call it inside the runtime manager's `with` block."""
        for i, servo in enumerate(self.servos):
            rt.ActuatorControl(
                name=f"{servo.name}_command",
                actuator=servo,
                control_func=lambda user_data, state, i=i: float(self._command[i]),
            ).register_to_rm()

    def solve(
        self, state: mojo.MjState, tip: mojo.Vec3, frame: mojo.Mat3
    ) -> np.ndarray:
        """
        Joint angles, in radians from home, that put the free end effector's tip at `tip` with the orientation `frame`, both in the world. They are in the order of `joints`.

        It is a damped least squares solve on a private copy of the state: it repeatedly moves the joints by the step that the arm's Jacobian says brings the tip closer to the goal. It starts from its own last answer, not from the angles the servos are commanded to (which lag behind while the arm slews), so a goal that holds still costs nothing and one that moves slowly costs a step or two, and the answer is continuous from one call to the next. The seventh joint, which the goal leaves free, is settled by pulling the arm toward its home pose in the one direction that does not move the tip. A goal out of reach gives the nearest the arm can get.
        """
        model = state.model
        if self._scratch is None:
            self._scratch = mujoco.MjData(model)
            self._qpos_address = np.array(
                [model.jnt_qposadr[joint.get_id(model)] for joint in self.joints]
            )
            self._dof_address = np.array(
                [model.jnt_dofadr[joint.get_id(model)] for joint in self.joints]
            )
            self._tip_id = self.free_effector.tip.get_id(model)
        scratch = self._scratch

        goal_quat = np.empty(4)
        mujoco.mju_mat2Quat(goal_quat, np.asarray(frame, dtype=float).ravel())

        angles = self._solution.copy()
        for _ in range(SOLVER_ITERATIONS):
            scratch.qpos[self._qpos_address] = angles
            mujoco.mj_kinematics(model, scratch)
            mujoco.mj_comPos(model, scratch)

            # the orientation error is the rotation, as a vector in the world, that takes the tip's frame to the goal's
            tip_quat, tip_inverse, difference = np.empty(4), np.empty(4), np.empty(4)
            mujoco.mju_mat2Quat(tip_quat, scratch.site_xmat[self._tip_id])
            mujoco.mju_negQuat(tip_inverse, tip_quat)
            mujoco.mju_mulQuat(difference, goal_quat, tip_inverse)
            rotation_error = np.empty(3)
            mujoco.mju_quat2Vel(rotation_error, difference, 1.0)
            position_error = tip - scratch.site_xpos[self._tip_id]
            if (
                np.linalg.norm(position_error) < SOLVER_TOLERANCE
                and np.linalg.norm(rotation_error) < SOLVER_TOLERANCE
            ):
                break

            jacobian_position = np.zeros((3, model.nv))
            jacobian_rotation = np.zeros((3, model.nv))
            mujoco.mj_jacSite(
                model, scratch, jacobian_position, jacobian_rotation, self._tip_id
            )
            jacobian = np.vstack((jacobian_position, jacobian_rotation))[
                :, self._dof_address
            ]
            error = np.concatenate((position_error, rotation_error))
            pseudo_inverse = jacobian.T @ np.linalg.inv(
                jacobian @ jacobian.T + SOLVER_DAMPING**2 * np.eye(6)
            )
            step = pseudo_inverse @ error

            # the seventh joint leaves the goal a whole family of answers (the elbow can swivel around the line from shoulder to wrist), and nothing in the goal chooses between them, so numerical noise alone would walk the arm along it. The answer closest to home is chosen instead, by a pull toward home that is projected so that it cannot move the tip
            null_space = np.eye(len(angles)) - pseudo_inverse @ jacobian
            step -= null_space @ (SOLVER_HOME_PULL * angles)

            angles += np.clip(step, -SOLVER_MAX_STEP, SOLVER_MAX_STEP)

        self._solution = angles
        return angles.copy()

    def slew(self, goal: np.ndarray, dt: float) -> None:
        """Moves the commanded angles one step of `dt` seconds toward `goal`, in radians from home and in the order of `joints`, no faster than the servos' slew rate and never past their range."""
        limit = np.deg2rad(ARM.servo.RANGE_DEG)
        step = np.deg2rad(ARM.servo.SLEW_RATE_DEG) * dt
        goal = np.clip(goal, -limit, limit)
        self._command += np.clip(goal - self._command, -step, step)

    def approach(
        self, state: mojo.MjState, site: mojo.SiteSphere, standoff: float
    ) -> float:
        """
        Takes one step toward putting the free end effector's tip `standoff` meters in front of `site`, facing it, and returns how far the tip still is from there, in meters.

        In front means back along the site's X axis, which points into whatever the site is on, and facing it means the tip's frame matches the site's, which is the frame the capture weld pulls the two together in. A `standoff` of zero is on the site itself. The goal is worked out from where the site is now, so it follows a site that moves.
        """
        frame = site.rt_xmat(state)
        goal = site.rt_pos(state) - standoff * frame[:, 0]
        self.slew(self.solve(state, goal, frame), state.model.opt.timestep)
        return float(np.linalg.norm(self.free_effector.tip.rt_pos(state) - goal))

    def misalignment(
        self, state: mojo.MjState, site: mojo.SiteSphere
    ) -> tuple[float, float]:
        """
        How far the free end effector is from being colinear with `site`: the distance of the tip from the line through the site along its X axis, in meters, and the angle between the tip's X axis and the site's, in radians. Both zero means the end effector is on the site's axis and pointing along it, which is how it has to be to go in straight.

        Being close to a spot on the axis does not say so: the tip can be in the right place and turned, or on the right heading and off to one side.
        """
        axis = site.rt_xmat(state)[:, 0]
        to_tip = self.free_effector.tip.rt_pos(state) - site.rt_pos(state)
        off_axis = np.linalg.norm(to_tip - (to_tip @ axis) * axis)
        tip_axis = self.free_effector.tip.rt_xmat(state)[:, 0]
        angle = np.arccos(np.clip(tip_axis @ axis, -1.0, 1.0))
        return float(off_axis), float(angle)

    @property
    def joints(self) -> list[mojo.Joint]:
        """The seven joints, from the station out: shoulder roll, yaw and pitch, elbow pitch, then wrist pitch, yaw and roll."""
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
        """Builds the arm and nests it in the frame of `base`, the station's grapple fixture."""
        # the booms are builtin cylinders and the reach envelope is a builtin hemisphere, which MuJoCo makes when it compiles the model: a cylinder lies along Z until it is laid down along the arm, and a hemisphere has its flat face on the origin and its dome along Z, with its radius set by the scale
        mojo_model.mjcf.assets.append(
            mojo.Asset(
                meshes=[
                    boom_1_mesh := cylinder_mesh(
                        "boom_1_mesh", ARM.boom_1.RADIUS, ARM.boom_1.LENGTH
                    ),
                    boom_2_mesh := cylinder_mesh(
                        "boom_2_mesh", ARM.boom_2.RADIUS, ARM.boom_2.LENGTH
                    ),
                    reach_mesh := mojo.MeshHemisphere(
                        name=mojo.MeshName("reach_mesh"),
                        resolution=8,
                        scale=np.full(3, ARM.LENGTH),
                    ),
                ]
            )
        )
        assert boom_1_mesh.name
        assert boom_2_mesh.name
        assert reach_mesh.name

        # each boom runs from its joint outward along the arm, so it is laid down along X and moved out by half its length
        boom_1 = mojo.GeomMesh(
            name=mojo.GeomName("boom_1_geom"),
            mesh=boom_1_mesh.name,
            pose=lying_along("x", center=np.array((ARM.boom_1.LENGTH / 2, 0, 0))),
            mass=ARM.boom_1.MASS,
            rgba=mojo.utils.Color.SLATE_200.rgba,
        )
        boom_2 = mojo.GeomMesh(
            name=mojo.GeomName("boom_2_geom"),
            mesh=boom_2_mesh.name,
            pose=lying_along("x", center=np.array((ARM.boom_2.LENGTH / 2, 0, 0))),
            mass=ARM.boom_2.MASS,
            rgba=mojo.utils.Color.SLATE_400.rgba,
        )

        # the end effector at the base is the same part as the one at the free end, latched onto the station's fixture the way the free one will latch onto the visitor's: its tip is at the fixture's site with the same frame, and it runs out of the station, so its root is one end effector length farther out
        root = base.site.pose.pos - np.array((END_EFFECTOR.LENGTH, 0, 0))
        base_effector = EndEffector.new(mojo_model, "base", mojo.PoseQuat(pos=root))
        base.frame.frames.append(base_effector.frame)

        # the reach envelope is a hemisphere with its flat face on the fixture's site and its dome pointing out of the station, and no mass or collisions of its own: the fixture's X axis points into the station, so turning the dome's Z axis a quarter revolution about Y the other way points it out
        reach = mojo.GeomMesh(
            name=mojo.GeomName("reach_geom"),
            mesh=reach_mesh.name,
            pose=mojo.PoseEuler(
                euler=np.array((0, -90, 0)),
                angle=mojo.Angle.DEGREE,
                pos=base.site.pose.pos,
            ),
            density=0,
            contype=0,
            conaffinity=0,
            rgba=mojo.utils.Color.TEAL_500.with_alpha(REACH_OPACITY),
        )
        base.frame.geoms.append(reach)

        # one body per joint, from the station out, so each joint turns everything after it: roll, then yaw, then pitch, starting at the root of the base end effector's far end
        roll_body = mojo.Body(
            name=mojo.BodyName("shoulder_roll"),
            # turned out of the station first, then rolled about its own X axis, which is how two poses chain with `*`
            pose=out_of_station(root)
            * turned(np.zeros(3), "x", ARM.home.SHOULDER_ROLL),
            geoms=[roll_housing("shoulder_roll_geom")],
        )
        shoulder_roll = hinge("shoulder_roll", (1, 0, 0))
        roll_body.joints.append(shoulder_roll)

        # the yaw and pitch bodies sit at the shoulder, the far end of the roll housing, so all three axes meet there
        yaw_body = mojo.Body(
            name=mojo.BodyName("shoulder_yaw"),
            pose=turned(np.array((ARM.roll.LENGTH, 0, 0)), "z", ARM.home.SHOULDER_YAW),
            geoms=[yaw_housing("shoulder_yaw_geom")],
        )
        shoulder_yaw = hinge("shoulder_yaw", (0, 0, 1))
        yaw_body.joints.append(shoulder_yaw)
        roll_body.bodies.append(yaw_body)

        # the pitch body carries the first boom
        pitch_body = mojo.Body(
            name=mojo.BodyName("shoulder_pitch"),
            pose=turned(np.zeros(3), "y", ARM.home.SHOULDER_PITCH),
            geoms=[pitch_housing("shoulder_pitch_geom"), boom_1],
        )
        shoulder_pitch = hinge("shoulder_pitch", (0, 1, 0))
        pitch_body.joints.append(shoulder_pitch)
        yaw_body.bodies.append(pitch_body)

        # the elbow body sits at the end of the first boom, and carries the second boom and the elbow's housing, a cylinder along its pitch axis
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
                ),
                boom_2,
            ],
        )
        elbow_pitch = hinge("elbow_pitch", (0, 1, 0))
        elbow_body.joints.append(elbow_pitch)
        pitch_body.bodies.append(elbow_body)

        # the wrist's three axes meet at the end of the second boom, so its bodies sit there: pitch, then yaw, then roll, with the same housings as the shoulder
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

        # the roll body holds the roll housing, a drum from the wrist out along the arm like the shoulder's, and the free end effector is mounted at its far end, so the roll turns both
        wrist_roll_body = mojo.Body(
            name=mojo.BodyName("wrist_roll"),
            pose=turned(np.zeros(3), "x", ARM.home.WRIST_ROLL),
            geoms=[roll_housing("wrist_roll_geom")],
        )
        free_effector = EndEffector.new(
            mojo_model, "free", mojo.PoseQuat(pos=np.array((ARM.roll.LENGTH, 0, 0)))
        )
        wrist_roll_body.frames.append(free_effector.frame)

        # the camera is only on the free end effector, in its frame so the roll turns it too: it sits just behind the tip and off the axis, and looks along the end effector (+X in its frame, with +Z up), so the grapple fixture grows in the picture as the end effector closes in
        eye = np.array((END_EFFECTOR.LENGTH - ARM.camera.SETBACK, 0, ARM.camera.HEIGHT))
        camera = mojo.Camera(
            name=mojo.CameraName("arm_camera"),
            fovy=ARM.camera.FOVY,
            pose=mojo.PoseQuat.look_at(
                target=eye + np.array((1, 0, 0)), eye=eye, roll=-90
            ),
        )
        free_effector.frame.cameras.append(camera)
        wrist_roll = hinge("wrist_roll", (1, 0, 0))
        wrist_roll_body.joints.append(wrist_roll)
        wrist_yaw_body.bodies.append(wrist_roll_body)

        # the shoulder hangs off the fixture, which is in the station's body, so it is fixed to the station
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
            reach=reach,
            camera=camera,
            servos=[],
        )

        # one position servo per joint, in the order of `joints`, each referring to its joint by its name: the control value is the angle to hold, in radians, and the servo pulls the joint toward it with a spring (`KP`) and a damper (`KV`)
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

        return arm


# --8<-- [end:arm]
