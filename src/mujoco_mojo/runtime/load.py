from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal, Self

import mujoco
import numpy as np
from pydantic import PrivateAttr, SerializeAsAny, model_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.body import Body
from mujoco_mojo.mjcf.mujoco_attr.body_attr.joint import Joint
from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import AnySite
from mujoco_mojo.mojo_model import UserData
from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.settings import MujocoMojoSettings, VisualizationSettings
from mujoco_mojo.stochas import NamedValue
from mujoco_mojo.typing import SignalCategory, Vec3, Vec4
from mujoco_mojo.utils.color import Color
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.visualization import ArrowConfig

if TYPE_CHECKING:
    from mujoco_mojo.runtime.runtime_manager import RuntimeManager

logger = get_logger(__name__)


def _ideal_force_logic(
    dist: float,
    vel: float,
    stiffness: float | NamedValue[float],
    damping: float | NamedValue[float],
    rest_length: float,
) -> float:
    """Core restorative force calculation (F = -k*dx - c*v)."""
    k = stiffness.value if isinstance(stiffness, NamedValue) else stiffness
    c = damping.value if isinstance(damping, NamedValue) else damping

    # Standard restorative magnitude
    return -1.0 * (k * (dist - rest_length) + c * vel)


class Load(MojoBaseModel, ABC):
    """Abstract base for Cartesian-space forcing functions applied at a named site. Subclass and implement `calculate()` to return (force_world, torque_world); the base class handles `mj_applyFT`, telemetry, and visualization."""

    name: str
    """Unique label used for telemetry column naming and duplicate-registration warnings."""

    active: bool = True
    """When False the load writes zeros and clears its last-frame cache."""

    action_site: AnySite
    """Site where the force is applied. Its parent body receives the generalized force."""

    rel_to_site: AnySite | None = None
    """Coordinate frame for force/torque components returned by `calculate()`. When None, components are in the world frame."""

    user_data: SerializeAsAny[UserData] | None = None
    """Optional strongly-typed payload accessible inside `calculate()`. Passed through unchanged each timestep."""

    _last_f: Vec4 = PrivateAttr(default_factory=lambda: np.zeros(4))
    """Previous timestep's force values. Used for request management."""

    _last_t: Vec4 = PrivateAttr(default_factory=lambda: np.zeros(4))
    """Previous timestep's torque values. Used for request management."""

    _vis: VisualizationSettings = PrivateAttr(default_factory=VisualizationSettings)
    """Visualization color settings, loaded from user settings on resolve."""

    def handle_inactive(self):
        # [3] is magnitude
        if not np.isclose(0, self._last_f[3] + self._last_t[3]):
            self._last_f = np.zeros(4)
            self._last_t = np.zeros(4)

    def resolve_ids(self, state: MjState):
        """Caches the integer IDs from the compiled MuJoCo model."""
        self._vis = MujocoMojoSettings().visualization
        self.action_site.get_id(state.model)

        if self.rel_to_site:
            self.rel_to_site.get_id(state.model)

    def _get_world_vectors(self, state: MjState, local: Vec3) -> Vec3:
        """Rotates local force/torque into world coordinates based on relative_to."""
        if self.rel_to_site is None:
            return local

        return self.rel_to_site.rt_xmat(state) @ local

    @abstractmethod
    def calculate(self, state: MjState) -> tuple[np.ndarray, np.ndarray]:
        """
        Calculate the force for the timestep.

        Args:
            state: The paired MuJoCo model and data instance.

        Returns:
            tuple[np.ndarray, np.ndarray]: The force and toque vector output.

        """

    def register_to_rm(self, runtime_manager: RuntimeManager) -> Self:
        runtime_manager.add_load(self)
        return self

    def apply_load(self, state: MjState):
        if not self.active:
            self.handle_inactive()
            return

        f_world, t_world = self.calculate(state)
        self._last_f[:3] = f_world
        self._last_f[3] = np.linalg.norm(f_world)
        self._last_t[:3] = t_world
        self._last_t[3] = np.linalg.norm(t_world)

        # apply to action site
        action_pos = self.action_site.rt_pos(state)
        action_bid = self.action_site.rt_parent_body(state)
        mujoco.mj_applyFT(
            m=state.model,
            d=state.data,
            force=f_world,
            torque=t_world,
            point=action_pos,
            body=action_bid,
            # target generalized force array
            qfrc_target=state.data.qfrc_applied,
        )

    def request(
        self,
        signal_manager: SignalManager,
        attrs: list[Literal["force", "torque"]] = ["force", "torque"],
    ):
        def sample(state: MjState):
            for attr in attrs:
                source = self._last_f if attr == "force" else self._last_t

                # iterate through x, y, z, and magnitude (pop. pop.)
                for i, k in enumerate("xyzm"):
                    signal_manager.post(
                        value=float(source[i]) if self.active else 0.0,
                        category=SignalCategory.LOADS,
                        # nest the force/torque under the function name
                        subgroups=(f"{self.name}", attr),
                        attr=k,
                    )

        signal_manager.register_sampler(sample)

    def get_visuals(self, state: MjState) -> list[ArrowConfig]:
        """Returns a list of arrow configurations for the renderer."""
        if not self.active:
            return []

        visuals: list[ArrowConfig] = []
        action_pos = self.action_site.rt_pos(state)

        if self._last_f[3] > 1e-4 and self._vis.action_force:
            visuals.append(
                ArrowConfig(
                    pos=action_pos,
                    vec=self._last_f[:3],
                    color=Color[self._vis.action_force].rgba,
                    is_torque=False,
                )
            )

        if self._last_t[3] > 1e-4 and self._vis.torque:
            visuals.append(
                ArrowConfig(
                    pos=action_pos,
                    vec=self._last_t[:3],
                    color=Color[self._vis.torque].rgba,
                    is_torque=True,
                )
            )

        return visuals


