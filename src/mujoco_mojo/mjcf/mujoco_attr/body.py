from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

import mujoco
import numpy as np
from pydantic import Field

from mujoco_mojo.mjcf.meta.frame import Frame
from mujoco_mojo.mjcf.mujoco_attr.body_attr.attach import Attach
from mujoco_mojo.mjcf.mujoco_attr.body_attr.camera import Camera
from mujoco_mojo.mjcf.mujoco_attr.body_attr.composite import Composite
from mujoco_mojo.mjcf.mujoco_attr.body_attr.flexcomp import FlexComp
from mujoco_mojo.mjcf.mujoco_attr.body_attr.free_joint import FreeJoint
from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import AnyGeom
from mujoco_mojo.mjcf.mujoco_attr.body_attr.inertial import Inertial
from mujoco_mojo.mjcf.mujoco_attr.body_attr.joint import Joint
from mujoco_mojo.mjcf.mujoco_attr.body_attr.light import Light
from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import AnySite
from mujoco_mojo.mjcf.plugin import Plugin
from mujoco_mojo.mjcf.pose import AnyPose, PoseQuat
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import (
    Angle,
    BodyName,
    Mat3,
    SignalCategory,
    Sleep,
    Vec3,
    Vec4,
    Vec6,
    VecN,
)
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.utils import is_empty_list

if TYPE_CHECKING:
    from mujoco_mojo.runtime.signal_manager import SignalManager

logger = get_logger(__name__)

__all__ = ["Body", "WorldBody"]

_body_attr = (
    "name",
    "childclass",
    "pose",
    "mocap",
    "gravcomp",
    "sleep",
    "user",
)
_body_children = (
    "inertial",
    "joints",
    "freejoints",
    "geoms",
    "sites",
    "cameras",
    "lights",
    "composites",
    "flexcomps",
    "plugins",
    "attaches",
    "frames",
    "bodies",
)


