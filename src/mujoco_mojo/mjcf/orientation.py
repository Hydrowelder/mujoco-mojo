from __future__ import annotations

from enum import StrEnum, auto
from typing import Annotated, Literal, Optional, TypeAlias

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.types import Vec3, Vec4, Vec6

__all__ = [
    "Orientation",
    "Quat",
    "AxisAngle",
    "XYAxes",
    "ZAxis",
    "Euler",
]


class OrientationType(StrEnum):
    QUAT = auto()
    AXISANGLE = auto()
    XYAXES = auto()
    ZAXIS = auto()
    EULER = auto()


class OrientationBase(XMLModel):
    tag = ""


class Quat(OrientationBase):
    type: Literal[OrientationType.QUAT] = OrientationType.QUAT

    attributes = ("quat",)

    quat: Optional[Vec4] = None
    """Orientation of the geom frame. See Frame orientations."""


class AxisAngle(OrientationBase):
    type: Literal[OrientationType.AXISANGLE] = OrientationType.AXISANGLE
    attributes = ("axisangle",)

    axisangle: Optional[Vec4] = None
    """Orientation of the geom frame. See Frame orientations."""


class XYAxes(OrientationBase):
    type: Literal[OrientationType.XYAXES] = OrientationType.XYAXES
    attributes = ("xyaxes",)

    xyaxes: Optional[Vec6] = None
    """Orientation of the geom frame. See Frame orientations."""


class ZAxis(OrientationBase):
    type: Literal[OrientationType.ZAXIS] = OrientationType.ZAXIS
    attributes = ("zaxis",)

    zaxis: Optional[Vec3] = None
    """Orientation of the geom frame. See Frame orientations."""


class Euler(OrientationBase):
    type: Literal[OrientationType.EULER] = OrientationType.EULER
    attributes = ("euler",)

    euler: Optional[Vec3] = None
    """Orientation of the geom frame. See Frame orientations."""


Orientation: TypeAlias = Annotated[
    Quat | AxisAngle | XYAxes | ZAxis | Euler,
    Field(discriminator="type"),
]
