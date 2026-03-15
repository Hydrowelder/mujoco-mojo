from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, ClassVar, Literal

import mujoco
import numpy as np
from pydantic import ConfigDict, Field

from mujoco_mojo.mjcf.orientation import Orientation, Quat
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import (
    GeomType,
    MaterialName,
    SiteName,
    Vec2,
    Vec3,
    Vec4,
    Vec6,
    VecN,
)
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from mujoco_mojo.runtime.results_manager import ResultsManager

logger = get_logger(__name__)

__all__ = [
    "Site",
    "SiteBox",
    "SiteCapsule",
    "SiteCylinder",
    "SiteEllipsoid",
    "SiteSphere",
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
    "rgba",
    "user",
)


class SiteBase(XMLModel):
    """
    This element creates a site, which is a simplified and restricted kind of geom. A small subset of the geom attributes are available here; see the geom element for their detailed documentation. Semantically sites represent locations of interest relative to the body frames. Sites do not participate in collisions and computation of body masses and inertias. The geometric shapes that can be used to render sites are limited to a subset of the available geom types. However sites can be used in some places where geoms are not allowed: mounting sensors, specifying via-points of spatial tendons, constructing slider-crank transmissions for actuators.

    This is also used to determine the `SensorObjectType` using the `Sensor.get_sensor_object_type` staticmethod.
    """

    model_config = ConfigDict(extra="forbid")

    tag = "site"

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_SITE

    name: SiteName | None = None
    """Name of the site."""

    class_: str | None = None
    """Defaults class for setting unspecified attributes."""

    group: int = 0
    """Integer group to which the site belongs. This attribute can be used for custom tags. It is also used by the visualizer to enable and disable the rendering of entire groups of sites."""

    material: MaterialName | None = None
    """Material used to specify the visual properties of the site."""

    rgba: Vec4 = np.array((0.5, 0.5, 0.5, 1))
    """Color and transparency. If this value is different from the internal default, it overrides the corresponding material properties."""

    pos: Pos = Pos(pos=np.array((0, 0, 0)))
    """Position of the site frame."""

    orientation: Orientation = Quat()
    """Orientation of the site frame. See Frame orientations."""

    user: VecN | None = None
    """See User parameters."""

    def rt_displacements(
        self,
        other: Site | None,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        relative_to: Site | None = None,
    ) -> np.ndarray:
        """Returns the 3D displacement vector from 'other' to 'self'. If 'relative_to' is provided the vector is rotated into that site's local frame."""
        p1 = self.rt_pos(mj_model, mj_data)
        p2 = other.rt_pos(mj_model, mj_data) if other else np.zeros(3)

        # world displacement
        dr_world = p1 - p2

        if relative_to is None:
            return dr_world

        # rotate into relative_to frame: R^T * dr_world
        rot = mj_data.site_xmat[relative_to.get_id(mj_model)].reshape(3, 3)
        return rot.T @ dr_world

    def rt_dx(
        self,
        other: Site | None,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        relative_to: Site | None = None,
    ) -> float:
        """
        Returns the runtime X displacement between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_displacements(
                other=other,
                mj_model=mj_model,
                mj_data=mj_data,
                relative_to=relative_to,
            )[0]
        )

    def rt_dy(
        self,
        other: Site | None,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        relative_to: Site | None = None,
    ) -> float:
        """
        Returns the runtime Y displacement between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_displacements(
                other=other,
                mj_model=mj_model,
                mj_data=mj_data,
                relative_to=relative_to,
            )[1]
        )

    def rt_dz(
        self,
        other: Site | None,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        relative_to: Site | None = None,
    ) -> float:
        """
        Returns the runtime Z displacement between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_displacements(
                other=other,
                mj_model=mj_model,
                mj_data=mj_data,
                relative_to=relative_to,
            )[2]
        )

    def rt_dm(
        self, other: Site | None, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> float:
        """Returns the runtime euclidian distance between two sites. If `other` is None this will just be the position of self."""
        return float(
            np.linalg.norm(
                self.rt_displacements(other=other, mj_model=mj_model, mj_data=mj_data)
            )
        )

    def rt_parent_body(self, mj_model: mujoco.MjModel) -> int:
        return mj_model.site_bodyid[self.get_id(mj_model)]

    def rt_pos(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> np.ndarray:
        return mj_data.site_xpos[self.get_id(mj_model)]

    def rt_vel(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> np.ndarray:
        assert self._mjt_obj is not None
        res = np.zeros(6)  # 6 element buffer for angular, linear velocity
        mujoco.mj_objectVelocity(
            mj_model, mj_data, self._mjt_obj, self.get_id(mj_model), res, 0
        )
        return res[3:6]

    def rt_ang_vel(
        self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData
    ) -> np.ndarray:
        assert self._mjt_obj is not None
        res = np.zeros(6)  # 6 element buffer for angular, linear velocity
        mujoco.mj_objectVelocity(
            mj_model, mj_data, self._mjt_obj, self.get_id(mj_model), res, 0
        )
        return res[0:3]

    def request(
        self,
        results_manager: ResultsManager,
        attrs: list[Literal["xpos", "xmat", "xvelp", "xvelr"]] = [
            "xpos",
            "xmat",
            "xvelp",
            "xvelr",
        ],
    ):
        """Registers specific site attributes for logging. Requires a named site."""
        if self.name is None:
            msg = f"Cannot request telemetry for an unnamed {self.tag}. Please assign a 'name' to the site before requesting outputs."
            logger.error(msg)
            raise ValueError(msg)

        def harvest(mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
            sid = self.get_id(mj_model)
            for attr in attrs:
                # Handle attributes that MuJoCo doesn't pre-calculate in mjData
                if attr == "xvelp":
                    val = self.rt_vel(mj_model, mj_data)
                elif attr == "xvelr":
                    val = self.rt_ang_vel(mj_model, mj_data)
                else:
                    # Standard pull for xpos, xmat
                    val = getattr(mj_data, f"site_{attr}")[sid]

                # Logging logic
                if val.ndim == 1:
                    for i, k in enumerate("xyz"[: len(val)]):
                        results_manager.post(f"{self.name}_{attr}_{k}", val[i])
                else:
                    results_manager.post(f"{self.name}_{attr}", val.copy())

        results_manager.schedule_harvest_task(harvest)


class SiteSphere(SiteBase):
    """This element creates a sphere site."""

    attributes = (
        *_site_attr,
        "size",
    )
    type: Literal[GeomType.SPHERE] = GeomType.SPHERE
    """Type of geometric shape. The keywords have the following meaning:

    The `sphere` type defines a sphere. This and the next four types correspond to built-in geometric primitives. These primitives are treated as analytic surfaces for collision detection purposes, in many cases relying on custom pair- wise collision routines. Models including only planes, spheres, capsules and boxes are the most efficient in terms of collision detection. Other geom types invoke the general-purpose convex collider. The sphere is centered at the geom's position. Only one size parameter is used, specifying the radius of the sphere. Rendering of geometric primitives is done with automatically generated meshes whose density can be adjusted via quality. The sphere mesh is triangulated along the lines of latitude and longitude, with the Z axis passing through the north and south pole. This can be useful in wireframe mode for visualizing frame orientation."""

    size: float | None = None
    """Radius of the sphere.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


class SiteCapsule(SiteBase):
    """This element creates a capsule site."""

    attributes = (*_site_attr, "size", "fromto")
    type: Literal[GeomType.CAPSULE] = GeomType.CAPSULE
    """Type of geometric shape.

    The `capsule` type defines a capsule, which is a cylinder capped with two half-spheres. It is oriented along the Z axis of the geom's frame. When the geom frame is specified in the usual way, two size parameters are required: the radius of the capsule followed by the half-height of the cylinder part. However capsules as well as cylinders can also be thought of as connectors, allowing an alternative specification with the fromto attribute below. In that case only one size parameter is required, namely the radius of the capsule.
    """

    size: Vec2 | float | None = None
    """Radius of the capsule; half-length of the cylinder part when not using the fromto specification.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """

    fromto: Vec6 | None = None
    """This attribute can only be used with capsule, cylinder, ellipsoid and box sites. It provides an alternative specification of the site length as well as the frame position and orientation. The six numbers are the 3D coordinates of one point followed by the 3D coordinates of another point. The elongated part of the site connects these two points, with the +Z axis of the site's frame oriented from the first towards the second point. The frame orientation is obtained with the same procedure as the zaxis attribute described in Frame orientations. The frame position is in the middle between the two points. If this attribute is specified, the remaining position and orientation-related attributes are ignored."""


