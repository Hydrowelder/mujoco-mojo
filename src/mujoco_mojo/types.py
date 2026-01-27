from __future__ import annotations

from enum import StrEnum, auto
from typing import Annotated, Tuple

from pydantic import Field

__all__ = ["Vec2", "Vec3", "Vec4", "Vec5", "GeomType", "Integrator"]

ActuatorGroup = Annotated[int, Field(ge=0, le=30)]

GeomGroup = Annotated[int, Field(ge=0, le=30)]
InertiaGroupRange = Tuple[GeomGroup, GeomGroup]

Vec2 = Tuple[float, float]
Vec3 = Tuple[float, float, float]
Vec4 = Tuple[float, float, float, float]
Vec5 = Tuple[float, float, float, float, float]


class GeomType(StrEnum):
    PLANE = auto()
    HFIELD = auto()
    SPHERE = auto()
    CAPSULE = auto()
    ELLIPSOID = auto()
    CYLINDER = auto()
    BOX = auto()
    MESH = auto()
    SDF = auto()


class Integrator(StrEnum):
    EULER = "Euler"
    RK4 = "RK4"
    IMPLICIT = "implicit"
    IMPLICITFAST = "implicitfast"


class Cone(StrEnum):
    PYRAMIDAL = auto()
    ELLIPTIC = auto()


class Jacobian(StrEnum):
    DENSE = auto()
    SPARSE = auto()
    AUTO = auto()


class Solver(StrEnum):
    PGS = "PGS"
    CG = "CG"
    NEWTON = "Newton"


class EnableDisable(StrEnum):
    ENABLE = auto()
    DISABLE = auto()


class Coordinate(StrEnum):
    LOCAL = auto()
    GLOBAL = auto()


class Angle(StrEnum):
    RADIAN = auto()
    DEGREE = auto()


class InertiaFromGeom(StrEnum):
    FALSE = auto()
    TRUE = auto()
    AUTO = auto()


class Mode(StrEnum):
    NONE = auto()
    MUSCLE = auto()
    MUSCLEUSER = auto()
    ALL = auto()