class PointToPointForce(Load):
    """Scalar force along the line-of-sight between two sites, with an equal and opposite reaction on `xtion_site`. Use the class-method factories for standard spring formulations, or supply a custom `magnitude_func`."""

    xtion_site: AnySite
    """Site that receives the equal-and-opposite reaction force. Named `xtion` to avoid ambiguity with `rel_to_site`."""

    magnitude_func: Callable[[UserData | None, MjState], float]
    """Callable (user_data, state) -> signed force magnitude (N). Positive pushes sites apart."""

    _r0_mag: float = PrivateAttr(default=0.0)
    """Rest distance between the two sites, captured at `resolve_ids` time."""

    def resolve_ids(self, state: MjState):
        """Caches the integer IDs from the compiled MuJoCo model."""
        super().resolve_ids(state)
        self.xtion_site.get_id(state.model)
        self._r0_mag = self.action_site.rt_dm(self.xtion_site, state)
        on_resolve = getattr(self.magnitude_func, "on_resolve", None)
        if callable(on_resolve):
            on_resolve(self._r0_mag)

    @model_validator(mode="after")
    def _validate_frame(self) -> Self:
        if self.rel_to_site is not None:
            raise ValueError(
                f"PointToPointForce '{self.name}' cannot use 'rel_to_site'. It is natively defined by the line-of-sight between sites."
            )
        return self

    def apply_load(self, state: MjState):
        if not self.active:
            self.handle_inactive()
            return

        super().apply_load(state)

        f_world = self._last_f[:3]
        t_world = self._last_t[:3]

        xtion_pos = self.xtion_site.rt_pos(state)
        xtion_bid = self.xtion_site.rt_parent_body(state)

        mujoco.mj_applyFT(
            m=state.model,
            d=state.data,
            force=-f_world,
            torque=-t_world,
            point=xtion_pos,
            body=xtion_bid,
            qfrc_target=state.data.qfrc_applied,
        )

    def get_visuals(self, state: MjState) -> list[ArrowConfig]:
        """Returns a list of arrow configurations for the renderer."""
        if not self.active:
            return []

        visuals = super().get_visuals(state)

        if self._last_f[3] > 1e-4 and self._vis.reaction_force:
            xtion_pos = self.xtion_site.rt_pos(state)
            visuals.append(
                ArrowConfig(
                    pos=xtion_pos,
                    vec=-self._last_f[:3],
                    color=Color[self._vis.reaction_force].rgba,
                    is_torque=False,
                )
            )

        return visuals

    def calculate(self, state: MjState) -> tuple[np.ndarray, np.ndarray]:
        dr_world = self.action_site.rt_displacements(self.xtion_site, state)
        dist = float(np.linalg.norm(dr_world))
        unit_vec = dr_world / dist if dist > 1e-9 else np.zeros(3)

        f_mag = self.magnitude_func(self.user_data, state)

        return unit_vec * f_mag, np.zeros(3)

    @classmethod
    def ideal_spring(
        cls,
        name: str,
        action_site: AnySite,
        xtion_site: AnySite,
        stiffness: float | NamedValue[float] = 0.0,
        damping: float | NamedValue[float] = 0.0,
        rest_length: float = 0.0,
    ) -> Self:
        """Bidirectional spring-damper active in both tension and compression. `F = -k*(d - d0) - c*v`."""

        def logic(ud: UserData | None, state: MjState) -> float:
            dr = action_site.rt_displacements(xtion_site, state)
            dist = float(np.linalg.norm(dr))
            unit_vec = dr / dist if dist > 1e-9 else np.zeros(3)
            vel = float(
                np.dot(
                    action_site.rt_velocities(xtion_site, state)[3:6],
                    unit_vec,
                )
            )
            return _ideal_force_logic(dist, vel, stiffness, damping, rest_length)

        return cls(
            name=name,
            action_site=action_site,
            xtion_site=xtion_site,
            magnitude_func=logic,
        )

    @classmethod
    def stroke_compression_spring(
        cls,
        name: str,
        action_site: AnySite,
        xtion_site: AnySite,
        stiffness: float | NamedValue[float] = 0.0,
        damping: float | NamedValue[float] = 0.0,
        preload: float | NamedValue[float] = 0.0,
        max_stroke: float | NamedValue[float] = 0.1,
    ) -> Self:
        """Compression spring with a finite stroke; only active while the sites are compressed between rest and (rest + max_stroke). Useful for preloaded gas springs and mechanical end-stops."""

        class _Logic:
            def __init__(self) -> None:
                self._r0: float = 0.0

            def on_resolve(self, r0: float) -> None:
                self._r0 = r0

            def __call__(self, ud: UserData | None, state: MjState) -> float:
                dr = action_site.rt_displacements(xtion_site, state)
                dist = float(np.linalg.norm(dr))
                unit_vec = dr / dist if dist > 1e-9 else np.zeros(3)
                vel = float(
                    np.dot(
                        action_site.rt_velocities(xtion_site, state)[3:6],
                        unit_vec,
                    )
                )

                k = stiffness.value if isinstance(stiffness, NamedValue) else stiffness
                c = damping.value if isinstance(damping, NamedValue) else damping
                f_0 = preload.value if isinstance(preload, NamedValue) else preload
                d_f = (
                    max_stroke.value
                    if isinstance(max_stroke, NamedValue)
                    else max_stroke
                )

                delta_d = dist - self._r0
                if 0 <= delta_d <= d_f:
                    f_mag = f_0 - (k * delta_d) - (c * vel)
                    return max(0.0, f_mag)
                return 0.0

        logic = _Logic()

        return cls(
            name=name,
            action_site=action_site,
            xtion_site=xtion_site,
            magnitude_func=logic,
        )

    @classmethod
    def compression_spring(
        cls,
        name: str,
        action_site: AnySite,
        xtion_site: AnySite,
        stiffness: float | NamedValue[float] = 0.0,
        damping: float | NamedValue[float] = 0.0,
        rest_length: float = 0.0,
    ) -> Self:
        """
        Creates a spring-damper that only acts when compressed (dist < rest_length). Useful for bumpers, feet, push-off springs, or end-stops.
        """

        def logic(ud: UserData | None, state: MjState) -> float:
            dr = action_site.rt_displacements(xtion_site, state)
            dist = float(np.linalg.norm(dr))
            unit_vec = dr / dist if dist > 1e-9 else np.zeros(3)
            vel = float(
                np.dot(
                    action_site.rt_velocities(xtion_site, state)[3:6],
                    unit_vec,
                )
            )
            if dist < rest_length:
                return _ideal_force_logic(dist, vel, stiffness, damping, rest_length)
            return 0.0

        return cls(
            name=name,
            action_site=action_site,
            xtion_site=xtion_site,
            magnitude_func=logic,
        )

    @classmethod
    def tension_spring(
        cls,
        name: str,
        action_site: AnySite,
        xtion_site: AnySite,
        stiffness: float | NamedValue[float] = 0.0,
        damping: float | NamedValue[float] = 0.0,
        rest_length: float = 0.0,
    ) -> Self:
        """
        Creates a spring-damper that only acts when extended (dist > rest_length). Useful for cables, bungees, or tendons.
        """

        def logic(ud: UserData | None, state: MjState) -> float:
            dr = action_site.rt_displacements(xtion_site, state)
            dist = float(np.linalg.norm(dr))
            unit_vec = dr / dist if dist > 1e-9 else np.zeros(3)
            vel = float(
                np.dot(
                    action_site.rt_velocities(xtion_site, state)[3:6],
                    unit_vec,
                )
            )
            if dist > rest_length:
                return _ideal_force_logic(dist, vel, stiffness, damping, rest_length)
            return 0.0

        return cls(
            name=name,
            action_site=action_site,
            xtion_site=xtion_site,
            magnitude_func=logic,
        )


