from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import numpy as np
from pytransform3d.transform_manager import TransformManager

from mujoco_mojo.mjcf.orientation import Quat
from mujoco_mojo.mjcf.pose import AnyPose, PoseQuat
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from mujoco_mojo.mjcf.meta.frame import Frame
    from mujoco_mojo.mjcf.mujoco import Mujoco
    from mujoco_mojo.mjcf.mujoco_attr.body import Body, WorldBody

__all__ = ["HasPose", "PoseContext", "PoseRef"]

logger = get_logger(__name__)

_WORLD = "__world__"


@runtime_checkable
class HasPose(Protocol):
    """Structural type for any MJCF element that carries a pose."""

    pose: AnyPose


def _to_T(posed: HasPose) -> np.ndarray:
    T = np.eye(4)
    T[:3, :3] = posed.pose.as_matrix()
    T[:3, 3] = np.asarray(posed.pose.pos, dtype=float)
    return T


def _from_T(T: np.ndarray) -> PoseQuat:
    return Quat.from_matrix(T[:3, :3]).as_pose(pos=T[:3, 3])


class PoseContext:
    """
    Graph of all posed elements in a WorldBody tree for cross-branch pose resolution.

    Every element with a pose (`Body`, any site type, `Frame`, `Camera`, `Light`, etc.) is registered as a node keyed by Python object identity, so no naming is required.

    Attributes:
        _tm: internal pytransform3d `TransformManager` storing pairwise 4x4 transforms.
        _registered: set of `id()` values for every element registered during the tree walk.

    """

    def __init__(self, worldbody: WorldBody) -> None:
        self._tm = TransformManager()
        self._registered: set[int] = set()
        self._build(worldbody)

    def _key(self, obj: object) -> str:
        self._registered.add(id(obj))
        return str(id(obj))

    def _register_posed_children(self, parent_obj: object, parent_key: str) -> None:
        """Registers sites, cameras, and lights of a body as child frames."""
        for attr in ("sites", "cameras", "lights"):
            for child in getattr(parent_obj, attr, ()):
                logger.debug(
                    f"registering {attr[:-1]} {getattr(child, 'name', id(child))}"
                )
                self._tm.add_transform(self._key(child), parent_key, _to_T(child))

    def _walk_frames(self, frm: Frame, parent_key: str) -> None:
        """Recursively registers a Frame and its nested frames."""
        logger.debug(f"registering frame {getattr(frm, 'name', id(frm))}")
        frm_key = self._key(frm)
        self._tm.add_transform(frm_key, parent_key, _to_T(frm))
        for nested in frm.frames:
            self._walk_frames(nested, frm_key)

    def _build(self, worldbody: WorldBody) -> None:
        """Walks the full worldbody tree and registers every posed element."""
        logger.debug("building pose context from worldbody")
        wb_key = self._key(worldbody)
        self._tm.add_transform(wb_key, _WORLD, np.eye(4))
        self._register_posed_children(worldbody, wb_key)
        for frm in worldbody.frames:
            self._walk_frames(frm, wb_key)
        for body in worldbody.bodies:
            self._walk(body, wb_key)

    def _walk(self, body: Body, parent_key: str) -> None:
        """Recursively registers a body and all its descendants."""
        logger.debug(f"registering body {getattr(body, 'name', id(body))}")
        body_key = self._key(body)
        self._tm.add_transform(body_key, parent_key, _to_T(body))
        self._register_posed_children(body, body_key)
        for frm in body.frames:
            self._walk_frames(frm, body_key)
        for child in body.bodies:
            self._walk(child, body_key)

    def local_pose(self, frame: HasPose, relative_to: HasPose) -> PoseQuat:
        """Returns the pose of `frame` expressed in `relative_to`'s coordinate system."""
        if id(frame) not in self._registered:
            msg = "frame is not registered in the pose context. Ensure it is part of the worldbody tree before resolving poses."
            logger.error(msg)
            raise ValueError(msg)
        if id(relative_to) not in self._registered:
            msg = "relative_to is not registered in the pose context. Ensure it is part of the worldbody tree before resolving poses."
            logger.error(msg)
            raise ValueError(msg)
        try:
            T = self._tm.get_transform(str(id(frame)), str(id(relative_to)))
        except Exception as exc:
            msg = f"Cannot resolve transform from frame to relative_to: {exc}"
            logger.error(msg)
            raise ValueError(msg) from exc
        return _from_T(T)


@dataclass(frozen=True)
class PoseRef:
    """Deferred pose reference resolved via `Mujoco.local_pose`. `relative_to` must be the direct parent body of the element receiving the resolved pose."""

    frame: HasPose = field()
    """The element whose world-space pose you want to resolve."""

    relative_to: HasPose = field()
    """The element whose local coordinate system the result is expressed in. Must be the parent body of whatever element receives the resolved pose."""

    def to_quat(self, mjcf: Mujoco) -> PoseQuat:
        """Resolves this reference to a concrete `PoseQuat` in `relative_to`'s coordinate system."""
        return mjcf.local_pose(self.frame, self.relative_to)
