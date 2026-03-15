from abc import abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Literal, Self

import mujoco
import numpy as np
from pydantic import PrivateAttr, model_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import Site
from mujoco_mojo.process_manager import NamedValue
from mujoco_mojo.runtime.results_manager import ResultsManager
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


class ForcingFunction(MojoBaseModel):
    """Base class to build forcing functions off of."""

    name: str
    """Name of the forcing function. Used in data output column naming."""

    active: bool = True
    """Whether or not this force should be active."""

    action_site: Site
    """Site on which the forcing function acts."""

    xtion_site: Site | None = None
    """Site on which the forcing function will apply a reation force. Leave as None to use the worldbody.

    This is called xtion to limit confusion between "reaction" and "relative"."""

    rel_to_site: Site | None = None
    """Frame of reference for the calculated force. If None, uses worldbody."""

    _last_f: np.ndarray = PrivateAttr(default_factory=lambda: np.zeros(4))
    """Previous timestep's force values. Used for request management."""

    _last_t: np.ndarray = PrivateAttr(default_factory=lambda: np.zeros(4))
    """Previous timestep's torque values. Used for request management."""

    _r0_mag: float = PrivateAttr(default=0.0)
    """Initial distance between action and reaction sites."""

    def resolve_ids(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """Caches the integer IDs from the compiled MuJoCo model."""
        self.action_site.get_id(mj_model)
        if self.xtion_site:
            self.xtion_site.get_id(mj_model)
        if self.rel_to_site:
            self.rel_to_site.get_id(mj_model)

        self._r0_mag = self.action_site.rt_dm(self.xtion_site, mj_model, mj_data)

    def _get_world_vectors(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        f_local: np.ndarray,
        t_local: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Rotates local force/torque into world coordinates based on relative_to."""
        if self.rel_to_site is None:
            return f_local, t_local

        # Get the 3x3 rotation matrix for the reference site
        # MuJoCo stores this as a flat 9-element array in site_xmat
        rot: np.ndarray = mj_data.site_xmat[self.rel_to_site.get_id(mj_model)].reshape(
            3, 3
        )
        return rot @ f_local, rot @ t_local

    @abstractmethod
    def calculate(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        results_manager: ResultsManager | None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Calculate the force for the timestep.

        Args:
            mj_model (mujoco.MjModel): _description_
            mj_data (mujoco.MjData): _description_
            results_manager (ResultsManager): _description_

        Returns:
            tuple[np.ndarray, np.ndarray]: The force and toque vector output.

        """

    def register_to_rm(self, runtime_manager: "RuntimeManager") -> Self:
        runtime_manager.add_load(self)
        return self

    def apply_load(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        results_manager: ResultsManager | None = None,
    ):
        if not self.active:
            return

        f_world, t_world = self.calculate(
            mj_model=mj_model, mj_data=mj_data, results_manager=results_manager
        )
        self._last_f = np.append(f_world, np.linalg.norm(f_world))
        self._last_t = np.append(t_world, np.linalg.norm(t_world))

        # apply to action site
        action_pos = self.action_site.rt_pos(mj_model, mj_data)
        mujoco.mj_applyFT(
            m=mj_model,
            d=mj_data,
            force=f_world,
            torque=t_world,
            point=action_pos,
            body=self.action_site.rt_parent_body(mj_model),
            # target generalized force array
            qfrc_target=mj_data.qfrc_applied,
        )

        # apply reaction force
        if self.xtion_site is not None:
            if isinstance(self, PointToPointForce):
                reaction_pos = self.xtion_site.rt_pos(mj_model, mj_data)
            else:
                reaction_pos = action_pos

            mujoco.mj_applyFT(
                m=mj_model,
                d=mj_data,
                force=-f_world,  # some nerd came up with this
                torque=-t_world,
                point=reaction_pos,
                body=self.xtion_site.rt_parent_body(mj_model),
                qfrc_target=mj_data.qfrc_applied,
            )

    def request(
        self,
        results_manager: ResultsManager,
        attrs: list[Literal["force", "torque"]] = ["force", "torque"],
    ):
        def harvest(mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
            if "force" in attrs:
                for i, k in enumerate("xyzm"):
                    results_manager.post(f"{self.name}_force_{k}", self._last_f[i])
            if "torque" in attrs:
                for i, k in enumerate("xyzm"):
                    results_manager.post(f"{self.name}_torque_{k}", self._last_t[i])

        results_manager.schedule_harvest_task(harvest)


class PointToPointForce(ForcingFunction):
    """Acts along the line-of-sight between two sites."""

    magnitude_func: Callable[[float, float, float], float]
    """Func(distance, velocity, initial distance) -> scalar_force. Can be a regular function, lambda, etc."""

    @model_validator(mode="after")
    def _validate_frame(self) -> Self:
        if self.rel_to_site is not None:
            raise ValueError(
                f"PointToPointForce '{self.name}' cannot use 'relative_to'. It is natively defined by the line-of-sight between sites."
            )
        return self

    def calculate(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        results_manager: ResultsManager | None = None,
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
        f_mag = self.magnitude_func(dist, vel, self._r0_mag)

        return unit_vec * f_mag, np.zeros(3)

    @classmethod
    def ideal_spring(
        cls,
        name: str,
        action_site: Site,
        xtion_site: Site | None = None,
        stiffness: float | NamedValue[float] = 0.0,
        damping: float | NamedValue[float] = 0.0,
        rest_length: float = 0.0,
    ) -> Self:
        """Standard linear spring-damper (works in both tension and compression)."""

        def logic(d: float, v: float, r0: float) -> float:
            return _ideal_force_logic(d, v, stiffness, damping, rest_length)

        return cls(
            name=name,
            action_site=action_site,
            xtion_site=xtion_site,
            magnitude_func=logic,
        )

    @classmethod
    def stroke_spring(
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

        def logic(d: float, v: float, r0: float) -> float:
            k = stiffness.value if isinstance(stiffness, NamedValue) else stiffness
            c = damping.value if isinstance(damping, NamedValue) else damping
            f_0 = preload.value if isinstance(preload, NamedValue) else preload
            d_f = max_stroke.value if isinstance(max_stroke, NamedValue) else max_stroke

            delta_d = d - r0

            if 0 <= delta_d <= d_f:
                return -1.0 * (f_0 + k * delta_d + c * v)
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
        xtion_site: Site | None = None,
        stiffness: float | NamedValue[float] = 0.0,
        damping: float | NamedValue[float] = 0.0,
        rest_length: float = 0.0,
    ) -> Self:
        """
        Creates a spring-damper that only acts when compressed (dist < rest_length). Useful for bumpers, feet, push-off springs, or end-stops.
        """

        def logic(d: float, v: float, r0: float) -> float:
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
        xtion_site: Site | None = None,
        stiffness: float | NamedValue[float] = 0.0,
        damping: float | NamedValue[float] = 0.0,
        rest_length: float = 0.0,
    ) -> Self:
        """
        Creates a spring-damper that only acts when extended (dist > rest_length). Useful for cables, bungees, or tendons.
        """

        def logic(d: float, v: float, r0: float) -> float:
            if d > rest_length:
                return _ideal_force_logic(d, v, stiffness, damping, rest_length)
            return 0.0

        return cls(
            name=name,
            action_site=action_site,
            xtion_site=xtion_site,
            magnitude_func=logic,
        )


class GeneralForce(ForcingFunction):
    """A 6-DOF force/torque applier."""

    fx: Callable[[float], float] = lambda t: 0.0
    fy: Callable[[float], float] = lambda t: 0.0
    fz: Callable[[float], float] = lambda t: 0.0
    tx: Callable[[float], float] = lambda t: 0.0
    ty: Callable[[float], float] = lambda t: 0.0
    tz: Callable[[float], float] = lambda t: 0.0

    def calculate(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        results_manager: ResultsManager | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        t = mj_data.time
        f_raw = np.array([self.fx(t), self.fy(t), self.fz(t)])
        t_raw = np.array([self.tx(t), self.ty(t), self.tz(t)])
        return self._get_world_vectors(mj_model, mj_data, f_raw, t_raw)
