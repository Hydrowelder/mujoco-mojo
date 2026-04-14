"""Defines child attributes of the Asset class."""

from .hfield import HField
from .material import Material
from .material_attr import Layer
from .mesh import (
    Mesh,
    MeshCone,
    MeshHemisphere,
    MeshPlate,
    MeshSphere,
    MeshSupersphere,
    MeshTorus,
    MeshWedge,
)
from .model import Model
from .texture import Texture, TextureBuiltIn

__all__ = [
    "HField",
    "Layer",
    "Material",
    "Mesh",
    "MeshCone",
    "MeshHemisphere",
    "MeshPlate",
    "MeshSphere",
    "MeshSupersphere",
    "MeshTorus",
    "MeshWedge",
    "Model",
    "Texture",
    "TextureBuiltIn",
]
