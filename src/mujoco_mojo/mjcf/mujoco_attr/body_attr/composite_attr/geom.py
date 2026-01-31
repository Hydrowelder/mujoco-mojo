"""Defines the geometric types for composites.

!!! note
    I was pretty lazy when I did this, I just decided to have these type inherit from their respective Geom class. That is not a super clean way to do it because it means that these objects may have attributes that MuJoCo will just ignore. The XML attributes defined here are restricted to the subset that only the composite geometries have.

    Sorry...
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import (
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

__all__ = [
    "CompositePlane",
    "CompositeHField",
    "CompositeSphere",
    "CompositeCapsule",
    "CompositeEllipsoid",
    "CompositeCylinder",
    "CompositeBox",
    "CompositeMesh",
    "CompositeSDF",
]

_composite_geom_attr = (
    "type",
    "contype",
    "conaffinity",
    "condim",
    "group",
    "priority",
    "material",
    "rgba",
    "friction",
    "mass",
    "density",
    "solmix",
    "solref",
    "solimp",
    "margin",
    "gap",
)
"""Composite geometry XML attributes."""


class CompositePlane(GeomPlane):
    """Same as GeomPlane with different attributes.

    This sub-element adjusts the attributes of the geoms in the composite object. The default attributes are the same as in the rest of MJCF (except that user-defined defaults have no effect here). Note that the geom sub-element can appears only once, unlike joint and tendon sub-elements which can appear multiple times. This is because different kinds of joints and tendons have different sets of attributes, while all geoms in the composite object are identical."""

    attributes = _composite_geom_attr + ("size",)


class CompositeHField(GeomHField):
    """Same as GeomHField with different attributes.

    This sub-element adjusts the attributes of the geoms in the composite object. The default attributes are the same as in the rest of MJCF (except that user-defined defaults have no effect here). Note that the geom sub-element can appears only once, unlike joint and tendon sub-elements which can appear multiple times. This is because different kinds of joints and tendons have different sets of attributes, while all geoms in the composite object are identical."""

    attributes = _composite_geom_attr


class CompositeSphere(GeomSphere):
    """Same as GeomSphere with different attributes.

    This sub-element adjusts the attributes of the geoms in the composite object. The default attributes are the same as in the rest of MJCF (except that user-defined defaults have no effect here). Note that the geom sub-element can appears only once, unlike joint and tendon sub-elements which can appear multiple times. This is because different kinds of joints and tendons have different sets of attributes, while all geoms in the composite object are identical."""

    attributes = _composite_geom_attr + ("size",)


class CompositeCapsule(GeomCapsule):
    """Same as GeomCapsule with different attributes.

    This sub-element adjusts the attributes of the geoms in the composite object. The default attributes are the same as in the rest of MJCF (except that user-defined defaults have no effect here). Note that the geom sub-element can appears only once, unlike joint and tendon sub-elements which can appear multiple times. This is because different kinds of joints and tendons have different sets of attributes, while all geoms in the composite object are identical."""

    attributes = _composite_geom_attr + ("size",)


class CompositeEllipsoid(GeomEllipsoid):
    """Same as GeomEllipsoid with different attributes.

    This sub-element adjusts the attributes of the geoms in the composite object. The default attributes are the same as in the rest of MJCF (except that user-defined defaults have no effect here). Note that the geom sub-element can appears only once, unlike joint and tendon sub-elements which can appear multiple times. This is because different kinds of joints and tendons have different sets of attributes, while all geoms in the composite object are identical."""

    attributes = _composite_geom_attr + ("size",)


class CompositeCylinder(GeomCylinder):
    """Same as GeomCylinder with different attributes.

    This sub-element adjusts the attributes of the geoms in the composite object. The default attributes are the same as in the rest of MJCF (except that user-defined defaults have no effect here). Note that the geom sub-element can appears only once, unlike joint and tendon sub-elements which can appear multiple times. This is because different kinds of joints and tendons have different sets of attributes, while all geoms in the composite object are identical."""

    attributes = _composite_geom_attr + ("size",)


class CompositeBox(GeomBox):
    """Same as GeomBox with different attributes.

    This sub-element adjusts the attributes of the geoms in the composite object. The default attributes are the same as in the rest of MJCF (except that user-defined defaults have no effect here). Note that the geom sub-element can appears only once, unlike joint and tendon sub-elements which can appear multiple times. This is because different kinds of joints and tendons have different sets of attributes, while all geoms in the composite object are identical."""

    attributes = _composite_geom_attr + ("size",)


class CompositeMesh(GeomMesh):
    """Same as GeomMesh with different attributes.

    This sub-element adjusts the attributes of the geoms in the composite object. The default attributes are the same as in the rest of MJCF (except that user-defined defaults have no effect here). Note that the geom sub-element can appears only once, unlike joint and tendon sub-elements which can appear multiple times. This is because different kinds of joints and tendons have different sets of attributes, while all geoms in the composite object are identical."""

    attributes = _composite_geom_attr


class CompositeSDF(GeomSDF):
    """Same as GeomSDF with different attributes.

    This sub-element adjusts the attributes of the geoms in the composite object. The default attributes are the same as in the rest of MJCF (except that user-defined defaults have no effect here). Note that the geom sub-element can appears only once, unlike joint and tendon sub-elements which can appear multiple times. This is because different kinds of joints and tendons have different sets of attributes, while all geoms in the composite object are identical."""

    attributes = _composite_geom_attr


CompositeGeom = Annotated[
    CompositePlane
    | CompositeHField
    | CompositeSphere
    | CompositeCapsule
    | CompositeEllipsoid
    | CompositeCylinder
    | CompositeBox
    | CompositeMesh
    | CompositeSDF,
    Field(discriminator="type"),
]
