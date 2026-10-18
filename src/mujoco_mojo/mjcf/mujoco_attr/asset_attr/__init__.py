"""Defines child attributes of the Asset class."""

from .hfield import HField
from .material import Material
from .material_attr import Layer
from .mesh import (
    AnyMesh,
    Mesh,
    MeshCone,
    MeshHemisphere,
    MeshPlate,
    MeshBox,
    MeshCylinder,
    MeshDisc,
    MeshEllipsoid,
    MeshGrid,
    MeshSquare,
    MeshSphere,
    MeshSupersphere,
    MeshTorus,
    MeshWedge,
)
from .model import Model
from .texture import Texture, TextureBuiltIn

__all__ = [
    "AnyMesh",
    "HField",
    "Layer",
    "Material",
    "Mesh",
    "MeshBox",
    "MeshCone",
    "MeshCylinder",
    "MeshDisc",
    "MeshEllipsoid",
    "MeshGrid",
    "MeshHemisphere",
    "MeshPlate",
    "MeshSphere",
    "MeshSquare",
    "MeshSupersphere",
    "MeshTorus",
    "MeshWedge",
    "Model",
    "Texture",
    "TextureBuiltIn",
]
