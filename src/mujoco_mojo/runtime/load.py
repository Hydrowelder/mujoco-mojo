from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal, Self

import mujoco
import numpy as np
from pydantic import PrivateAttr, SerializeAsAny, model_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco_attr.body import Body
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
    """Base class to build forcing functions off of."""

    name: str
    """Name of the forcing function. Used in data output column naming."""

    active: bool = True
    """Whether or not this force should be active."""

    action_site: AnySite
    """Site on which the forcing function acts."""

    rel_to_site: AnySite | None = None
    """Frame of reference for the calculated force. If None, uses worldbody."""

    user_data: SerializeAsAny[UserData] | None = None
    """Optional typed custom data accessible inside `calculate()`. Set by subclassing `UserData`."""

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

    def resolve_ids(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """Caches the integer IDs from the compiled MuJoCo model."""
        self._vis = MujocoMojoSettings().visualization
        self.action_site.get_id(mj_model)

        if self.rel_to_site:
            self.rel_to_site.get_id(mj_model)

    def _get_world_vectors(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        local: Vec3,
    ) -> Vec3:
        """Rotates local force/torque into world coordinates based on relative_to."""
        if self.rel_to_site is None:
            return local

        return self.rel_to_site.rt_xmat(mj_model, mj_data) @ local

    @abstractmethod
    def calculate(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Calculate the force for the timestep.

        Args:
            mj_model (mujoco.MjModel): _description_
            mj_data (mujoco.MjData): _description_

        Returns:
            tuple[np.ndarray, np.ndarray]: The force and toque vector output.

        """

    def register_to_rm(self, runtime_manager: RuntimeManager) -> Self:
        runtime_manager.add_load(self)
        return self

    def apply_load(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        if not self.active:
            self.handle_inactive()
            return

        f_world, t_world = self.calculate(mj_model=mj_model, mj_data=mj_data)
        self._last_f[:3] = f_world
        self._last_f[3] = np.linalg.norm(f_world)
        self._last_t[:3] = t_world
        self._last_t[3] = np.linalg.norm(t_world)

        # apply to action site
        action_pos = self.action_site.rt_pos(mj_model, mj_data)
        action_bid = self.action_site.rt_parent_body(mj_model)
        mujoco.mj_applyFT(
            m=mj_model,
            d=mj_data,
            force=f_world,
            torque=t_world,
            point=action_pos,
            body=action_bid,
            # target generalized force array
            qfrc_target=mj_data.qfrc_applied,
        )

    def request(
        self,
        signal_manager: SignalManager,
        attrs: list[Literal["force", "torque"]] = ["force", "torque"],
    ):
        def sample(mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
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

    def get_visuals(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> list[ArrowConfig]:
        """Returns a list of arrow configurations for the renderer."""
        if not self.active:
            return []

        visuals: list[ArrowConfig] = []
        action_pos = self.action_site.rt_pos(mj_model, mj_data)

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
    """Acts along the line-of-sight between two sites."""

    xtion_site: AnySite
    """Site on which the forcing function will apply a reation force. Leave as None to use the worldbody.

    This is called xtion to limit confusion between "reaction" and "relative"."""

    magnitude_func: Callable[[UserData | None, mujoco.MjModel, mujoco.MjData], float]
    """Func(user_data, MjModel, MjData) -> scalar_force magnitude. Can be a regular function, lambda, etc."""

    _r0_mag: float = PrivateAttr(default=0.0)
    """Initial distance between action and reaction sites."""

    def resolve_ids(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """Caches the integer IDs from the compiled MuJoCo model."""
        super().resolve_ids(mj_model, mj_data)
        self.xtion_site.get_id(mj_model)
        self._r0_mag = self.action_site.rt_dm(self.xtion_site, mj_model, mj_data)
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

    def apply_load(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        if not self.active:
            self.handle_inactive()
            return

        super().apply_load(mj_model, mj_data)

        f_world = self._last_f[:3]
        t_world = self._last_t[:3]

        xtion_pos = self.xtion_site.rt_pos(mj_model, mj_data)
        xtion_bid = self.xtion_site.rt_parent_body(mj_model)

        mujoco.mj_applyFT(
            m=mj_model,
            d=mj_data,
            force=-f_world,
            torque=-t_world,
            point=xtion_pos,
            body=xtion_bid,
            qfrc_target=mj_data.qfrc_applied,
        )

    def get_visuals(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> list[ArrowConfig]:
        """Returns a list of arrow configurations for the renderer."""
        if not self.active:
            return []

        visuals = super().get_visuals(mj_model, mj_data)

        if self._last_f[3] > 1e-4 and self._vis.reaction_force:
            xtion_pos = self.xtion_site.rt_pos(mj_model, mj_data)
            visuals.append(
                ArrowConfig(
                    pos=xtion_pos,
                    vec=-self._last_f[:3],
                    color=Color[self._vis.reaction_force].rgba,
                    is_torque=False,
                )
            )

        return visuals

    def calculate(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[np.ndarray, np.ndarray]:
        dr_world = self.action_site.rt_displacements(self.xtion_site, mj_model, mj_data)
        dist = float(np.linalg.norm(dr_world))
        unit_vec = dr_world / dist if dist > 1e-9 else np.zeros(3)

        f_mag = self.magnitude_func(self.user_data, mj_model, mj_data)

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
        """Standard linear spring-damper (works in both tension and compression)."""

        def logic(
            ud: UserData | None, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
        ) -> float:
            dr = action_site.rt_displacements(xtion_site, mj_model, mj_data)
            dist = float(np.linalg.norm(dr))
            unit_vec = dr / dist if dist > 1e-9 else np.zeros(3)
            vel = float(
                np.dot(
                    action_site.rt_velocities(xtion_site, mj_model, mj_data)[3:6],
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
        """Creates a spring-damper that only acts when the runtime length is between rest_length and (rest_legnth + stroke_length)."""

        class _Logic:
            def __init__(self) -> None:
                self._r0: float = 0.0

            def on_resolve(self, r0: float) -> None:
                self._r0 = r0

            def __call__(
                self,
                ud: UserData | None,
                mj_model: mujoco.MjModel,
                mj_data: mujoco.MjData,
            ) -> float:
                dr = action_site.rt_displacements(xtion_site, mj_model, mj_data)
                dist = float(np.linalg.norm(dr))
                unit_vec = dr / dist if dist > 1e-9 else np.zeros(3)
                vel = float(
                    np.dot(
                        action_site.rt_velocities(xtion_site, mj_model, mj_data)[3:6],
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

        def logic(
            ud: UserData | None, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
        ) -> float:
            dr = action_site.rt_displacements(xtion_site, mj_model, mj_data)
            dist = float(np.linalg.norm(dr))
            unit_vec = dr / dist if dist > 1e-9 else np.zeros(3)
            vel = float(
                np.dot(
                    action_site.rt_velocities(xtion_site, mj_model, mj_data)[3:6],
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

        def logic(
            ud: UserData | None, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
        ) -> float:
            dr = action_site.rt_displacements(xtion_site, mj_model, mj_data)
            dist = float(np.linalg.norm(dr))
            unit_vec = dr / dist if dist > 1e-9 else np.zeros(3)
            vel = float(
                np.dot(
                    action_site.rt_velocities(xtion_site, mj_model, mj_data)[3:6],
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
    xtion_body: Body | None = None
    """Body on which the load should be acted on. If None the world will be used."""

    def resolve_ids(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        super().resolve_ids(mj_model, mj_data)
        if self.xtion_body:
            self.xtion_body.get_id(mj_model)

    def apply_load(self, mj_model, mj_data):
        if not self.active:
            self.handle_inactive()
            return

        super().apply_load(mj_model, mj_data)

        if self.xtion_body is None:
            return

        f_world = self._last_f[:3]
        t_world = self._last_t[:3]

        # Reaction applied at the action_site position but to the reaction body
        mujoco.mj_applyFT(
            mj_model,
            mj_data,
            -f_world,
            -t_world,
            self.action_site.rt_pos(mj_model, mj_data),
            self.xtion_body.get_id(mj_model),
            mj_data.qfrc_applied,
        )


class ScalarForce(BodyReactionForce):
    """Applies a scalar force along the local X-axis of the action_site."""

    scalar_func: Callable[[UserData | None, mujoco.MjModel, mujoco.MjData], float] = (
        lambda ud, m, d: 0.0
    )
    """Func(user_data, MjModel, MjData) -> scalar force magnitude."""

    def calculate(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> tuple[np.ndarray, np.ndarray]:
        unit_vec = self.action_site.rt_xmat(mj_model, mj_data)[:, 0]
        mag = self.scalar_func(self.user_data, mj_model, mj_data)
        return unit_vec * mag, np.zeros(3)


class ScalarTorque(BodyReactionForce):
    """Applies a scalar torque along the local X-axis of the action_site."""

    scalar_func: Callable[[UserData | None, mujoco.MjModel, mujoco.MjData], float] = (
        lambda ud, m, d: 0.0
    )
    """Func(user_data, MjModel, MjData) -> scalar torque magnitude."""

    def calculate(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> tuple[np.ndarray, np.ndarray]:
        unit_vec = self.action_site.rt_xmat(mj_model, mj_data)[:, 0]
        mag = self.scalar_func(self.user_data, mj_model, mj_data)
        return np.zeros(3), unit_vec * mag


class VectorForce(BodyReactionForce):
    fx: Callable[[UserData | None, mujoco.MjModel, mujoco.MjData], float] = (
        lambda ud, m, d: 0.0
    )
    fy: Callable[[UserData | None, mujoco.MjModel, mujoco.MjData], float] = (
        lambda ud, m, d: 0.0
    )
    fz: Callable[[UserData | None, mujoco.MjModel, mujoco.MjData], float] = (
        lambda ud, m, d: 0.0
    )

    def calculate(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[np.ndarray, np.ndarray]:
        ud = self.user_data
        f_raw = np.array(
            [
                self.fx(ud, mj_model, mj_data),
                self.fy(ud, mj_model, mj_data),
                self.fz(ud, mj_model, mj_data),
            ]
        )
        return self._get_world_vectors(mj_model, mj_data, f_raw), np.zeros(3)


class VectorTorque(BodyReactionForce):
    tx: Callable[[UserData | None, mujoco.MjModel, mujoco.MjData], float] = (
        lambda ud, m, d: 0.0
    )
    ty: Callable[[UserData | None, mujoco.MjModel, mujoco.MjData], float] = (
        lambda ud, m, d: 0.0
    )
    tz: Callable[[UserData | None, mujoco.MjModel, mujoco.MjData], float] = (
        lambda ud, m, d: 0.0
    )

    def calculate(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[np.ndarray, np.ndarray]:
        ud = self.user_data
        t_raw = np.array(
            [
                self.tx(ud, mj_model, mj_data),
                self.ty(ud, mj_model, mj_data),
                self.tz(ud, mj_model, mj_data),
            ]
        )
        return np.zeros(3), self._get_world_vectors(mj_model, mj_data, t_raw)


class GeneralLoad(VectorForce, VectorTorque):
    """A 6-DOF force/torque applier."""

    def calculate(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[np.ndarray, np.ndarray]:
        ud = self.user_data
        f_raw = np.array(
            [
                self.fx(ud, mj_model, mj_data),
                self.fy(ud, mj_model, mj_data),
                self.fz(ud, mj_model, mj_data),
            ]
        )
        t_raw = np.array(
            [
                self.tx(ud, mj_model, mj_data),
                self.ty(ud, mj_model, mj_data),
                self.tz(ud, mj_model, mj_data),
            ]
        )
        return self._get_world_vectors(
            mj_model,
            mj_data,
            f_raw,
        ), self._get_world_vectors(
            mj_model,
            mj_data,
            t_raw,
        )