class BodyReactionForce(Load):
    """Load that also applies an equal and opposite reaction to a second body. If `xtion_body` is None, only the action site receives the force."""

    xtion_body: Body | None = None
    """Body that receives the reaction force. When None, no reaction is applied and the force acts on the world."""

    def resolve_ids(self, state: MjState):
        super().resolve_ids(state)
        if self.xtion_body:
            self.xtion_body.get_id(state.model)

    def apply_load(self, state: MjState):
        if not self.active:
            self.handle_inactive()
            return

        super().apply_load(state)

        if self.xtion_body is None:
            return

        f_world = self._last_f[:3]
        t_world = self._last_t[:3]

        # Reaction applied at the action_site position but to the reaction body
        mujoco.mj_applyFT(
            state.model,
            state.data,
            -f_world,
            -t_world,
            self.action_site.rt_pos(state),
            self.xtion_body.get_id(state.model),
            state.data.qfrc_applied,
        )


class ScalarForce(BodyReactionForce):
    """Force along the local X-axis of `action_site`, scaled by `scalar_func` each timestep."""

    scalar_func: Callable[[UserData | None, MjState], float] = lambda ud, s: 0.0
    """Callable (user_data, state) -> signed force magnitude (N). Positive is along the site's +X axis."""

    def calculate(self, state: MjState) -> tuple[np.ndarray, np.ndarray]:
        unit_vec = self.action_site.rt_xmat(state)[:, 0]
        mag = self.scalar_func(self.user_data, state)
        return unit_vec * mag, np.zeros(3)


