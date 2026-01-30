from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.types import FluidShape, GeomType, Vec2, Vec3, Vec4, Vec5, Vec6, VecN

__all__ = [
    "Geom",
    "GeomPlane",
    "GeomHField",
    "GeomSphere",
    "GeomCapsule",
    "GeomEllipsoid",
    "GeomCylinder",
    "GeomBox",
    "GeomMesh",
    "GeomSDF",
]

_geom_attr = (
    "name",
    "class_",
    "type",
    "contype",
    "conaffinity",
    "condim",
    "group",
    "priority",
    "material",
    "friction",
    "mass",
    "density",
    "shellinertia",
    "solmix",
    "solref",
    "solimp",
    "margin",
    "gap",
    "fromto",
    "pos",
    "quat",
    "axisangle",
    "xyaxes",
    "zaxis",
    "euler",
    "hfield",
    "mesh",
    "fitscale",
    "rgba",
    "fluidshape",
    "fluidcoef",
    "user",
)


class GeomBase(XMLModel):
    """This element creates a geom, and attaches it rigidly to the body within which the geom is defined. Multiple geoms can be attached to the same body. At runtime they determine the appearance and collision properties of the body. At compile time they can also determine the inertial properties of the body, depending on the presence of the inertial element and the setting of the inertiafromgeom attribute of compiler. This is done by summing the masses and inertias of all geoms attached to the body with geom group in the range specified by the inertiagrouprange attribute of compiler. The geom masses and inertias are computed using the geom shape, a specified density or a geom mass which implies a density, and the assumption of uniform density.

    Geoms are not strictly required for physics simulation. One can create and simulate a model that only has bodies and joints. Such a model can even be visualized, using equivalent inertia boxes to represent bodies. Only contact forces would be missing from such a simulation. We do not recommend using such models, but knowing that this is possible helps clarify the role of bodies and geoms in MuJoCo.
    """

    model_config = {"extra": "forbid"}

    tag = "geom"

    name: Optional[str] = None
    """Name of the geom."""

    class_: Optional[str] = None
    """Defaults class for setting unspecified attributes."""

    # size: Optional[Tuple[float, ...] | float] = None
    # """Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.

    # | Type      | Number | Description                                                                                                                                                                        |
    # |-----------|--------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
    # | plane     | 3      | X half-size; Y half-size; spacing between square grid lines for rendering. If either the X or Y half-size is 0, the plane is rendered as infinite in the dimension(s) with 0 size. |
    # | hfield    | 0      | The geom sizes are ignored and the height field sizes are used instead.                                                                                                            |
    # | sphere    | 1      | Radius of the sphere.                                                                                                                                                              |
    # | capsule   | 1 or 2 | Radius of the capsule; half-length of the cylinder part when not using the `fromto` specification.                                                                                 |
    # | ellipsoid | 3      | X radius; Y radius; Z radius.                                                                                                                                                      |
    # | cylinder  | 1 or 2 | Radius of the cylinder; half-length of the cylinder when not using the `fromto` specification.                                                                                     |
    # | box       | 3      | X half-size; Y half-size; Z half-size.                                                                                                                                             |
    # | mesh      | 0      | The geom sizes are ignored and the mesh sizes are used instead.                                                                                                                    |
    # """

    contype: Optional[int] = None
    """This attribute and the next specify 32-bit integer bitmasks used for contact filtering of dynamically generated contact pairs. See Collision detection in the Computation chapter. Two geoms can collide if the contype of one geom is compatible with the conaffinity of the other geom or vice versa. Compatible means that the two bitmasks have a common bit set to 1."""

    conaffinity: Optional[int] = None
    """Bitmask for contact filtering; see contype above."""

    condim: Optional[Literal[1, 3, 4, 6]] = None
    """The dimensionality of the contact space for a dynamically generated contact pair is set to the maximum of the condim values of the two participating geoms. See Contact in the Computation chapter. The allowed values and their meaning are:

    | condim | Description                                                                                                                                                                                                                                 |
    |:-------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | 1      | Frictionless contact.                                                                                                                                                                                                                       |
    | 3      | Regular frictional contact, opposing slip in the tangent plane.                                                                                                                                                                             |
    | 4      | Frictional contact, opposing slip in the tangent plane and rotation around the contact normal. This is useful for modeling soft contacts (independent of contact penetration).                                                              |
    | 6      | Frictional contact, opposing slip in the tangent plane, rotation around the contact normal and rotation around the two axes of the tangent plane. The latter frictional effects are useful for |preventing objects from indefinite rolling. |"""

    group: Optional[int] = None
    """This attribute specifies an integer group to which the geom belongs. The only effect on the physics is at compile time, when body masses and inertias are inferred from geoms selected based on their group; see inertiagrouprange attribute of compiler. At runtime this attribute is used by the visualizer to enable and disable the rendering of entire geom groups. By default, groups 0, 1 and 2 are visible, while all other groups are invisible. The group attribute can also be used as a tag for custom computations."""

    priority: Optional[int] = None
    """The geom priority determines how the properties of two colliding geoms are combined to form the properties of the contact. This interacts with the solmix attribute. See Contact parameters."""

    material: Optional[str] = None
    """If specified, this attribute applies a material to the geom. Otherwise, if unspecified and the type of the geom is a mesh the compiler will apply the mesh asset material if present.

    The material determines the visual properties of the geom. The only exception is color: if the rgba attribute below is different from its internal default, it takes precedence while the remaining material properties are still applied. Note that if the same material is referenced from multiple geoms (as well as sites and tendons) and the user changes some of its properties at runtime, these changes will take effect immediately for all model elements referencing the material. This is because the compiler saves the material and its properties as a separate element in mjModel, and the elements using this material only keep a reference to it."""

    rgba: Optional[Vec4] = None
    """Instead of creating material assets and referencing them, this attribute can be used to set color and transparency only. This is not as flexible as the material mechanism, but is more convenient and is often sufficient. If the value of this attribute is different from the internal default, it takes precedence over the material."""

    friction: Optional[Vec3] = None
    """Contact friction parameters for dynamically generated contact pairs. The first number is the sliding friction, acting along both axes of the tangent plane. The second number is the torsional friction, acting around the contact normal. The third number is the rolling friction, acting around both axes of the tangent plane. The friction parameters for the contact pair are combined depending on the solmix and priority attributes, as explained in Contact parameters. See the general Contact section for descriptions of the semantics of this attribute."""

    mass: Optional[float] = None
    """If this attribute is specified, the density attribute below is ignored and the geom density is computed from the given mass, using the geom shape and the assumption of uniform density. The computed density is then used to obtain the geom inertia. Recall that the geom mass and inertia are only used during compilation, to infer the body mass and inertia if necessary. At runtime only the body inertial properties affect the simulation; the geom mass and inertia are not saved in mjModel."""

    density: Optional[float] = None
    """Material density used to compute the geom mass and inertia. The computation is based on the geom shape and the assumption of uniform density. The internal default of 1000 is the density of water in SI units. This attribute is used only when the mass attribute above is unspecified. If shellinertia is "false" (the default), density has semantics of mass/volume; if "true", it has semantics of mass/area."""

    shellinertia: Optional[bool] = None
    """If true, the geom's inertia is computed assuming that all the mass is concentrated on the surface. In this case density is interpreted as surface rather than volumetric density. This attribute only applies to primitive geoms and is ignored for meshes. Surface inertia for meshes can be specified by setting the asset/mesh/inertia attribute to "shell"."""

    solmix: Optional[float] = None
    """This attribute specifies the weight used for averaging of contact parameters, and interacts with the priority attribute. See Contact parameters."""

    solref: Optional[Vec2] = None
    """Constraint solver parameters for contact simulation. See Solver parameters."""

    solimp: Optional[Vec5] = None
    """Constraint solver parameters for contact simulation. See Solver parameters."""

    margin: Optional[float] = None
    """Distance threshold below which contacts are detected and included in the global array mjData.contact. This however does not mean that contact force will be generated. A contact is considered active only if the distance between the two geom surfaces is below margin-gap. Recall that constraint impedance can be a function of distance, as explained in Solver parameters. The quantity this function is applied to is the distance between the two geoms minus the margin plus the gap."""

    gap: Optional[float] = None
    """This attribute is used to enable the generation of inactive contacts, i.e., contacts that are ignored by the constraint solver but are included in mjData.contact for the purpose of custom computations. When this value is positive, geom distances between margin and margin-gap correspond to such inactive contacts."""

    fromto: Optional[Vec6] = None
    """This attribute can only be used with capsule, box, cylinder and ellipsoid geoms. It provides an alternative specification of the geom length as well as the frame position and orientation. The six numbers are the 3D coordinates of one point followed by the 3D coordinates of another point. The elongated part of the geom connects these two points, with the +Z axis of the geom's frame oriented from the first towards the second point, while in the perpendicular direction, the geom sizes are both equal to the first value of the size attribute. The frame orientation is obtained with the same procedure as the zaxis attribute described in Frame orientations. The frame position is in the middle between the end points. If this attribute is specified, the remaining position and orientation-related attributes are ignored. The image on the right demonstrates use of fromto with the four supported geoms, using identical Z values. The model is here. Note that the fromto semantics of capsule are unique: the two end points specify the segment around which the radius defines the capsule surface."""

    pos: Optional[Vec3] = None
    """Position of the geom, specified in the frame of the body where the geom is defined."""

    quat: Optional[Vec3] = None
    """Orientation of the geom frame. See Frame orientations."""

    axisangle: Optional[Vec3] = None
    """Orientation of the geom frame. See Frame orientations."""

    xyaxes: Optional[Vec3] = None
    """Orientation of the geom frame. See Frame orientations."""

    zaxis: Optional[Vec3] = None
    """Orientation of the geom frame. See Frame orientations."""

    euler: Optional[Vec3] = None
    """Orientation of the geom frame. See Frame orientations."""

    hfield: Optional[str] = None
    """This attribute must be specified if and only if the geom type is "hfield". It references the height field asset to be instantiated at the position and orientation of the geom frame."""

    mesh: Optional[str] = None
    """If the geom type is "mesh", this attribute is required. It references the mesh asset to be instantiated. This attribute can also be specified if the geom type corresponds to a geometric primitive, namely one of "sphere", "capsule", "cylinder", "ellipsoid", "box". In that case the primitive is automatically fitted to the mesh asset referenced here. The fitting procedure uses either the equivalent inertia box or the axis-aligned bounding box of the mesh, as determined by the attribute fitaabb of compiler. The resulting size of the fitted geom is usually what one would expect, but if not, it can be further adjusted with the fitscale attribute below. In the compiled mjModel the geom is represented as a regular geom of the specified primitive type, and there is no reference to the mesh used for fitting."""

    fitscale: Optional[float] = None
    """This attribute is used only when a primitive geometric type is being fitted to a mesh asset. The scale specified here is relative to the output of the automated fitting procedure. The default value of 1 leaves the result unchanged, a value of 2 makes all sizes of the fitted geom two times larger."""

    fluidshape: Optional[FluidShape] = None
    """"ellipsoid" activates the geom-level fluid interaction model based on an ellipsoidal approximation of the geom shape. When active, the model based on body inertia sizes is disabled for the body in which the geom is defined. See section on ellipsoid-based fluid interaction model for details."""

    fluidcoef: Optional[Vec5] = None
    """Dimensionless coefficients of fluid interaction model, as follows. See section on ellipsoid-based fluid interaction model for details.

    | Index | Description              | Symbol     | Default |
    |:------|:-------------------------|:-----------|:--------|
    | 0     | Blunt drag coefficient   | CD,blunt   | 0.5     |
    | 1     | Slender drag coefficient | CD,slender | 0.25    |
    | 2     | Angular drag coefficient | CD,angular | 1.5     |
    | 3     | Kutta lift coefficient   | CK         | 1.0     |
    | 4     | Magnus lift coefficient  | CM         | 1.0     |"""

    user: Optional[VecN] = None
    """See User parameters."""


