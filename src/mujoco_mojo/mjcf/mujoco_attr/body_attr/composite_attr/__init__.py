"""Defines child attributes of the Composite class."""

from .geom import AnyCompositeGeom
from .joint import CompositeJoint
from .site import CompositeSite
from .skin import CompositeSkin

__all__ = [
    "AnyCompositeGeom",
    "CompositeJoint",
    "CompositeSite",
    "CompositeSkin",
]
