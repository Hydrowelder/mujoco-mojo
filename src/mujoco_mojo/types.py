from __future__ import annotations

from enum import StrEnum, auto
from typing import Annotated, Tuple, TypeAlias

from numpydantic import NDArray, Shape
from pydantic import Field

__all__ = ["Vec2", "Vec3", "Vec4", "Vec5", "GeomType", "Integrator"]

ActuatorGroup = Annotated[int, Field(ge=0, le=30)]

GeomGroup = Annotated[int, Field(ge=0, le=30)]
InertiaGroupRange = Tuple[GeomGroup, GeomGroup]

Vec2: TypeAlias = NDArray[Shape["2"], float | int]  # type: ignore
Vec3: TypeAlias = NDArray[Shape["3"], float | int]  # type: ignore
Vec4: TypeAlias = NDArray[Shape["4"], float | int]  # type: ignore
Vec5: TypeAlias = NDArray[Shape["5"], float | int]  # type: ignore


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


class Inertia(StrEnum):
    CONVEX = auto()
    EXACT = auto()
    LEGACY = auto()
    SHELL = auto()


class Type(StrEnum):
    D2 = "2d"
    CUBE = "cube"
    SKYBOX = "skybox"


class ColorSpace(StrEnum):
    AUTO = auto()
    LINEAR = auto()
    SRGB = auto()


class Mark(StrEnum):
    NONE = auto()
    EDGE = auto()
    CROSS = auto()
    RANDOM = auto()


class TextureBuiltIn(StrEnum):
    NONE = auto()
    GRADIENT = auto()
    CHECKER = auto()
    FLAT = auto()
