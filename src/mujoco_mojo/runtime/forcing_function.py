from abc import abstractmethod
from collections.abc import Callable
from typing import Self

import mujoco
import numpy as np
from pydantic import model_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import Site
from mujoco_mojo.process_manager import NamedValue
from mujoco_mojo.runtime.result_manager import ResultsManager


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

    log_to_results: bool = False
    """If True, the forcing function force/torque values will be logged at every step."""

    def resolve_ids(self, mj_model: mujoco.MjModel):
        """Caches the integer IDs from the compiled MuJoCo model."""
        self.action_site.get_id(mj_model)
        if self.xtion_site:
            self.xtion_site.get_id(mj_model)
        if self.rel_to_site:
            self.rel_to_site.get_id(mj_model)

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
    ) -> tuple[np.ndarray, np.ndarray]:  # TODO write docstring
        """
        Calculate the force for the timestep.

        Args:
            mj_model (mujoco.MjModel): _description_
            mj_data (mujoco.MjData): _description_
            results_manager (ResultsManager): _description_

        Returns:
            tuple[np.ndarray, np.ndarray]: The force and toque vector output.

        """

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

        if self.log_to_results and results_manager:
            for i, k in enumerate("xyz"):
                results_manager.post(f"{self.name}_force_{k}", f_world[i])
                results_manager.post(f"{self.name}_torque_{k}", t_world[i])

        # apply to action site
        mujoco.mj_applyFT(
            m=mj_model,
            d=mj_data,
            force=f_world,
            torque=t_world,
            point=self.action_site.rt_pos(mj_model, mj_data),
            body=self.action_site.rt_parent_body(mj_model),
            # target generalized force array
            qfrc_target=mj_data.qfrc_applied,
        )

        # apply reaction force
        if self.xtion_site is not None:
            # Newton's 3rd Law
            mujoco.mj_applyFT(
                m=mj_model,
                d=mj_data,
                force=-f_world,
                torque=-t_world,
                point=self.xtion_site.rt_pos(mj_model, mj_data),
                body=self.xtion_site.rt_parent_body(mj_model),
                qfrc_target=mj_data.qfrc_applied,
            )


class PointToPointForce(ForcingFunction):
    """Acts along the line-of-sight between two sites."""

    magnitude_func: Callable[[float, float], float]
    """Func(distance, velocity) -> scalar_force. Can be a regular function, lambda, etc."""

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
        p1 = self.action_site.rt_pos(mj_model, mj_data)
        p2 = (
            self.xtion_site.rt_pos(mj_model, mj_data)
            if self.xtion_site is not None
            else np.zeros(3)
        )

        r_vec = p1 - p2
        dist = float(np.linalg.norm(r_vec))
        unit_vec = r_vec / dist if dist > 1e-9 else np.zeros(3)

        # simple velocity approximation along the line for damping
        v1 = self.action_site.rt_vel(mj_model, mj_data)
        v2 = (
            self.xtion_site.rt_vel(mj_model, mj_data)
            if self.xtion_site is not None
            else np.zeros(3)
        )
        vel = np.dot(v1 - v2, unit_vec)

        # user defined logic (spring, spring damper, etc.)
        f_mag = self.magnitude_func(dist, vel)
        f_vec = unit_vec * f_mag

        return f_vec, np.zeros(3)

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

        def logic(d: float, v: float) -> float:
            return _ideal_force_logic(d, v, stiffness, damping, rest_length)

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

        def logic(d: float, v: float) -> float:
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

        def logic(d: float, v: float) -> float:
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
