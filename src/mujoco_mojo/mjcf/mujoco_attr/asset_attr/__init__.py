"""Defines child attributes of the Asset class."""

from .hfield import HField
from .material import Material
from .material_attr import Layer
from .mesh import Mesh
from .model import Model
from .texture import Texture

__all__ = [
    "HField",
    "Material",
    "Layer",
    "Mesh",
    "Model",
    "Texture",
]
