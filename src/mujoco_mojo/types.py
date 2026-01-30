from __future__ import annotations

from enum import StrEnum, auto
from typing import Annotated, Tuple

from numpydantic import NDArray, Shape
from pydantic import Field

__all__ = ["Vec2", "Vec3", "Vec4", "Vec5", "GeomType", "Integrator"]


ActuatorGroup = Annotated[int, Field(ge=0, le=30)]
"""An integer representing an actuator group index. Must be between 0 and 30 inclusive."""

GeomGroup = Annotated[int, Field(ge=0, le=30)]
"""An integer representing a geom group index. Must be between 0 and 30 inclusive."""

InertiaGroupRange = Tuple[GeomGroup, GeomGroup]
"""A tuple specifying the inclusive range of geom groups used for inertia computation."""

Vec2 = Annotated[NDArray[Shape["2"], float | int], ...]
"""A 2-element numeric array."""

Vec3 = Annotated[NDArray[Shape["3"], float | int], ...]
"""A 3-element numeric array, often used for positions or directions."""

Vec4 = Annotated[NDArray[Shape["4"], float | int], ...]
"""A 4-element numeric array, often used for RGBA colors or quaternions."""

Vec5 = Annotated[NDArray[Shape["5"], float | int], ...]
"""A 5-element numeric array."""

Vec6 = Annotated[NDArray[Shape["6"], float | int], ...]
"""A 6-element numeric array."""

VecN = Annotated[NDArray[Shape["*"], float | int], ...]  # type: ignore  # noqa: F722
"""An N-element numeric array of arbitrary length."""


class GeomType(StrEnum):
    """Enumeration of supported geometric types in MuJoCo."""

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
    """Enumeration of simulation integrators."""

    EULER = "Euler"
    RK4 = "RK4"
    IMPLICIT = "implicit"
    IMPLICITFAST = "implicitfast"


class Cone(StrEnum):
    """Cone types used in collision/contact modeling."""

    PYRAMIDAL = auto()
    ELLIPTIC = auto()


class Jacobian(StrEnum):
    """Jacobian computation methods."""

    DENSE = auto()
    SPARSE = auto()
    AUTO = auto()


class Solver(StrEnum):
    """Solver algorithms for constraint resolution."""

    PGS = "PGS"
    CG = "CG"
    NEWTON = "Newton"


class EnableDisable(StrEnum):
    """Enable or disable a feature."""

    ENABLE = auto()
    DISABLE = auto()


class Coordinate(StrEnum):
    """Reference frame for coordinates."""

    LOCAL = auto()
    GLOBAL = auto()


class Angle(StrEnum):
    """Unit for angles."""

    RADIAN = auto()
    DEGREE = auto()


class InertiaFromGeom(StrEnum):
    """Specifies how inertia is computed from geometry."""

    FALSE = auto()
    TRUE = auto()
    AUTO = auto()


class Mode(StrEnum):
    """Operational mode flags for components like muscles."""

    NONE = auto()
    MUSCLE = auto()
    MUSCLEUSER = auto()
    ALL = auto()


class Inertia(StrEnum):
    """Methods for inertia calculation."""

    CONVEX = auto()
    EXACT = auto()
    LEGACY = auto()
    SHELL = auto()


class Type(StrEnum):
    """Shape type for textures or visual elements."""

    D2 = "2d"
    CUBE = "cube"
    SKYBOX = "skybox"


class ColorSpace(StrEnum):
    """Color space options for textures and materials."""

    AUTO = auto()
    LINEAR = auto()
    SRGB = auto()


class Mark(StrEnum):
    """Mark type for rendering markers."""

    NONE = auto()
    EDGE = auto()
    CROSS = auto()
    RANDOM = auto()


class TextureBuiltIn(StrEnum):
    """Built-in texture patterns."""

    NONE = auto()
    GRADIENT = auto()
    CHECKER = auto()
    FLAT = auto()


class Sleep(StrEnum):
    """Sleep modes for simulation objects."""

    AUTO = auto()
    NEVER = auto()
    ALLOWED = auto()
    INIT = auto()


class JointType(StrEnum):
    """Types of joints supported in MuJoCo."""

    FREE = auto()
    BALL = auto()
    SLIDE = auto()
    HINGE = auto()


class Limited(StrEnum):
    """Flag to indicate if a joint or actuator is limited."""

    FALSE = auto()
    TRUE = auto()
    AUTO = auto()


class ActuatorFrcLimited(StrEnum):
    """Specifies if actuator force is limited."""

    FALSE = auto()
    TRUE = auto()
    AUTO = auto()


class Align(StrEnum):
    """Specifies alignment options for components."""

    FALSE = auto()
    TRUE = auto()
    AUTO = auto()


class FluidShape(StrEnum):
    """Shape of fluid particles."""

    NONE = auto()
    ELLIPSOID = auto()
