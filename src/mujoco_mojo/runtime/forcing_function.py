from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal, Self

import mujoco
import numpy as np
from pydantic import PrivateAttr, model_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco_attr.body import Body
from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import Site
from mujoco_mojo.process_manager import NamedValue
from mujoco_mojo.runtime.results_manager import ResultsManager
from mujoco_mojo.runtime.video_recorder import ArrowConfig
from mujoco_mojo.utils.color import Color
from mujoco_mojo.utils.log import get_logger

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


class ForcingFunction(MojoBaseModel, ABC):
    """Base class to build forcing functions off of."""

    name: str
    """Name of the forcing function. Used in data output column naming."""

    active: bool = True
    """Whether or not this force should be active."""

    action_site: Site
    """Site on which the forcing function acts."""

    rel_to_site: Site | None = None
    """Frame of reference for the calculated force. If None, uses worldbody."""

    _last_f: np.ndarray = PrivateAttr(default_factory=lambda: np.zeros(4))
    """Previous timestep's force values. Used for request management."""

    _last_t: np.ndarray = PrivateAttr(default_factory=lambda: np.zeros(4))
    """Previous timestep's torque values. Used for request management."""

    def resolve_ids(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """Caches the integer IDs from the compiled MuJoCo model."""
        self.action_site.get_id(mj_model)

        if self.rel_to_site:
            self.rel_to_site.get_id(mj_model)

    def _get_world_vectors(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        local: np.ndarray,
    ) -> np.ndarray:
        """Rotates local force/torque into world coordinates based on relative_to."""
        if self.rel_to_site is None:
            return local

        # Get the 3x3 rotation matrix for the reference site
        # MuJoCo stores this as a flat 9-element array in site_xmat
        rot = np.asarray(mj_data.site_xmat[self.rel_to_site.get_id(mj_model)]).reshape(
            3, 3
        )
        return rot @ local

    @abstractmethod
    def calculate(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Calculate the force for the timestep.

        Args:
            mj_model (mujoco.MjModel): _description_
            mj_data (mujoco.MjData): _description_

        Returns:
            tuple[np.ndarray, np.ndarray]: The force and toque vector output.

        """

    def register_to_rm(self, runtime_manager: "RuntimeManager") -> Self:
        runtime_manager.add_load(self)
        return self

    def apply_load(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        if not self.active:
            return

        f_world, t_world = self.calculate(mj_model=mj_model, mj_data=mj_data)
        self._last_f = np.append(f_world, np.linalg.norm(f_world))
        self._last_t = np.append(t_world, np.linalg.norm(t_world))

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

        # shadow for visualization (action)
        # xfrc_applied is [fx, fy, fz, tx, ty, tz]
        mj_data.xfrc_applied[action_bid][:3] += f_world
        mj_data.xfrc_applied[action_bid][3:] += t_world

    def request(
        self,
        results_manager: ResultsManager,
        attrs: list[Literal["force", "torque"]] = ["force", "torque"],
    ):
        def harvest(mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
            if "force" in attrs:
                for i, k in enumerate("xyzm"):
                    results_manager.post(
                        f"{self.name}_force_{k}", self._last_f[i] if self.active else 0
                    )
            if "torque" in attrs:
                for i, k in enumerate("xyzm"):
                    results_manager.post(
                        f"{self.name}_torque_{k}", self._last_t[i] if self.active else 0
                    )

        results_manager.schedule_harvest_task(harvest)

    def get_visuals(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> list[ArrowConfig]:
        """Returns a list of arrow configurations for the renderer."""
        if not self.active:
            return []

        visuals: list[ArrowConfig] = []
        action_pos = self.action_site.rt_pos(mj_model, mj_data)

        # force arrow
        f_vec = self._last_f[:3]
        if np.linalg.norm(f_vec) > 1e-4:
            visuals.append(
                {
                    "pos": action_pos,
                    "vec": f_vec,
                    "color": np.asarray(Color.EMERALD_500.rgba),
                    "is_torque": False,
                }
            )

        t_vec = self._last_t[:3]
        if np.linalg.norm(t_vec) > 1e-4:
            visuals.append(
                {
                    "pos": action_pos,
                    "vec": t_vec,
                    "color": np.asarray(Color.AMBER_500.rgba),
                    "is_torque": True,
                }
            )

        return visuals


class PointToPointForce(ForcingFunction):
    """Acts along the line-of-sight between two sites."""

    xtion_site: Site
    """Site on which the forcing function will apply a reation force. Leave as None to use the worldbody.

    This is called xtion to limit confusion between "reaction" and "relative"."""

    magnitude_func: Callable[
        [float, float, float, mujoco.MjModel, mujoco.MjData], float
    ]
    """Func(distance, velocity, initial distance, MjModel, MjData) -> scalar_force. Can be a regular function, lambda, etc."""

    _r0_mag: float = PrivateAttr(default=0.0)
    """Initial distance between action and reaction sites."""

    def resolve_ids(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """Caches the integer IDs from the compiled MuJoCo model."""
        super().resolve_ids(mj_model, mj_data)
        self.xtion_site.get_id(mj_model)
        self._r0_mag = self.action_site.rt_dm(self.xtion_site, mj_model, mj_data)

    @model_validator(mode="after")
    def _validate_frame(self) -> Self:
        if self.rel_to_site is not None:
            raise ValueError(
                f"PointToPointForce '{self.name}' cannot use 'relative_to'. It is natively defined by the line-of-sight between sites."
            )
        return self

    def apply_load(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
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
        mj_data.xfrc_applied[xtion_bid][:3] += -f_world
        mj_data.xfrc_applied[xtion_bid][3:] += -t_world

    def get_visuals(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> list[ArrowConfig]:
        """Returns a list of arrow configurations for the renderer."""
        visuals = super().get_visuals(mj_model, mj_data)

        if not self.active:
            return []

        # Add the reaction force arrow at the xtion site
        xtion_pos = self.xtion_site.rt_pos(mj_model, mj_data)
        f_vec = self._last_f[:3]

        if np.linalg.norm(f_vec) > 1e-4:
            visuals.append(
                {
                    "pos": xtion_pos,
                    "vec": -f_vec,  # opposite direction
                    "color": np.asarray(Color.ROSE_500.rgba),  # Red for Reaction
                    "is_torque": False,
                }
            )

        return visuals

    def calculate(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[np.ndarray, np.ndarray]:
        # get euclidian distance
        dist = self.action_site.rt_dm(self.xtion_site, mj_model, mj_data)

        # get relative displacement vector in world frame
        dr_world = self.action_site.rt_displacements(self.xtion_site, mj_model, mj_data)
        unit_vec = dr_world / dist if dist > 1e-9 else np.zeros(3)

        # get relative velocity along line-of-action
        v_rel_world = self.action_site.rt_velocities(
            self.xtion_site, mj_model, mj_data
        )[3:6]
        vel = np.dot(v_rel_world, unit_vec)

        # user defined logic
        f_mag = self.magnitude_func(dist, vel, self._r0_mag, mj_model, mj_data)

        return unit_vec * f_mag, np.zeros(3)

    @classmethod
    def ideal_spring(
        cls,
        name: str,
        action_site: Site,
        xtion_site: Site,
        stiffness: float | NamedValue[float] = 0.0,
        damping: float | NamedValue[float] = 0.0,
        rest_length: float = 0.0,
    ) -> Self:
        """Standard linear spring-damper (works in both tension and compression)."""

        def logic(
            d: float,
            v: float,
            r0: float,
            mj_model: mujoco.MjModel,
            mj_data: mujoco.MjData,
        ) -> float:
            return _ideal_force_logic(d, v, stiffness, damping, rest_length)

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
        action_site: Site,
        xtion_site: Site,
        stiffness: float | NamedValue[float] = 0.0,
        damping: float | NamedValue[float] = 0.0,
        preload: float | NamedValue[float] = 0.0,
        max_stroke: float | NamedValue[float] = 0.1,
    ) -> Self:
        """Creates a spring-damper that only acts when the runtime length is between rest_length and (rest_legnth + stroke_length)"""

        def logic(
            d: float,
            v: float,
            r0: float,
            mj_model: mujoco.MjModel,
            mj_data: mujoco.MjData,
        ) -> float:
            k = stiffness.value if isinstance(stiffness, NamedValue) else stiffness
            c = damping.value if isinstance(damping, NamedValue) else damping
            f_0 = preload.value if isinstance(preload, NamedValue) else preload
            d_f = max_stroke.value if isinstance(max_stroke, NamedValue) else max_stroke

            delta_d = d - r0

            if 0 <= delta_d <= d_f:
                f_mag = f_0 - (k * delta_d) - (c * v)
                return max(0.0, f_mag)
            return 0.0

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
        action_site: Site,
        xtion_site: Site,
        stiffness: float | NamedValue[float] = 0.0,
        damping: float | NamedValue[float] = 0.0,
        rest_length: float = 0.0,
    ) -> Self:
        """
        Creates a spring-damper that only acts when compressed (dist < rest_length). Useful for bumpers, feet, push-off springs, or end-stops.
        """

        def logic(
            d: float,
            v: float,
            r0: float,
            mj_model: mujoco.MjModel,
            mj_data: mujoco.MjData,
        ) -> float:
            if d < rest_length:
                return _ideal_force_logic(d, v, stiffness, damping, rest_length)
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
        action_site: Site,
        xtion_site: Site,
        stiffness: float | NamedValue[float] = 0.0,
        damping: float | NamedValue[float] = 0.0,
        rest_length: float = 0.0,
    ) -> Self:
        """
        Creates a spring-damper that only acts when extended (dist > rest_length). Useful for cables, bungees, or tendons.
        """

        def logic(
            d: float,
            v: float,
            r0: float,
            mj_model: mujoco.MjModel,
            mj_data: mujoco.MjData,
        ) -> float:
            if d > rest_length:
                return _ideal_force_logic(d, v, stiffness, damping, rest_length)
            return 0.0

        return cls(
            name=name,
            action_site=action_site,
            xtion_site=xtion_site,
            magnitude_func=logic,
        )


class BodyReactionForce(ForcingFunction):
    xtion_body: Body | None = None
    """Body on which the load should be acted on. If None the world will be used."""

    def resolve_ids(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        super().resolve_ids(mj_model, mj_data)
        if self.xtion_body:
            self.xtion_body.get_id(mj_model)

    def apply_load(self, mj_model, mj_data):
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

    scalar_func: Callable[[float, np.ndarray, mujoco.MjModel, mujoco.MjData], float] = (
        lambda t, unit_vec, m, d: 0.0
    )
    """Func(time, action_site x axis unit vector, MjModel, MjData) -> scalar force value."""

    def calculate(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> tuple[np.ndarray, np.ndarray]:
        t = mj_data.time

        sid = self.action_site.get_id(mj_model)
        unit_vec = np.asarray(mj_data.site_xmat[sid]).reshape(3, 3)[:, 0]

        mag = self.scalar_func(t, unit_vec, mj_model, mj_data)

        f_world = unit_vec * mag
        return f_world, np.zeros(3)


class ScalarTorque(BodyReactionForce):
    """Applies a scalar torque along the local X-axis of the action_site."""

    scalar_func: Callable[[float, np.ndarray, mujoco.MjModel, mujoco.MjData], float] = (
        lambda t, unit_vec, m, d: 0.0
    )
    """Func(time, action_site x-axis unit vector, MjModel, MjData) -> scalar torque value."""

    def calculate(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> tuple[np.ndarray, np.ndarray]:
        t = mj_data.time

        sid = self.action_site.get_id(mj_model)
        unit_vec = np.asarray(mj_data.site_xmat[sid]).reshape(3, 3)[:, 0]

        mag = self.scalar_func(t, unit_vec, mj_model, mj_data)

        t_world = unit_vec * mag
        return np.zeros(3), t_world


class VectorForce(BodyReactionForce):
    fx: Callable[[float, mujoco.MjModel, mujoco.MjData], float] = lambda t, m, d: 0.0
    fy: Callable[[float, mujoco.MjModel, mujoco.MjData], float] = lambda t, m, d: 0.0
    fz: Callable[[float, mujoco.MjModel, mujoco.MjData], float] = lambda t, m, d: 0.0

    def calculate(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[np.ndarray, np.ndarray]:
        t = mj_data.time
        f_raw = np.array(
            [
                self.fx(t, mj_model, mj_data),
                self.fy(t, mj_model, mj_data),
                self.fz(t, mj_model, mj_data),
            ]
        )
        return self._get_world_vectors(mj_model, mj_data, f_raw), np.zeros(3)


class VectorTorque(BodyReactionForce):
    tx: Callable[[float, mujoco.MjModel, mujoco.MjData], float] = lambda t, m, d: 0.0
    ty: Callable[[float, mujoco.MjModel, mujoco.MjData], float] = lambda t, m, d: 0.0
    tz: Callable[[float, mujoco.MjModel, mujoco.MjData], float] = lambda t, m, d: 0.0

    def calculate(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[np.ndarray, np.ndarray]:
        t = mj_data.time
        t_raw = np.array(
            [
                self.tx(t, mj_model, mj_data),
                self.ty(t, mj_model, mj_data),
                self.tz(t, mj_model, mj_data),
            ]
        )
        return np.zeros(3), self._get_world_vectors(mj_model, mj_data, t_raw)


class GeneralForce(VectorForce, VectorTorque):
    """A 6-DOF force/torque applier."""

    def calculate(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
    ) -> tuple[np.ndarray, np.ndarray]:
        t = mj_data.time
        f_raw = np.array(
            [
                self.fx(t, mj_model, mj_data),
                self.fy(t, mj_model, mj_data),
                self.fz(t, mj_model, mj_data),
            ]
        )
        t_raw = np.array(
            [
                self.tx(t, mj_model, mj_data),
                self.ty(t, mj_model, mj_data),
                self.tz(t, mj_model, mj_data),
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