class ScalarTorque(BodyReactionForce):
    """Torque about the local X-axis of `action_site`, scaled by `scalar_func` each timestep."""

    scalar_func: Callable[[UserData | None, MjState], float] = lambda ud, s: 0.0
    """Callable (user_data, state) -> signed torque magnitude. Positive follows the right-hand rule about the site's +X axis."""

    def calculate(self, state: MjState) -> tuple[np.ndarray, np.ndarray]:
        unit_vec = self.action_site.rt_xmat(state)[:, 0]
        mag = self.scalar_func(self.user_data, state)
        return np.zeros(3), unit_vec * mag


class VectorForce(BodyReactionForce):
    """3-axis force with independent per-axis callables. Components are expressed in `rel_to_site` frame, or world frame if None."""

    fx: Callable[[UserData | None, MjState], float] = lambda ud, s: 0.0
    """Callable (user_data, state) -> X-axis force component (N)."""

    fy: Callable[[UserData | None, MjState], float] = lambda ud, s: 0.0
    """Callable (user_data, state) -> Y-axis force component (N)."""

    fz: Callable[[UserData | None, MjState], float] = lambda ud, s: 0.0
    """Callable (user_data, state) -> Z-axis force component (N)."""

    def calculate(self, state: MjState) -> tuple[np.ndarray, np.ndarray]:
        ud = self.user_data
        f_raw = np.array(
            [
                self.fx(ud, state),
                self.fy(ud, state),
                self.fz(ud, state),
            ]
        )
        return self._get_world_vectors(state, f_raw), np.zeros(3)