class SiteEllipsoid(SiteBase):
    """This element creates a ellipsoid site."""

    attributes = (*_site_attr, "size", "fromto")
    type: Literal[GeomType.ELLIPSOID] = GeomType.ELLIPSOID
    """Type of geometric shape.

    The `ellipsoid` type defines a ellipsoid. This is a sphere scaled separately along the X, Y and Z axes of the local frame. It requires three size parameters, corresponding to the three radii. Note that even though ellipsoids are smooth, their collisions are handled via the general-purpose convex collider. The only exception are plane-ellipsoid collisions which are computed analytically.
    """

    size: Vec3 | None = None
    """X radius; Y radius; Z radius.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """

    fromto: Vec6 | None = None
    """This attribute can only be used with capsule, cylinder, ellipsoid and box sites. It provides an alternative specification of the site length as well as the frame position and orientation. The six numbers are the 3D coordinates of one point followed by the 3D coordinates of another point. The elongated part of the site connects these two points, with the +Z axis of the site's frame oriented from the first towards the second point. The frame orientation is obtained with the same procedure as the zaxis attribute described in Frame orientations. The frame position is in the middle between the two points. If this attribute is specified, the remaining position and orientation-related attributes are ignored."""


class SiteCylinder(SiteBase):
    """This element creates a cylinder site."""

    attributes = (*_site_attr, "size", "fromto")
    type: Literal[GeomType.CYLINDER] = GeomType.CYLINDER
    """Type of geometric shape.

    The `cylinder` type defines a cylinder. It requires two size parameters: the radius and half-height of the cylinder. The cylinder is oriented along the Z axis of the geom's frame. It can alternatively be specified with the fromto attribute below.
    """

    size: Vec2 | float | None = None
    """Radius of the cylinder; half-length of the cylinder when not using the fromto specification.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """

    fromto: Vec6 | None = None
    """This attribute can only be used with capsule, cylinder, ellipsoid and box sites. It provides an alternative specification of the site length as well as the frame position and orientation. The six numbers are the 3D coordinates of one point followed by the 3D coordinates of another point. The elongated part of the site connects these two points, with the +Z axis of the site's frame oriented from the first towards the second point. The frame orientation is obtained with the same procedure as the zaxis attribute described in Frame orientations. The frame position is in the middle between the two points. If this attribute is specified, the remaining position and orientation-related attributes are ignored."""


class SiteBox(SiteBase):
    """This element creates a box site."""

    attributes = (*_site_attr, "size", "fromto")
    type: Literal[GeomType.BOX] = GeomType.BOX
    """Type of geometric shape.

    The `box` type defines a box. Three size parameters are required, corresponding to the half-sizes of the box along the X, Y and Z axes of the geom's frame. Note that box-box collisions can generate up to 8 contact points.
    """

    size: Vec3 | None = None
    """X half-size; Y half-size; Z half-size.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """

    fromto: Vec6 | None = None
    """This attribute can only be used with capsule, cylinder, ellipsoid and box sites. It provides an alternative specification of the site length as well as the frame position and orientation. The six numbers are the 3D coordinates of one point followed by the 3D coordinates of another point. The elongated part of the site connects these two points, with the +Z axis of the site's frame oriented from the first towards the second point. The frame orientation is obtained with the same procedure as the zaxis attribute described in Frame orientations. The frame position is in the middle between the two points. If this attribute is specified, the remaining position and orientation-related attributes are ignored."""


Site = Annotated[
    SiteSphere | SiteCapsule | SiteEllipsoid | SiteCylinder | SiteBox,
    Field(discriminator="type"),
]
