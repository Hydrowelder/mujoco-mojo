from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.orientation import Orientation
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.types import (
    GeomType,
    MaterialName,
    Vec2,
    Vec3,
    Vec4,
    Vec6,
    VecN,
)

__all__ = [
    "Site",
    "SiteSphere",
    "SiteCapsule",
    "SiteEllipsoid",
    "SiteCylinder",
    "SiteBox",
]

_site_attr = (
    "name",
    "class_",
    "type",
    "group",
    "pos",
    "orientation",
    "material",
    "size",
    "fromto",
    "rgba",
    "user",
)


class SiteBase(XMLModel):
    """This element creates a site, which is a simplified and restricted kind of geom. A small subset of the geom attributes are available here; see the geom element for their detailed documentation. Semantically sites represent locations of interest relative to the body frames. Sites do not participate in collisions and computation of body masses and inertias. The geometric shapes that can be used to render sites are limited to a subset of the available geom types. However sites can be used in some places where geoms are not allowed: mounting sensors, specifying via-points of spatial tendons, constructing slider-crank transmissions for actuators."""

    model_config = {"extra": "forbid"}

    tag = "site"

    name: Optional[str] = None
    """Name of the site."""

    class_: Optional[str] = None
    """Defaults class for setting unspecified attributes."""

    group: Optional[int] = None
    """Integer group to which the site belongs. This attribute can be used for custom tags. It is also used by the visualizer to enable and disable the rendering of entire groups of sites."""

    material: Optional[MaterialName] = None
    """Material used to specify the visual properties of the site."""

    rgba: Optional[Vec4] = None
    """Color and transparency. If this value is different from the internal default, it overrides the corresponding material properties."""

    fromto: Optional[Vec6] = None
    """This attribute can only be used with capsule, cylinder, ellipsoid and box sites. It provides an alternative specification of the site length as well as the frame position and orientation. The six numbers are the 3D coordinates of one point followed by the 3D coordinates of another point. The elongated part of the site connects these two points, with the +Z axis of the site's frame oriented from the first towards the second point. The frame orientation is obtained with the same procedure as the zaxis attribute described in Frame orientations. The frame position is in the middle between the two points. If this attribute is specified, the remaining position and orientation-related attributes are ignored."""

    pos: Optional[Pos] = None
    """Position of the site frame."""

    orientation: Optional[Orientation] = None
    """Orientation of the site frame. See Frame orientations."""

    user: Optional[VecN] = None
    """See User parameters."""


class SiteSphere(SiteBase):
    """This element creates a sphere site."""

    attributes = _site_attr + ("size",)
    type: Literal[GeomType.SPHERE] = GeomType.SPHERE
    """Type of geometric shape. The keywords have the following meaning:

    The `sphere` type defines a sphere. This and the next four types correspond to built-in geometric primitives. These primitives are treated as analytic surfaces for collision detection purposes, in many cases relying on custom pair- wise collision routines. Models including only planes, spheres, capsules and boxes are the most efficient in terms of collision detection. Other geom types invoke the general-purpose convex collider. The sphere is centered at the geom's position. Only one size parameter is used, specifying the radius of the sphere. Rendering of geometric primitives is done with automatically generated meshes whose density can be adjusted via quality. The sphere mesh is triangulated along the lines of latitude and longitude, with the Z axis passing through the north and south pole. This can be useful in wireframe mode for visualizing frame orientation."""

    size: Optional[float] = None
    """Radius of the sphere.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


class SiteCapsule(SiteBase):
    """This element creates a capsule site."""

    attributes = _site_attr + ("size",)
    type: Literal[GeomType.CAPSULE] = GeomType.CAPSULE
    """Type of geometric shape.

    The `capsule` type defines a capsule, which is a cylinder capped with two half-spheres. It is oriented along the Z axis of the geom's frame. When the geom frame is specified in the usual way, two size parameters are required: the radius of the capsule followed by the half-height of the cylinder part. However capsules as well as cylinders can also be thought of as connectors, allowing an alternative specification with the fromto attribute below. In that case only one size parameter is required, namely the radius of the capsule.
    """

    size: Optional[Vec2 | float] = None
    """Radius of the capsule; half-length of the cylinder part when not using the fromto specification.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


class SiteEllipsoid(SiteBase):
    """This element creates a ellipsoid site."""

    attributes = _site_attr + ("size",)
    type: Literal[GeomType.ELLIPSOID] = GeomType.ELLIPSOID
    """Type of geometric shape.

    The `ellipsoid` type defines a ellipsoid. This is a sphere scaled separately along the X, Y and Z axes of the local frame. It requires three size parameters, corresponding to the three radii. Note that even though ellipsoids are smooth, their collisions are handled via the general-purpose convex collider. The only exception are plane-ellipsoid collisions which are computed analytically.
    """

    size: Optional[Vec3] = None
    """X radius; Y radius; Z radius.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


class SiteCylinder(SiteBase):
    """This element creates a cylinder site."""

    attributes = _site_attr + ("size",)
    type: Literal[GeomType.CYLINDER] = GeomType.CYLINDER
    """Type of geometric shape.

    The `cylinder` type defines a cylinder. It requires two size parameters: the radius and half-height of the cylinder. The cylinder is oriented along the Z axis of the geom's frame. It can alternatively be specified with the fromto attribute below.
    """

    size: Optional[Vec2 | float] = None
    """Radius of the cylinder; half-length of the cylinder when not using the fromto specification.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


class SiteBox(SiteBase):
    """This element creates a box site."""

    attributes = _site_attr + ("size",)
    type: Literal[GeomType.BOX] = GeomType.BOX
    """Type of geometric shape.

    The `box` type defines a box. Three size parameters are required, corresponding to the half-sizes of the box along the X, Y and Z axes of the geom's frame. Note that box-box collisions can generate up to 8 contact points.
    """

    size: Optional[Vec3] = None
    """X half-size; Y half-size; Z half-size.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


Site = Annotated[
    SiteSphere | SiteCapsule | SiteEllipsoid | SiteCylinder | SiteBox,
    Field(discriminator="type"),
]