class VectorTorque(BodyReactionForce):
    """3-axis torque with independent per-axis callables. Components are expressed in `rel_to_site` frame, or world frame if None."""

    tx: Callable[[UserData | None, MjState], float] = lambda ud, s: 0.0
    """Callable (user_data, state) -> X-axis torque component."""

    ty: Callable[[UserData | None, MjState], float] = lambda ud, s: 0.0
    """Callable (user_data, state) -> Y-axis torque component."""

    tz: Callable[[UserData | None, MjState], float] = lambda ud, s: 0.0
    """Callable (user_data, state) -> Z-axis torque component."""

    def calculate(self, state: MjState) -> tuple[np.ndarray, np.ndarray]:
        ud = self.user_data
        t_raw = np.array(
            [
                self.tx(ud, state),
                self.ty(ud, state),
                self.tz(ud, state),
            ]
        )
        return np.zeros(3), self._get_world_vectors(state, t_raw)


class GeneralLoad(VectorForce, VectorTorque):
    """Full 6-DOF force and torque with independent callables for each component. Combines `VectorForce` and `VectorTorque` into a single load."""

    def calculate(self, state: MjState) -> tuple[np.ndarray, np.ndarray]:
        ud = self.user_data
        f_raw = np.array(
            [
                self.fx(ud, state),
                self.fy(ud, state),
                self.fz(ud, state),
            ]
        )
        t_raw = np.array(
            [
                self.tx(ud, state),
                self.ty(ud, state),
                self.tz(ud, state),
            ]
        )
        return self._get_world_vectors(state, f_raw), self._get_world_vectors(
            state, t_raw
        )


class JointLoad(MojoBaseModel, ABC):
    """Abstract base for loads applied directly in generalized-coordinate (joint) space via `qfrc_applied`. Subclass and implement `apply_load()`."""

    name: str
    """Name used in telemetry output column naming."""

    active: bool = True
    """Whether this load is active."""

    joint: Joint
    """The MJCF joint this load acts on."""

    _jid: int = PrivateAttr(default=-1)
    _dof_adr: int = PrivateAttr(default=-1)
    _nv: int = PrivateAttr(default=1)

    def resolve_ids(self, state: MjState) -> None:
        """Caches the joint ID, DOF address, and DOF count from the compiled MuJoCo model."""
        self._jid = self.joint.get_id(state.model)
        jnt_type = state.model.jnt_type[self._jid]
        match jnt_type:
            case mujoco.mjtJoint.mjJNT_HINGE | mujoco.mjtJoint.mjJNT_SLIDE:
                self._nv = 1
            case mujoco.mjtJoint.mjJNT_BALL:
                self._nv = 3
            case _:
                msg = f"JointLoad '{self.name}': joint '{self.joint.name}' must be hinge, slide, or ball (got type {jnt_type})"
                logger.error(msg)
                raise ValueError(msg)
        self._dof_adr = int(state.model.jnt_dofadr[self._jid])
        logger.debug(
            "resolved joint '%s' to dof_adr=%d nv=%d",
            self.joint.name,
            self._dof_adr,
            self._nv,
        )

    @abstractmethod
    def apply_load(self, state: MjState) -> None:
        """Writes the load contribution into `state.data.qfrc_applied`."""

    def get_visuals(self, state: MjState) -> list[ArrowConfig]:
        """Joint loads have no Cartesian visualization."""
        return []

    def register_to_rm(self, runtime_manager: RuntimeManager) -> Self:
        runtime_manager.add_joint_load(self)
        return self