class GeomPlane(GeomBase):
    """This element creates a plane geometry."""

    attributes = _geom_attr
    type: Literal[GeomType.PLANE] = GeomType.PLANE
    """Type of geometric shape.

    The `plane` type defines a plane which is infinite for collision detection purposes. It can only be attached to the world body or static children of the world. The plane passes through a point specified via the pos attribute. It is normal to the Z axis of the geom's local frame. The +Z direction corresponds to empty space. Thus the position and orientation defaults of (0,0,0) and (1,0,0,0) would create a ground plane at Z=0 elevation, with +Z being the vertical direction in the world (which is MuJoCo's convention). Since the plane is infinite, it could have been defined using any other point in the plane. The specified position however has additional meaning with regard to rendering. If either of the first two size parameters are positive, the plane is rendered as a rectangle of finite size (in the positive dimensions). This rectangle is centered at the specified position. Three size parameters are required. The first two specify the half- size of the rectangle along the X and Y axes. The third size parameter is unusual: it specifies the spacing between the grid subdivisions of the plane for rendering purposes. The subdivisions are revealed in wireframe rendering mode, but in general they should not be used to paint a grid over the ground plane (textures should be used for that purpose). Instead their role is to improve lighting and shadows, similar to the subdivisions used to render boxes. When planes are viewed from the back, the are automatically made semi-transparent. Planes and the +Z faces of boxes are the only surfaces that can show reflections, if the material applied to the geom has positive reflection. To render an infinite plane, set the first two size parameters to zero.
    """

    size: Optional[Vec3] = None
    """X half-size; Y half-size; spacing between square grid lines for rendering. If either the X or Y half-size is 0, the plane is rendered as infinite in the dimension(s) with 0 size.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


class GeomHField(GeomBase):
    """This element creates a height field geometry."""

    attributes = _geom_attr
    type: Literal[GeomType.HFIELD] = GeomType.HFIELD
    """Type of geometric shape.

    The `hfield` type defines a height field geom. The geom must reference the desired height field asset with the hfield attribute below. The position and orientation of the geom set the position and orientation of the height field. The size of the geom is ignored, and the size parameters of the height field asset are used instead. See the description of the hfield element. Similar to planes, height field geoms can only be attached to the world body or to static children of the world.
    """


class GeomSphere(GeomBase):
    """This element creates a sphere geometry."""

    attributes = _geom_attr + ("size",)
    type: Literal[GeomType.SPHERE] = GeomType.SPHERE
    """Type of geometric shape. The keywords have the following meaning:

    The `sphere` type defines a sphere. This and the next four types correspond to built-in geometric primitives. These primitives are treated as analytic surfaces for collision detection purposes, in many cases relying on custom pair- wise collision routines. Models including only planes, spheres, capsules and boxes are the most efficient in terms of collision detection. Other geom types invoke the general-purpose convex collider. The sphere is centered at the geom's position. Only one size parameter is used, specifying the radius of the sphere. Rendering of geometric primitives is done with automatically generated meshes whose density can be adjusted via quality. The sphere mesh is triangulated along the lines of latitude and longitude, with the Z axis passing through the north and south pole. This can be useful in wireframe mode for visualizing frame orientation."""

    size: Optional[float] = None
    """Radius of the sphere.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


class GeomCapsule(GeomBase):
    """This element creates a capsule geometry."""

    attributes = _geom_attr + ("size",)
    type: Literal[GeomType.CAPSULE] = GeomType.CAPSULE
    """Type of geometric shape.

    The `capsule` type defines a capsule, which is a cylinder capped with two half-spheres. It is oriented along the Z axis of the geom's frame. When the geom frame is specified in the usual way, two size parameters are required: the radius of the capsule followed by the half-height of the cylinder part. However capsules as well as cylinders can also be thought of as connectors, allowing an alternative specification with the fromto attribute below. In that case only one size parameter is required, namely the radius of the capsule.
    """

    size: Optional[Vec2 | float] = None
    """Radius of the capsule; half-length of the cylinder part when not using the fromto specification.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