class Body(XMLModel):
    """This element is used to construct the kinematic tree via nesting. The element worldbody is used for the top-level body, while the element body is used for all other bodies. The top-level body is a restricted type of body: it cannot have child elements inertial and joint, and also cannot have any attributes. It corresponds to the origin of the world frame, within which the rest of the kinematic tree is defined. Its body name is automatically defined as "world"."""

    tag = "body"

    attributes = _body_attr
    children = _body_children

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_BODY

    name: BodyName | None = None
    """Name of the body."""

    childclass: str | None = None
    """If this attribute is present, all descendant elements that admit a defaults class will use the class specified here, unless they specify their own class or another body or frame with a childclass attribute is encountered along the chain of nested bodies and frames. Recall Default settings."""

    mocap: bool = False
    """If this attribute is "true", the body is labeled as a mocap body. This is allowed only for bodies that are children of the world body and have no joints. Such bodies are fixed from the viewpoint of the dynamics, but nevertheless the forward kinematics set their position and orientation from the fields mjData.mocap_{pos,quat} at each time step. The size of these arrays is adjusted by the compiler so as to match the number of mocap bodies in the model. This mechanism can be used to stream motion capture data into the simulation. Mocap bodies can also be moved via mouse perturbations in the interactive visualizer, even in dynamic simulation mode. This can be useful for creating props with adjustable position and orientation."""

    pose: AnyPose = PoseQuat()
    """The 3D position and orientation of the body frame, in the parent coordinate frame. If undefined it defaults to (0,0,0)."""

    gravcomp: float = 0
    """Gravity compensation force, specified as fraction of body weight. This attribute creates an upwards force applied to the body's center of mass, countering the force of gravity. As an example, a value of 1 creates an upward force equal to the body's weight and compensates for gravity exactly. Values greater than 1 will create a net upwards force or buoyancy effect."""

    sleep: Sleep = Sleep.AUTO
    """Sleep policy for the tree under this body. This attribute is only supported by moving bodies which are the root of a kinematic tree. For the default auto, the compiler will set the sleep policy as follows:

    - A tree which is affected by actuators is not allowed to sleep (overridable).
    - Trees which are connected by tendons which have non-zero stiffness and damping are not allowed to sleep (overridable).
    - Trees which are connected by tendons which connect more than two trees are not allowed to sleep (not overridable).
    - flexes are not allowed to sleep (not overridable).
    - All other trees are allowed to sleep (overridable).

    The policies never and allowed constitute user overrides of the automatic compiler policy.

    The init sleep policy can only be specified by the user and means "initialize this tree as asleep". This policy is implemented in mj_resetData and mj_makeData and only applies to the default configuration. If a keyframe changes the configuration of (or assigns nonzero velocity to) a sleeping tree, it will be woken up. This policy is useful for very large models where waiting for the automatic sleeping mechanism to kick in can be expensive. Trees initialized as sleeping can be placed in unstable configurations like deep penetration or in mid-air, but will only move when woken up. Also note that this policy can fail. For example if a tree marked as sleep="init" is in contact with a tree not marked as such (i.e., they are in the same island) then it is impossible to put the tree to sleep; such models will lead to a compilation error.

    See implementation notes for more details."""

    user: VecN | None = None
    """See User parameters. Has length of `nbody_user`"""

    inertial: Inertial | None = None
    """Inertial assigned to body."""

    joints: list[Joint] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Joints assigned to body."""

    freejoints: list[FreeJoint] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Free joints assigned to body. Defining more than one free joint will not do anything"""

    geoms: list[AnyGeom] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Geometries assigned to body."""

    sites: list[AnySite] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Sites assigned to body."""

    cameras: list[Camera] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Cameras assigned to body."""

    lights: list[Light] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Lights assigned to body."""

    composites: list[Composite] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Composites assigned to body."""

    flexcomps: list[FlexComp] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Flexible composites assigned to body."""

    plugins: list[Plugin] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Plugins assigned to body."""

    attaches: list[Attach] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Attach elements assigned to body."""

    frames: list[Frame] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Frames assigned to body."""

    bodies: list[Body] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Bodies assigned to body. Handled recursively."""

    def walk_bodies(self, include_self: bool = False) -> list[Body]:
        """
        Recursively traverses the kinematic tree to retrieve all descendant bodies.

        This method performs a depth-first search (DFS) through the nested body hierarchy. It is particularly useful when called from the `worldbody` to get a flattened list of all physical entities in the simulation without including the world origin.

        Args:
            include_self (bool, optional): If True, the current body is included as the first element in the returned list. Defaults to False.

        Returns:
            list[Body]: A flattened list of all descendant Body objects, ordered by their depth in the kinematic tree.

        """
        bodies: list[Body] = [self] if include_self else []

        for child in self.bodies:
            bodies.extend(child.walk_bodies(include_self=True))

        return bodies

    def rt_mass(self, mj_model: mujoco.MjModel) -> float:
        """Mass of the body from a compiled MjModel."""
        return mj_model.body_mass[self.get_id(mj_model)]

    def rt_xmat(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData, flatten: bool = False
    ) -> Mat3:
        """Rotation matrix the body during runtime."""
        return (
            mj_data.xmat[self.get_id(mj_model)]
            if flatten
            else mj_data.xmat[self.get_id(mj_model)].reshape(3, 3)
        )

    def rt_quat(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec4:
        """
        Returns the (w, x, y, z) quaternion from the body's rotation matrix.
        Uses MuJoCo's internal C utility for speed.
        """
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, self.rt_xmat(mj_model, mj_data, flatten=True))
        return quat

    def rt_inertia_diag(self, mj_model: mujoco.MjModel) -> Vec3:
        """Diagonalized inertia tensor of the body (body relative)."""
        return mj_model.body_inertia[self.get_id(mj_model)]

    def rt_inertia_world(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> Mat3:
        """Inertia tensor of the body expressed in the world frame."""
        R = self.rt_ximat(mj_model, mj_data)
        I_diag = np.diag(self.rt_inertia_diag(mj_model))
        return R @ I_diag @ R.T

    def rt_parent_body_id(self, mj_model: mujoco.MjModel) -> int:
        """Parent ID of the body."""
        return mj_model.body_parentid[self.get_id(mj_model)]

    def rt_pos(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        """Position of the body during runtime."""
        return mj_data.xpos[self.get_id(mj_model)]

    def rt_spatial_vel(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec6:
        """Returns the 6D spatial velocity (ang, lin) at the CoM in world frame."""
        return mj_data.cvel[self.get_id(mj_model)]

    def rt_lin_vel(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        """Linear velocity of the body center of mass during runtime in the world frame."""
        return self.rt_spatial_vel(mj_model, mj_data)[3:6]

    def rt_ang_vel(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        """Angular velocity of the body center of mass during runtime  in the world frame."""
        return self.rt_spatial_vel(mj_model, mj_data)[0:3]

    def rt_lin_mom(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        """Linear momentum of the body during runtime."""
        return self.rt_mass(mj_model) * self.rt_lin_vel(mj_model, mj_data)

    def rt_ang_mom(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        """Angular momentum of the body during runtime."""
        return self.rt_inertia_world(mj_model, mj_data) @ self.rt_ang_vel(
            mj_model, mj_data
        )

    def rt_pe(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        ref_point: Vec3 | Pos | AnyPose = np.array((0, 0, 0)),
    ) -> float:
        g = mj_model.opt.gravity

        # early exit if gravity is off
        if g.sum() == 0:
            return 0

        mass = self.rt_mass(mj_model)

        # calculate datum to center of mass
        h_rel = self.rt_xipos(mj_model, mj_data) - np.asarray(ref_point)
        return -mass * np.dot(g, h_rel)

    def rt_trans_ke(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> float:
        """Translational kinetic energy of the body during runtime."""
        mass = self.rt_mass(mj_model)
        v = self.rt_lin_vel(mj_model, mj_data)
        return 0.5 * mass * np.dot(v, v)

    def rt_rot_ke(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> float:
        """Rotational kinetic energy of the body during runtime."""
        omega = self.rt_ang_vel(mj_model, mj_data)
        I_world = self.rt_inertia_world(mj_model, mj_data)
        return 0.5 * np.dot(omega, I_world @ omega)

    def rt_ke(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> float:
        """Total kinetic energy of the body during runtime."""
        return self.rt_trans_ke(mj_model, mj_data) + self.rt_rot_ke(mj_model, mj_data)

    def rt_xipos(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        """Position of the body inertial frame during runtime."""
        return mj_data.xipos[self.get_id(mj_model)]

    def rt_ximat(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData, flatten: bool = False
    ) -> Mat3:
        """Rotation matrix the body during runtime."""
        return (
            mj_data.ximat[self.get_id(mj_model)]
            if flatten
            else mj_data.ximat[self.get_id(mj_model)].reshape(3, 3)
        )

    def rt_xiquat(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec4:
        """
        Returns the (w, x, y, z) quaternion from the body's inertial rotation matrix.
        Uses MuJoCo's internal C utility for speed.
        """
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, self.rt_ximat(mj_model, mj_data, flatten=True))
        return quat

    def request(
        self,
        signal_manager: SignalManager,
        attrs: list[
            Literal[
                "xpos",
                "quat",
                "xmat",
                "xvelp",
                "xvelr",
                "lin_mom",
                "xipos",
                "xiquat",
                "ximat",
                "ang_mom",
                "ke_trans",
                "ke_rot",
                "pe",
                "ke_total",
                "total_energy",
            ]
        ] = [
            "xvelp",
            "xvelr",
            "xipos",
            "xiquat",
            "lin_mom",
            "ang_mom",
            "ke_trans",
            "ke_rot",
            "pe",
            "ke_total",
        ],
    ):
        """Registers specific site attributes for logging. Requires a named site."""
        if self.name is None:
            msg = f"Cannot request telemetry for an unnamed {self.tag}. Please assign a 'name' to the site before requesting outputs."
            logger.error(msg)
            raise ValueError(msg)

        def sample(mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
            for attr in attrs:
                match attr:
                    case "xpos":
                        val = self.rt_pos(mj_model, mj_data)
                    case "xmat" | "ximat":
                        match attr:
                            case "xmat":
                                val = self.rt_xmat(mj_model, mj_data, flatten=True)
                            case "ximat":
                                val = self.rt_ximat(mj_model, mj_data, flatten=True)

                        for i in range(len(val)):
                            signal_manager.post(
                                value=float(val[i]),
                                category=SignalCategory.BODIES,
                                subgroups=(f"{self.name}", attr),
                                attr=str(i),
                            )
                        continue
                    case "quat" | "xiquat":
                        match attr:
                            case "quat":
                                val = self.rt_quat(mj_model, mj_data)
                            case "xiquat":
                                val = self.rt_xiquat(mj_model, mj_data)

                        for i, k in enumerate("wxyz"):
                            signal_manager.post(
                                value=float(val[i]),
                                category=SignalCategory.BODIES,
                                subgroups=(f"{self.name}", attr),
                                attr=k,
                            )
                        continue
                    case "xvelp":
                        val = self.rt_lin_vel(mj_model, mj_data)
                    case "xvelr":
                        val = self.rt_ang_vel(mj_model, mj_data)
                    case "xipos":
                        val = self.rt_xipos(mj_model, mj_data)
                    case "lin_mom":
                        val = self.rt_lin_mom(mj_model, mj_data)
                    case "ang_mom":
                        val = self.rt_ang_mom(mj_model, mj_data)
                    case "pe":
                        val = self.rt_pe(mj_model, mj_data)
                    case "ke_trans":
                        val = self.rt_trans_ke(mj_model, mj_data)
                    case "ke_rot":
                        val = self.rt_rot_ke(mj_model, mj_data)
                    case "ke_total":
                        val = self.rt_ke(mj_model, mj_data)
                    case "total_energy":
                        val = self.rt_ke(mj_model, mj_data) + self.rt_pe(
                            mj_model, mj_data
                        )
                    case _:
                        continue

                if isinstance(val, np.ndarray):
                    # vector output (x, y, z + magnitude)
                    mag = np.linalg.norm(val)
                    full_vec = np.append(val, mag)

                    for i, k in enumerate("xyzm"):
                        signal_manager.post(
                            value=full_vec[i],
                            category=SignalCategory.BODIES,
                            subgroups=(f"{self.name}", attr),
                            attr=k,
                        )
                else:
                    # scalar output
                    signal_manager.post(
                        value=float(val),
                        category=SignalCategory.BODIES,
                        subgroups=(f"{self.name}", attr),
                        attr=attr,
                    )

        signal_manager.register_sampler(sample)

    def set_initial_velocity(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        linear_velocity: Vec3 = np.zeros(3),
        angular_velocity: Vec3 = np.zeros(3),
        angle: Angle = Angle.RADIAN,
        reference: AnyPose = PoseQuat(),
    ) -> None:
        """
        Sets the initial velocity (qvel) for a body with a free joint.

        This method applies a rigid body velocity mapping. If the velocity is defined at a specific point in space (e.g., the center of a rotating system), this calculates the resulting linear velocity at the body's actual position.

        Calculates:
            >>> v_world = R_ref @ v_local

            >>> w_world = R_ref @ w_local

            >>> v_body = v_world + w_world x (r_body - r_ref)

        Args:
            mj_model (mujoco.MjModel): The compiled MuJoCo model.
            mj_data (mujoco.MjData): The MuJoCo data state to modify.
            linear_velocity (Vec3): Linear velocity vector [x, y, z]. Expressed in the reference frame. Defaults to np.zeros(3).
            angular_velocity (Vec3): Angular velocity vector [wx, wy, wz]. Defaults to np.zeros(3).
            angle (Angle, optional): Type of angle measurement angular_velocity is expressed in. Defaults to Angle.RADIAN.
            reference (Pose, optional): The global pose where the velocities is defined (this Pose is expressed in the world frame). Defaults to PoseQuat().

        Raises:
            ValueError: If the body does not have a free joint.

        """
        if not self.freejoints:
            logger.warning(
                "Attempting to set initial velocity conditions for a body which does not have a free joint."
            )

        # convert from deg to rad
        w_input = np.asarray(angular_velocity, dtype=float)
        if angle == Angle.DEGREE:
            w_input = np.deg2rad(w_input)

        # coordinate transformation
        r_mat = reference.as_matrix()
        v_ref_world = r_mat @ np.asarray(linear_velocity, dtype=float)
        w_world = r_mat @ w_input

        # translate the velocity to the body origin
        r_body_world = self.rt_pos(mj_model, mj_data)
        r_ref_world = reference.pos

        v_body_linear = v_ref_world + np.cross(w_world, (r_body_world - r_ref_world))

        # apply to mj_data.qvel
        bid = self.get_id(mj_model)
        jnt_adr = mj_model.body_jntadr[bid]
        qvel_adr = mj_model.jnt_dofadr[jnt_adr]

        mj_data.qvel[qvel_adr : qvel_adr + 3] = v_body_linear
        mj_data.qvel[qvel_adr + 3 : qvel_adr + 6] = w_world


_temp_list = list(_body_children)
for not_in in ("inertial", "joints"):
    _temp_list.remove(not_in)
_world_body_children = tuple(_temp_list)


class WorldBody(Body):
    """This element is used to construct the kinematic tree via nesting. The element worldbody is used for the top-level body, while the element body is used for all other bodies. The top-level body is a restricted type of body: it cannot have child elements inertial and joint, and also cannot have any attributes. It corresponds to the origin of the world frame, within which the rest of the kinematic tree is defined. Its body name is automatically defined as "world"."""

    tag = "worldbody"

    attributes = ()
    children = _world_body_children

    @staticmethod
    def get_com(
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        bodies: list[Body],
    ) -> tuple[float, np.ndarray]:
        """Calculates the combined center of mass in world coordniates for multiple bodies."""
        total_mass = 0.0
        weighted_pos = np.zeros(3)

        for body in bodies:
            bid = body.get_id(mj_model)

            m = mj_model.body_mass[bid]
            p = mj_data.xipos[bid]

            total_mass += m
            weighted_pos += m * p

        return total_mass, weighted_pos / total_mass if total_mass > 0 else np.zeros(3)
