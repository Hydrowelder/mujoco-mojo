from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from pydantic import model_validator

from mujoco_mojo.base import XMLModel
from mujoco_mojo.types import GeomType, Vec3, Vec4

__all__ = ["Geom"]


class Geom(XMLModel):
    """This element creates a geom, and attaches it rigidly to the body within which the geom is defined. Multiple geoms can be attached to the same body. At runtime they determine the appearance and collision properties of the body. At compile time they can also determine the inertial properties of the body, depending on the presence of the inertial element and the setting of the inertiafromgeom attribute of compiler. This is done by summing the masses and inertias of all geoms attached to the body with geom group in the range specified by the inertiagrouprange attribute of compiler. The geom masses and inertias are computed using the geom shape, a specified density or a geom mass which implies a density, and the assumption of uniform density.

    Geoms are not strictly required for physics simulation. One can create and simulate a model that only has bodies and joints. Such a model can even be visualized, using equivalent inertia boxes to represent bodies. Only contact forces would be missing from such a simulation. We do not recommend using such models, but knowing that this is possible helps clarify the role of bodies and geoms in MuJoCo.
    """

    tag = "geom"

    attributes = ("name", "type", "size", "rgba", "pos")

    name: Optional[str] = None
    """Name of the geom."""

    class_: Optional[str] = None
    """Defaults class for setting unspecified attributes."""

    type: GeomType = GeomType.SPHERE
    """Type of geometric shape. The keywords have the following meaning: The plane type defines a plane which is infinite for collision detection purposes. It can only be attached to the world body or static children of the world. The plane passes through a point specified via the pos attribute. It is normal to the Z axis of the geom's local frame. The +Z direction corresponds to empty space. Thus the position and orientation defaults of (0,0,0) and (1,0,0,0) would create a ground plane at Z=0 elevation, with +Z being the vertical direction in the world (which is MuJoCo's convention). Since the plane is infinite, it could have been defined using any other point in the plane. The specified position however has additional meaning with regard to rendering. If either of the first two size parameters are positive, the plane is rendered as a rectangle of finite size (in the positive dimensions). This rectangle is centered at the specified position. Three size parameters are required. The first two specify the half- size of the rectangle along the X and Y axes. The third size parameter is unusual: it specifies the spacing between the grid subdivisions of the plane for rendering purposes. The subdivisions are revealed in wireframe rendering mode, but in general they should not be used to paint a grid over the ground plane (textures should be used for that purpose). Instead their role is to improve lighting and shadows, similar to the subdivisions used to render boxes. When planes are viewed from the back, the are automatically made semi-transparent. Planes and the +Z faces of boxes are the only surfaces that can show reflections, if the material applied to the geom has positive reflection. To render an infinite plane, set the first two size parameters to zero.

    The hfield type defines a height field geom. The geom must reference the desired height field asset with the hfield attribute below. The position and orientation of the geom set the position and orientation of the height field. The size of the geom is ignored, and the size parameters of the height field asset are used instead. See the description of the hfield element. Similar to planes, height field geoms can only be attached to the world body or to static children of the world.

    The sphere type defines a sphere. This and the next four types correspond to built-in geometric primitives. These primitives are treated as analytic surfaces for collision detection purposes, in many cases relying on custom pair- wise collision routines. Models including only planes, spheres, capsules and boxes are the most efficient in terms of collision detection. Other geom types invoke the general-purpose convex collider. The sphere is centered at the geom's position. Only one size parameter is used, specifying the radius of the sphere. Rendering of geometric primitives is done with automatically generated meshes whose density can be adjusted via quality. The sphere mesh is triangulated along the lines of latitude and longitude, with the Z axis passing through the north and south pole. This can be useful in wireframe mode for visualizing frame orientation.

    The capsule type defines a capsule, which is a cylinder capped with two half-spheres. It is oriented along the Z axis of the geom's frame. When the geom frame is specified in the usual way, two size parameters are required: the radius of the capsule followed by the half-height of the cylinder part. However capsules as well as cylinders can also be thought of as connectors, allowing an alternative specification with the fromto attribute below. In that case only one size parameter is required, namely the radius of the capsule.

    The ellipsoid type defines a ellipsoid. This is a sphere scaled separately along the X, Y and Z axes of the local frame. It requires three size parameters, corresponding to the three radii. Note that even though ellipsoids are smooth, their collisions are handled via the general-purpose convex collider. The only exception are plane-ellipsoid collisions which are computed analytically.

    The cylinder type defines a cylinder. It requires two size parameters: the radius and half-height of the cylinder. The cylinder is oriented along the Z axis of the geom's frame. It can alternatively be specified with the fromto attribute below.

    The box type defines a box. Three size parameters are required, corresponding to the half-sizes of the box along the X, Y and Z axes of the geom's frame. Note that box-box collisions can generate up to 8 contact points.

    The mesh type defines a mesh. The geom must reference the desired mesh asset with the mesh attribute. Note that mesh assets can also be referenced from other geom types, causing primitive shapes to be fitted; see below. The size is determined by the mesh asset and the geom size parameters are ignored. Unlike all other geoms, the position and orientation of mesh geoms after compilation do not equal the settings of the corresponding attributes here. Instead they are offset by the translation and rotation that were needed to center and align the mesh asset in its own coordinate frame. Recall the discussion of centering and alignment in the mesh element.

    The sdf type defines a signed distance field (SDF, also referred to as signed distance function). In order to visualize the SDF, a custom mesh must be specified using the mesh/plugin attribute. See the model/plugin/sdf/ directory for example models with SDF geometries. For more details regarding SDF plugins, see the Extensions chapter.
    """

    size: Optional[Tuple[float, ...] | float] = None
    """This is not"""

    rgba: Optional[Vec4] = None
    pos: Optional[Vec3] = None

    @model_validator(mode="after")
    def validate_vectors(self) -> Geom:
        if self.rgba is not None:
            # Safe runtime check
            if not isinstance(self.rgba, np.ndarray):
                self.rgba = np.asarray(self.rgba)
            if self.rgba.shape != (4,):
                raise ValueError("geom.rgba must have shape (4,)")

        if self.pos is not None:
            if not isinstance(self.pos, np.ndarray):
                self.pos = np.asarray(self.pos)
            if self.pos.shape != (3,):
                raise ValueError("geom.pos must have shape (3,)")

        if self.size is not None:
            expected = {
                GeomType.SPHERE: 1,
                GeomType.CAPSULE: 2,
                GeomType.CYLINDER: 2,
                GeomType.BOX: 3,
                GeomType.ELLIPSOID: 3,
                GeomType.PLANE: 3,
                GeomType.MESH: 3,
                GeomType.SDF: 3,
            }[self.type]

            if isinstance(self.size, tuple) and len(self.size) != expected:
                if self.type == GeomType.SPHERE:
                    raise TypeError(
                        f"geom.size for {self.type} must be a float, got a sequence with length {len(self.size)}"
                    )
                raise ValueError(
                    f"geom.size for {self.type} must have length {expected}, got {len(self.size)}"
                )

        return self
