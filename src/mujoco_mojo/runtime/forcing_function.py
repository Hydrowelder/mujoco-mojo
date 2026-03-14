from abc import abstractmethod
from collections.abc import Callable
from typing import Self

import mujoco
import numpy as np
from pydantic import PrivateAttr, model_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import Site
from mujoco_mojo.process_manager import NamedValue
from mujoco_mojo.typing import Vec3


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

    relative_to: Site | None = None
    """Frame of reference for the calculated force. If None, uses worldbody."""

    _action_id: int = PrivateAttr(-1)
    _xtion_id: int = PrivateAttr(-1)
    _relative_id: int = PrivateAttr(-1)

    def resolve_ids(self, mj_model: mujoco.MjModel):
        """Caches the integer IDs from the compiled MuJoCo model."""
        self._action_id = self.action_site.get_id(mj_model)
        if self.xtion_site:
            self._xtion_id = self.xtion_site.get_id(mj_model)
        if self.relative_to:
            self._relative_id = self.relative_to.get_id(mj_model)

    @staticmethod
    def _site_pos(site_id: int, mj_data: mujoco.MjData) -> Vec3:
        return mj_data.site_xpos[site_id]

    def action_pos(self, mj_data: mujoco.MjData) -> Vec3:
        return self._site_pos(self._action_id, mj_data)

    def xtion_pos(self, mj_data: mujoco.MjData) -> Vec3:
        return self._site_pos(self._xtion_id, mj_data)

    def rel_to_pos(self, mj_data: mujoco.MjData) -> Vec3:
        return self._site_pos(self._relative_id, mj_data)

    @staticmethod
    def _site_vel(
        site_id: int, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> Vec3:
        res = np.zeros(6)  # 6 element buffer for angular, linear velocity
        mujoco.mj_objectVelocity(
            mj_model, mj_data, mujoco.mjtObj.mjOBJ_SITE, site_id, res, 0
        )
        return res[3:6]

    def action_vel(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        return self._site_vel(self._action_id, mj_model, mj_data)

    def xtion_vel(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        return self._site_vel(self._xtion_id, mj_model, mj_data)

    def rel_to_vel(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        return self._site_vel(self._relative_id, mj_model, mj_data)

    @staticmethod
    def _site_ang_vel(
        site_id: int, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> Vec3:
        res = np.zeros(6)  # 6 element buffer for angular, linear velocity
        mujoco.mj_objectVelocity(
            mj_model, mj_data, mujoco.mjtObj.mjOBJ_SITE, site_id, res, 0
        )
        return res[0:3]

    def action_ang_vel(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        return self._site_ang_vel(self._action_id, mj_model, mj_data)

    def xtion_ang_vel(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        return self._site_ang_vel(self._xtion_id, mj_model, mj_data)

    def rel_to_ang_vel(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        return self._site_ang_vel(self._relative_id, mj_model, mj_data)

    def _get_world_vectors(
        self,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        f_local: Vec3,
        t_local: Vec3,
    ) -> tuple[Vec3, Vec3]:
        """Rotates local force/torque into world coordinates based on relative_to."""
        if self.relative_to is None:
            return f_local, t_local

        # Get the 3x3 rotation matrix for the reference site
        # MuJoCo stores this as a flat 9-element array in site_xmat
        rot = mj_data.site_xmat[self._relative_id].reshape(3, 3)
        return rot @ f_local, rot @ t_local

    @abstractmethod
    def calculate(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> tuple[Vec3, Vec3]:  # TODO write docstring
        """
        Calculate the force for the timestep.

        Args:
            mj_model (mujoco.MjModel): _description_
            mj_data (mujoco.MjData): _description_

        Returns:
            tuple[Vec3, Vec3]: The force and toque vector output.

        """


class PointToPointForce(ForcingFunction):
    """Acts along the line-of-sight between two sites."""

    magnitude_func: Callable[[float, float], float]
    """Func(distance, velocity) -> scalar_force. Can be a regular function, lambda, etc."""

    @model_validator(mode="after")
    def _validate_frame(self) -> Self:
        if self.relative_to is not None:
            raise ValueError(
                f"PointToPointForce '{self.name}' cannot use 'relative_to'. It is natively defined by the line-of-sight between sites."
            )
        return self

    def calculate(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> tuple[Vec3, Vec3]:
        p1 = np.asarray(self.action_pos(mj_data))
        p2 = (
            np.asarray(self.xtion_pos(mj_data))
            if self.xtion_site is not None
            else np.zeros(3)
        )

        r_vec = p1 - p2
        dist = float(np.linalg.norm(r_vec))
        unit_vec = r_vec / dist if dist > 1e-9 else np.zeros(3)

        # simple velocity approximation along the line for damping
        v1 = np.asarray(self.action_vel(mj_model, mj_data))
        v2 = (
            np.asarray(self.xtion_vel(mj_model, mj_data))
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
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> tuple[Vec3, Vec3]:
        t = mj_data.time
        f_raw = np.array([self.fx(t), self.fy(t), self.fz(t)])
        t_raw = np.array([self.tx(t), self.ty(t), self.tz(t)])
        return self._get_world_vectors(mj_model, mj_data, f_raw, t_raw)
