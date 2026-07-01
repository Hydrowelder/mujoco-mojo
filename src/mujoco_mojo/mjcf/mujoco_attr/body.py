from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

import mujoco
import numpy as np
from pydantic import Field

from mujoco_mojo.mj_state import MjState
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
from mujoco_mojo.utils.signal_metadata import (
    Dimension,
    angular_rate_metadata,
    dim,
    dimensionless_metadata,
    merge_signal_metadata,
)
from mujoco_mojo.utils.utils import is_empty_list

if TYPE_CHECKING:
    from mujoco_mojo.runtime.signal_manager import SignalManager

logger = get_logger(__name__)

__all__ = ["Body", "WorldBody"]

_REQUEST_CHANNEL_METADATA: dict[str, dict[str, str]] = {
    "xpos": dim(Dimension.LENGTH),
    "quat": dimensionless_metadata(),
    "xmat": dimensionless_metadata(),
    "xvelp": dim(Dimension.VELOCITY),
    "xvelr": angular_rate_metadata(),
    "xaccp": dim(Dimension.ACCELERATION),
    "xaccr": angular_rate_metadata(per="second ** 2"),
    "xipos": dim(Dimension.LENGTH),
    "xiquat": dimensionless_metadata(),
    "ximat": dimensionless_metadata(),
    "lin_mom": dim(Dimension.LINEAR_MOMENTUM),
    "ang_mom": dim(Dimension.ANGULAR_MOMENTUM),
    "ke_trans": dim(Dimension.ENERGY),
    "ke_rot": dim(Dimension.ENERGY),
    "pe": dim(Dimension.ENERGY),
    "ke_total": dim(Dimension.ENERGY),
    "total_energy": dim(Dimension.ENERGY),
}

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

    def rt_mass(self, state: MjState) -> float:
        """Mass of the body from a compiled MjModel."""
        return state.model.body_mass[self.get_id(state.model)]

    def rt_xmat(self, state: MjState, flatten: bool = False) -> Mat3:
        """Rotation matrix the body during runtime."""
        return (
            state.data.xmat[self.get_id(state.model)]
            if flatten
            else state.data.xmat[self.get_id(state.model)].reshape(3, 3)
        )

    def rt_quat(self, state: MjState) -> Vec4:
        """
        Returns the (w, x, y, z) quaternion from the body's rotation matrix.
        Uses MuJoCo's internal C utility for speed.
        """
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, self.rt_xmat(state, flatten=True))
        return quat

    def rt_inertia_diag(self, state: MjState) -> Vec3:
        """Diagonalized inertia tensor of the body (body relative)."""
        return state.model.body_inertia[self.get_id(state.model)]

    def rt_inertia_world(self, state: MjState) -> Mat3:
        """Inertia tensor of the body expressed in the world frame."""
        R = self.rt_ximat(state)
        I_diag = np.diag(self.rt_inertia_diag(state))
        return R @ I_diag @ R.T

    def rt_parent_body_id(self, state: MjState) -> int:
        """Parent ID of the body."""
        return state.model.body_parentid[self.get_id(state.model)]

    def rt_pos(self, state: MjState) -> Vec3:
        """Position of the body during runtime."""
        return state.data.xpos[self.get_id(state.model)]

    def rt_spatial_vel(self, state: MjState) -> Vec6:
        """Returns the 6D spatial velocity (ang, lin) at the CoM in world frame."""
        return state.data.cvel[self.get_id(state.model)]

    def rt_lin_vel(self, state: MjState) -> Vec3:
        """Linear velocity of the body center of mass during runtime in the world frame."""
        return self.rt_spatial_vel(state)[3:6]

    def rt_ang_vel(self, state: MjState) -> Vec3:
        """Angular velocity of the body center of mass during runtime  in the world frame."""
        return self.rt_spatial_vel(state)[0:3]

    def rt_spatial_acc(self, state: MjState) -> Vec6:
        """
        Returns the 6D spatial acceleration (ang, lin) at the body CoM in the world frame.

        Requires `mj_rnePostConstraint` to have run; calls `state.ensure_rne_post_constraint()` before reading so the result is always current.
        """
        assert self._mjt_obj is not None
        state.ensure_rne_post_constraint()
        res = np.zeros(6)
        mujoco.mj_objectAcceleration(
            state.model, state.data, self._mjt_obj, self.get_id(state.model), res, 0
        )
        return res

    def rt_lin_acc(self, state: MjState) -> Vec3:
        """Linear acceleration of the body CoM during runtime in the world frame."""
        return self.rt_spatial_acc(state)[3:6]

    def rt_ang_acc(self, state: MjState) -> Vec3:
        """Angular acceleration of the body CoM during runtime in the world frame."""
        return self.rt_spatial_acc(state)[0:3]

    def rt_lin_mom(self, state: MjState) -> Vec3:
        """Linear momentum of the body during runtime."""
        return self.rt_mass(state) * self.rt_lin_vel(state)

    def rt_ang_mom(self, state: MjState) -> Vec3:
        """Angular momentum of the body during runtime."""
        return self.rt_inertia_world(state) @ self.rt_ang_vel(state)

    def rt_pe(
        self,
        state: MjState,
        ref_point: Vec3 | Pos | AnyPose = np.array((0, 0, 0)),
    ) -> float:
        g = state.model.opt.gravity

        # early exit if gravity is off
        if g.sum() == 0:
            return 0

        mass = self.rt_mass(state)

        # calculate datum to center of mass
        h_rel = self.rt_xipos(state) - np.asarray(ref_point)
        return -mass * np.dot(g, h_rel)

    def rt_trans_ke(self, state: MjState) -> float:
        """Translational kinetic energy of the body during runtime."""
        mass = self.rt_mass(state)
        v = self.rt_lin_vel(state)
        return 0.5 * mass * np.dot(v, v)

    def rt_rot_ke(self, state: MjState) -> float:
        """Rotational kinetic energy of the body during runtime."""
        omega = self.rt_ang_vel(state)
        I_world = self.rt_inertia_world(state)
        return 0.5 * np.dot(omega, I_world @ omega)

    def rt_ke(self, state: MjState) -> float:
        """Total kinetic energy of the body during runtime."""
        return self.rt_trans_ke(state) + self.rt_rot_ke(state)

    def rt_xipos(self, state: MjState) -> Vec3:
        """Position of the body inertial frame during runtime."""
        return state.data.xipos[self.get_id(state.model)]

    def rt_ximat(self, state: MjState, flatten: bool = False) -> Mat3:
        """Rotation matrix the body during runtime."""
        return (
            state.data.ximat[self.get_id(state.model)]
            if flatten
            else state.data.ximat[self.get_id(state.model)].reshape(3, 3)
        )

    def rt_xiquat(self, state: MjState) -> Vec4:
        """
        Returns the (w, x, y, z) quaternion from the body's inertial rotation matrix.
        Uses MuJoCo's internal C utility for speed.
        """
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, self.rt_ximat(state, flatten=True))
        return quat

    def request(
        self,
        signal_manager: SignalManager | None = None,
        channels: list[
            Literal[
                "xpos",
                "quat",
                "xmat",
                "xvelp",
                "xvelr",
                "xaccp",
                "xaccr",
                "xipos",
                "xiquat",
                "ximat",
                "lin_mom",
                "ang_mom",
                "ke_trans",
                "ke_rot",
                "pe",
                "ke_total",
                "total_energy",
            ]
        ]
        | dict[
            Literal[
                "xpos",
                "quat",
                "xmat",
                "xvelp",
                "xvelr",
                "xaccp",
                "xaccr",
                "xipos",
                "xiquat",
                "ximat",
                "lin_mom",
                "ang_mom",
                "ke_trans",
                "ke_rot",
                "pe",
                "ke_total",
                "total_energy",
            ],
            dict[str, Any] | None,
        ] = [
            "xpos",
            "quat",
            "xvelp",
            "xvelr",
            "xaccp",
            "xaccr",
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
        """
        Registers specific channels for logging.

        | Channel        | Description                                         | Type   |
        |:---------------|:----------------------------------------------------|:-------|
        | `xpos`         | world position of the body                          | xyzm   |
        | `quat`         | world orientation quaternion                        | quat   |
        | `xmat`         | world rotation matrix                               | mat9   |
        | `xvelp`        | linear velocity in world frame                      | xyzm   |
        | `xvelr`        | angular velocity in world frame                     | xyzm   |
        | `xaccp`        | linear acceleration in world frame                  | xyzm   |
        | `xaccr`        | angular acceleration in world frame                 | xyzm   |
        | `xipos`        | world position of the center of mass                | xyzm   |
        | `xiquat`       | world orientation quaternion of the inertial frame  | quat   |
        | `ximat`        | world rotation matrix of the inertial frame         | mat9   |
        | `lin_mom`      | linear momentum                                     | xyzm   |
        | `ang_mom`      | angular momentum                                    | xyzm   |
        | `ke_trans`     | translational kinetic energy                        | scalar |
        | `ke_rot`       | rotational kinetic energy                           | scalar |
        | `pe`           | potential energy                                    | scalar |
        | `ke_total`     | total kinetic energy                                | scalar |
        | `total_energy` | total kinetic and potential energy                  | scalar |

        Each channel is posted under `subgroups=(body_name, channel)`.

        * An `xyzm` is a cartesian vector, posted as 4 values (`x`, `y`, `z`, and its magnitude `m`).
        * A `mat9` is a flattened 3x3 matrix, posted as 9 values with `attr` set to `0`-`8`.
        * A `quat` is an orientation quaternion, posted as 4 values (`w`, `x`, `y`, `z`).
        * A `scalar` is posted as a single value with `attr=channel` under `subgroups=(body_name,)`.

        Each signal is tagged with built-in `dimension`/`units` metadata for its channel (e.g. `xpos` is tagged as a length, `lin_mom` as linear momentum).

        If `signal_manager` is omitted, the `SignalManager` of the active `RuntimeManager` `with` block is used. If that `RuntimeManager` has no `SignalManager` configured, this is a no-op.

        Args:
            signal_manager: The signal manager to register the sampler with.
            channels: The body data channels to log. Pass a list to select channels, or a dict mapping channel name to metadata overrides (or `None`) to select channels and attach per-channel metadata in one step.

        """
        from mujoco_mojo.runtime.signal_manager import resolve_signal_manager

        signal_manager = resolve_signal_manager(signal_manager)
        if signal_manager is None:
            return

        if self.name is None:
            msg = f"Cannot request telemetry for an unnamed {self.tag}. Please assign a 'name' to the site before requesting outputs."
            logger.error(msg)
            raise ValueError(msg)

        if isinstance(channels, dict):
            _meta = cast("dict[str, dict[str, Any] | None]", channels)
            channels = list(channels.keys())
        else:
            _meta = {}

        def sample(state: MjState):
            for channel in channels:
                meta = merge_signal_metadata(
                    _REQUEST_CHANNEL_METADATA.get(channel),
                    channel,
                    _meta,
                    units=state.units,
                )

                match channel:
                    case "xpos":
                        val = self.rt_pos(state)
                    case "xmat" | "ximat":
                        match channel:
                            case "xmat":
                                val = self.rt_xmat(state, flatten=True)
                            case "ximat":
                                val = self.rt_ximat(state, flatten=True)

                        for i in range(len(val)):
                            signal_manager.post(
                                value=float(val[i]),
                                category=SignalCategory.BODIES,
                                subgroups=(f"{self.name}", channel),
                                attr=str(i),
                                metadata=meta,
                            )
                        continue
                    case "quat" | "xiquat":
                        match channel:
                            case "quat":
                                val = self.rt_quat(state)
                            case "xiquat":
                                val = self.rt_xiquat(state)

                        for i, attr in enumerate("wxyz"):
                            signal_manager.post(
                                value=float(val[i]),
                                category=SignalCategory.BODIES,
                                subgroups=(f"{self.name}", channel),
                                attr=attr,
                                metadata=meta,
                            )
                        continue
                    case "xvelp":
                        val = self.rt_lin_vel(state)
                    case "xvelr":
                        val = self.rt_ang_vel(state)
                    case "xaccp":
                        val = self.rt_lin_acc(state)
                    case "xaccr":
                        val = self.rt_ang_acc(state)
                    case "xipos":
                        val = self.rt_xipos(state)
                    case "lin_mom":
                        val = self.rt_lin_mom(state)
                    case "ang_mom":
                        val = self.rt_ang_mom(state)
                    case "pe":
                        val = self.rt_pe(state)
                    case "ke_trans":
                        val = self.rt_trans_ke(state)
                    case "ke_rot":
                        val = self.rt_rot_ke(state)
                    case "ke_total":
                        val = self.rt_ke(state)
                    case "total_energy":
                        val = self.rt_ke(state) + self.rt_pe(state)
                    case _:
                        continue

                if isinstance(val, np.ndarray):
                    # vector output (x, y, z + magnitude)
                    mag = np.linalg.norm(val)
                    full_vec = np.append(val, mag)

                    for i, attr in enumerate("xyzm"):
                        signal_manager.post(
                            value=full_vec[i],
                            category=SignalCategory.BODIES,
                            subgroups=(f"{self.name}", channel),
                            attr=attr,
                            metadata=meta,
                        )
                else:
                    # scalar output
                    signal_manager.post(
                        value=float(val),
                        category=SignalCategory.BODIES,
                        subgroups=(f"{self.name}",),
                        attr=channel,
                        metadata=meta,
                    )

        signal_manager.register_sampler(sample)

    def set_initial_velocity(
        self,
        state: MjState,
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
            state: The paired MuJoCo model and data state to modify.
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
        r_body_world = self.rt_pos(state)
        r_ref_world = reference.pos

        v_body_linear = v_ref_world + np.cross(w_world, (r_body_world - r_ref_world))

        # apply to state.data.qvel
        bid = self.get_id(state.model)
        jnt_adr = state.model.body_jntadr[bid]
        qvel_adr = state.model.jnt_dofadr[jnt_adr]

        state.data.qvel[qvel_adr : qvel_adr + 3] = v_body_linear
        state.data.qvel[qvel_adr + 3 : qvel_adr + 6] = w_world


_temp_list = list(_body_children)
for not_in in ("inertial", "joints"):
    _temp_list.remove(not_in)
_world_body_children = tuple(_temp_list)


class WorldBody(Body):
    """This element is used to construct the kinematic tree via nesting. The element worldbody is used for the top-level body, while the element body is used for all other bodies. The top-level body is a restricted type of body: it cannot have child elements inertial and joint, and also cannot have any attributes. It corresponds to the origin of the world frame, within which the rest of the kinematic tree is defined. Its body name is automatically defined as "world"."""

    tag = "worldbody"

    attributes = ()
    children = _world_body_children

    # per the class docstring, the top-level body cannot have any attributes
    # or the inertial/joints child elements
    non_xml_fields = (*_body_attr, "inertial", "joints")

    @staticmethod
    def get_com(
        state: MjState,
        bodies: list[Body],
    ) -> tuple[float, np.ndarray]:
        """Calculates the combined center of mass in world coordniates for multiple bodies."""
        total_mass = 0.0
        weighted_pos = np.zeros(3)

        for body in bodies:
            bid = body.get_id(state.model)

            m = state.model.body_mass[bid]
            p = state.data.xipos[bid]

            total_mass += m
            weighted_pos += m * p

        return total_mass, weighted_pos / total_mass if total_mass > 0 else np.zeros(3)
