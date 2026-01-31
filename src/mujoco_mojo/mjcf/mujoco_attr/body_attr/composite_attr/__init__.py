"""Defines child attributes of the Composite class."""

from .geom import CompositeGeom
from .joint import CompositeJoint
from .site import CompositeSite
from .skin import Skin

__all__ = [
    "CompositeJoint",
    "CompositeGeom",
    "CompositeSite",
    "Skin",
]
