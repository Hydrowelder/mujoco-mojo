"""Defines child attributes of the Mujoco class."""

from .asset import Asset
from .asset_attr import (
    HField,
    Layer,
    Material,
    Mesh,
    Model,
    Texture,
)
from .body import Body, WorldBody
from .body_attr import (
    Attach,
    Camera,
    Composite,
    CompositeGeom,
    CompositeJoint,
    CompositeSite,
    FlexComp,
    FreeJoint,
    Geom,
    GeomBox,
    GeomCapsule,
    GeomCylinder,
    GeomEllipsoid,
    GeomHField,
    GeomMesh,
    GeomPlane,
    GeomSDF,
    GeomSphere,
    Inertial,
    Joint,
    Light,
    Site,
    SiteBox,
    SiteCapsule,
    SiteCylinder,
    SiteEllipsoid,
    SiteSphere,
    Skin,
)
from .compiler import Compiler
from .compiler_attr import LengthRange
from .contact import Contact
from .contact_attr import Exclude, Pair
from .option import Option
from .option_attr import Flag
from .size import Size
from .statistic import Statistic

__all__ = [
    "Asset",
    "Attach",
    "Body",
    "Camera",
    "Compiler",
    "Composite",
    "CompositeGeom",
    "CompositeJoint",
    "CompositeSite",
    "Contact",
    "Exclude",
    "Flag",
    "FlexComp",
    "FreeJoint",
    "Geom",
    "GeomBox",
    "GeomCapsule",
    "GeomCylinder",
    "GeomEllipsoid",
    "GeomHField",
    "GeomMesh",
    "GeomPlane",
    "GeomSDF",
    "GeomSphere",
    "HField",
    "Inertial",
    "Joint",
    "Layer",
    "LengthRange",
    "Light",
    "Material",
    "Mesh",
    "Model",
    "Option",
    "Pair",
    "Site",
    "SiteBox",
    "SiteCapsule",
    "SiteCylinder",
    "SiteEllipsoid",
    "SiteSphere",
    "Size",
    "Skin",
    "Statistic",
    "Texture",
    "WorldBody",
]
