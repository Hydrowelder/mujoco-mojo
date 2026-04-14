"""Defines child attributes of the Body class."""

from .attach import Attach
from .camera import Camera
from .composite import Composite
from .composite_attr import (
    AnyCompositeGeom,
    CompositeJoint,
    CompositeSite,
    CompositeSkin,
)
from .flexcomp import FlexComp
from .flexcomp_attr import (
    FlexCompContact,
    FlexCompEdge,
    FlexCompElasticity,
    FlexCompPin,
)
from .free_joint import FreeJoint
from .geom import (
    AnyGeom,
    GeomBox,
    GeomCapsule,
    GeomCylinder,
    GeomEllipsoid,
    GeomHField,
    GeomMesh,
    GeomPlane,
    GeomSDF,
    GeomSphere,
)
from .inertial import Inertial
from .joint import Joint
from .light import Light
from .site import (
    AnySite,
    SiteBox,
    SiteCapsule,
    SiteCylinder,
    SiteEllipsoid,
    SiteSphere,
)

__all__ = [
    "AnyCompositeGeom",
    "AnyGeom",
    "AnySite",
    "Attach",
    "Camera",
    "Composite",
    "CompositeJoint",
    "CompositeSite",
    "CompositeSkin",
    "FlexComp",
    "FlexCompContact",
    "FlexCompEdge",
    "FlexCompElasticity",
    "FlexCompPin",
    "FreeJoint",
    "GeomBox",
    "GeomCapsule",
    "GeomCylinder",
    "GeomEllipsoid",
    "GeomHField",
    "GeomMesh",
    "GeomPlane",
    "GeomSDF",
    "GeomSphere",
    "Inertial",
    "Joint",
    "Light",
    "SiteBox",
    "SiteCapsule",
    "SiteCylinder",
    "SiteEllipsoid",
    "SiteSphere",
]