class JointFriction(JointLoad):
    """
    Joint friction with a pluggable formulation; use the class-method factories to construct.

    Works for hinge, slide, and ball joints. The `friction_func` receives the full generalized velocity vector for the joint's DOFs and returns a generalized force vector of the same length. All built-in formulations use the velocity magnitude as the scalar speed and apply the resulting force magnitude along `-vel/|vel|`, so they generalize naturally to multi-DOF joints. Use a `NamedValue` inside the closure to make parameters mutable at runtime.
    """

    friction_func: Callable[[np.ndarray, MjState], np.ndarray]
    """(vel, state) -> friction force/torque vector in generalized coordinates. Constructed by the named class-method factories."""

    _last_force: np.ndarray = PrivateAttr(default_factory=lambda: np.zeros(3))
    """Last applied friction expressed as a 3-vector in the world frame."""

    def _to_world_frc(self, frc: np.ndarray, state: MjState) -> np.ndarray:
        """Converts the generalized friction vector to a world-frame 3-vector. For ball joints the generalized forces are already world-frame torques. For hinge/slide, the scalar is projected onto the joint axis rotated into world frame."""
        if self._nv == 3:
            return frc.copy()
        body_id = int(state.model.jnt_bodyid[self._jid])
        jnt_axis = np.array(state.model.jnt_axis[self._jid])
        body_xmat = np.array(state.data.xmat[body_id]).reshape(3, 3)
        return float(frc[0]) * (body_xmat @ jnt_axis)

    def apply_load(self, state: MjState) -> None:
        """Evaluates `friction_func` at the current joint velocity vector and accumulates the result into `qfrc_applied`."""
        if not self.active or self._dof_adr < 0:
            self._last_force = np.zeros(3)
            return

        vel = np.array(state.data.qvel[self._dof_adr : self._dof_adr + self._nv])
        frc = self.friction_func(vel, state)
        state.data.qfrc_applied[self._dof_adr : self._dof_adr + self._nv] += frc
        self._last_force = self._to_world_frc(frc, state)

    def request(self, signal_manager: SignalManager) -> None:
        """
        Registers per-timestep friction force/torque in the world frame for telemetry. Posts x, y, z components and magnitude. Raises ValueError if the joint has no name.

        Args:
            signal_manager (SignalManager): Manager to register the sampler with.

        """
        if self.joint.name is None:
            msg = f"Cannot request telemetry for JointFriction '{self.name}': joint has no name."
            logger.error(msg)
            raise ValueError(msg)

        def sample(state: MjState) -> None:
            frc = self._last_force if self.active else np.zeros(3)
            for v, label in zip(frc, ("x", "y", "z")):
                signal_manager.post(
                    value=float(v),
                    category=SignalCategory.LOADS,
                    subgroups=(self.name, "friction"),
                    attr=label,
                )
            signal_manager.post(
                value=float(np.linalg.norm(frc)),
                category=SignalCategory.LOADS,
                subgroups=(self.name, "friction"),
                attr="m",
            )

        signal_manager.register_sampler(sample)

    @classmethod
    def coulomb(
        cls,
        name: str,
        joint: Joint,
        magnitude: float | NamedValue[float],
    ) -> Self:
        """
        Constant-magnitude Coulomb (dry) friction opposing motion. Zero force at standstill. Good for brake pads, dry contacts, and cable friction.

        Args:
            name (str): Load name used for telemetry column labeling.
            joint (Joint): The MJCF joint to act on (slide, hinge, or ball).
            magnitude (float | NamedValue[float]): Friction force or torque magnitude. Accepts `NamedValue[float]` for runtime mutation.

        """

        def func(vel: np.ndarray, state: MjState) -> np.ndarray:
            speed = float(np.linalg.norm(vel))
            return (
                -float(magnitude) * vel / speed if speed > 1e-9 else np.zeros_like(vel)
            )

        return cls(name=name, joint=joint, friction_func=func)

    @classmethod
    def viscous(
        cls,
        name: str,
        joint: Joint,
        damping: float | NamedValue[float],
    ) -> Self:
        """
        Velocity-proportional viscous damping. Force is continuous through zero with no discontinuity at standstill. Good for grease-lubricated joints and fluid drag.

        Args:
            name (str): Load name used for telemetry column labeling.
            joint (Joint): The MJCF joint to act on (slide, hinge, or ball).
            damping (float | NamedValue[float]): Damping coefficient (force per velocity, or torque per angular velocity). Accepts `NamedValue[float]` for runtime mutation.

        """

        def func(vel: np.ndarray, state: MjState) -> np.ndarray:
            return -float(damping) * vel

        return cls(name=name, joint=joint, friction_func=func)

    @classmethod
    def coulomb_viscous(
        cls,
        name: str,
        joint: Joint,
        coulomb: float | NamedValue[float],
        viscous: float | NamedValue[float],
    ) -> Self:
        """
        Coulomb and viscous friction combined. Constant sliding friction plus a velocity-proportional drag term. Realistic for most real joints.

        Args:
            name (str): Load name used for telemetry column labeling.
            joint (Joint): The MJCF joint to act on (slide, hinge, or ball).
            coulomb (float | NamedValue[float]): Coulomb friction force or torque magnitude. Accepts `NamedValue[float]` for runtime mutation.
            viscous (float | NamedValue[float]): Viscous damping coefficient (force per velocity, or torque per angular velocity). Accepts `NamedValue[float]` for runtime mutation.

        """

        def func(vel: np.ndarray, state: MjState) -> np.ndarray:
            speed = float(np.linalg.norm(vel))
            coulomb_term = (
                -float(coulomb) * vel / speed if speed > 1e-9 else np.zeros_like(vel)
            )
            return coulomb_term - float(viscous) * vel

        return cls(name=name, joint=joint, friction_func=func)

    @classmethod
    def stribeck(
        cls,
        name: str,
        joint: Joint,
        coulomb: float | NamedValue[float],
        static: float | NamedValue[float],
        stribeck_velocity: float | NamedValue[float],
        viscous: float | NamedValue[float] = 0.0,
    ) -> Self:
        """
        Full Stribeck friction model. Friction peaks at standstill, drops to the kinetic level as motion begins, then rises with speed. Best for brake and clutch models where stick-slip matters.

        F = -(coulomb + (static - coulomb) * exp(-|v| / stribeck_velocity) + viscous * |v|) * v / |v|

        Args:
            name (str): Load name used for telemetry column labeling.
            joint (Joint): The MJCF joint to act on (slide, hinge, or ball).
            coulomb (float | NamedValue[float]): Kinetic friction force or torque magnitude. Accepts `NamedValue[float]`.
            static (float | NamedValue[float]): Peak static friction force or torque at zero velocity. Must be >= `coulomb`. Accepts `NamedValue[float]`.
            stribeck_velocity (float | NamedValue[float]): Characteristic velocity at which friction transitions from static to kinetic. Smaller values give a sharper transition. Accepts `NamedValue[float]`.
            viscous (float | NamedValue[float], optional): Velocity-proportional damping (force per velocity, or torque per angular velocity). Defaults to 0. Accepts `NamedValue[float]`.

        """

        def func(vel: np.ndarray, state: MjState) -> np.ndarray:
            speed = float(np.linalg.norm(vel))
            if speed < 1e-9:
                return np.zeros_like(vel)
            fc, fs = float(coulomb), float(static)
            vs, fv = float(stribeck_velocity), float(viscous)
            mag = fc + (fs - fc) * np.exp(-speed / max(vs, 1e-9)) + fv * speed
            return -mag * vel / speed

        return cls(name=name, joint=joint, friction_func=func)
