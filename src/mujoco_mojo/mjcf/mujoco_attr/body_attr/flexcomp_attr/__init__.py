"""Defines child attributes of the FlexComp class."""

from .contact import FlexCompContact
from .edge import FlexCompEdge
from .elasticity import FlexCompElasticity
from .pin import FlexCompPin

__all__ = [
    "FlexCompContact",
    "FlexCompEdge",
    "FlexCompElasticity",
    "FlexCompPin",
]