class GeomEllipsoid(GeomBase):
    """This element creates a ellipsoid geometry."""

    attributes = _geom_attr + ("size",)
    type: Literal[GeomType.ELLIPSOID] = GeomType.ELLIPSOID
    """Type of geometric shape.

    The `ellipsoid` type defines a ellipsoid. This is a sphere scaled separately along the X, Y and Z axes of the local frame. It requires three size parameters, corresponding to the three radii. Note that even though ellipsoids are smooth, their collisions are handled via the general-purpose convex collider. The only exception are plane-ellipsoid collisions which are computed analytically.
    """

    size: Optional[Vec3] = None
    """X radius; Y radius; Z radius.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


class GeomCylinder(GeomBase):
    """This element creates a cylinder geometry."""

    attributes = _geom_attr + ("size",)
    type: Literal[GeomType.CYLINDER] = GeomType.CYLINDER
    """Type of geometric shape.

    The `cylinder` type defines a cylinder. It requires two size parameters: the radius and half-height of the cylinder. The cylinder is oriented along the Z axis of the geom's frame. It can alternatively be specified with the fromto attribute below.
    """

    size: Optional[Vec2 | float] = None
    """Radius of the cylinder; half-length of the cylinder when not using the fromto specification.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


class GeomBox(GeomBase):
    """This element creates a box geometry."""

    attributes = _geom_attr + ("size",)
    type: Literal[GeomType.BOX] = GeomType.BOX
    """Type of geometric shape.

    The `box` type defines a box. Three size parameters are required, corresponding to the half-sizes of the box along the X, Y and Z axes of the geom's frame. Note that box-box collisions can generate up to 8 contact points.
    """

    size: Optional[Vec3] = None
    """X half-size; Y half-size; Z half-size.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


class GeomMesh(GeomBase):
    """This element creates a mesh geometry."""

    attributes = _geom_attr
    type: Literal[GeomType.MESH] = GeomType.MESH
    """Type of geometric shape.

    The `mesh` type defines a mesh. The geom must reference the desired mesh asset with the mesh attribute. Note that mesh assets can also be referenced from other geom types, causing primitive shapes to be fitted; see below. The size is determined by the mesh asset and the geom size parameters are ignored. Unlike all other geoms, the position and orientation of mesh geoms after compilation do not equal the settings of the corresponding attributes here. Instead they are offset by the translation and rotation that were needed to center and align the mesh asset in its own coordinate frame. Recall the discussion of centering and alignment in the mesh element.
    """


class GeomSDF(GeomBase):
    attributes = _geom_attr
    type: Literal[GeomType.SDF] = GeomType.SDF
    """Type of geometric shape.

    The `sdf` type defines a signed distance field (SDF, also referred to as signed distance function). In order to visualize the SDF, a custom mesh must be specified using the mesh/plugin attribute. See the model/plugin/sdf/ directory for example models with SDF geometries. For more details regarding SDF plugins, see the Extensions chapter.
    """


Geom = Annotated[
    GeomPlane
    | GeomHField
    | GeomSphere
    | GeomCapsule
    | GeomEllipsoid
    | GeomCylinder
    | GeomBox
    | GeomMesh
    | GeomSDF,
    Field(discriminator="type"),
]
