from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal

import mujoco
import numpy as np
from pydantic import ConfigDict, Field

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.pose import AnyPose, PoseQuat
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import (
    GeomType,
    Mat3,
    MaterialName,
    SignalCategory,
    SiteName,
    Vec2,
    Vec3,
    Vec4,
    Vec6,
    VecN,
)
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from mujoco_mojo.runtime.signal_manager import SignalManager

logger = get_logger(__name__)

__all__ = [
    "AnySite",
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
    "pose",
    "material",
    "size",
    "rgba",
    "user",
)


class SiteBase(XMLModel, ABC):
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

    pose: AnyPose = PoseQuat()
    """Position and orientation of the site frame."""

    user: VecN | None = None
    """See User parameters."""

    def rt_xmat(self, state: MjState, flatten: bool = False) -> Mat3:
        """Rotation matrix the site during runtime."""
        return (
            state.data.site_xmat[self.get_id(state.model)]
            if flatten
            else state.data.site_xmat[self.get_id(state.model)].reshape(3, 3)
        )

    def rt_quat(self, state: MjState) -> Vec4:
        """
        Returns the (w, x, y, z) quaternion from the site's rotation matrix.
        Uses MuJoCo's internal C utility for speed.
        """
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, self.rt_xmat(state, flatten=True))
        return quat

    def rt_parent_body(self, state: MjState) -> int:
        return state.model.site_bodyid[self.get_id(state.model)]

    def rt_pos(self, state: MjState) -> Vec3:
        return state.data.site_xpos[self.get_id(state.model)]

    def rt_displacements(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> Vec3:
        """Returns the 3D displacement vector from 'other' to 'self'. If 'relative_to' is provided the vector is rotated into that site's local frame."""
        p1 = self.rt_pos(state)
        p2 = other.rt_pos(state) if other else np.zeros(3)

        # world displacement
        dr_world = p1 - p2

        if relative_to is None:
            return dr_world

        # rotate into relative_to frame: R^T * dr_world
        rot_t = relative_to.rt_xmat(state).T
        return rot_t @ dr_world

    def rt_dx(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime X displacement between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_displacements(
                other=other,
                state=state,
                relative_to=relative_to,
            )[0]
        )

    def rt_dy(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime Y displacement between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_displacements(
                other=other,
                state=state,
                relative_to=relative_to,
            )[1]
        )

    def rt_dz(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime Z displacement between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_displacements(
                other=other,
                state=state,
                relative_to=relative_to,
            )[2]
        )

    def rt_dm(self, other: AnySite | None, state: MjState) -> float:
        """Returns the runtime distance magnitude between two sites. If `other` is None this will just be the position of self."""
        return float(np.linalg.norm(self.rt_displacements(other=other, state=state)))

    def rt_vel(self, state: MjState) -> Vec6:
        """Returns the 6D velocity vector (ang, lin) in world coordinates."""
        assert self._mjt_obj is not None
        res = np.zeros(6)  # 6 element buffer for angular, linear
        mujoco.mj_objectVelocity(
            state.model, state.data, self._mjt_obj, self.get_id(state.model), res, 0
        )
        return res

    def rt_lin_vel(self, state: MjState) -> Vec3:
        """Returns the 3D linear velocity vector in the world frame."""
        return self.rt_vel(state)[3:6]

    def rt_ang_vel(self, state: MjState) -> Vec3:
        """Returns the 3D angular velocity vector in the world frame."""
        return self.rt_vel(state)[0:3]

    def rt_velocities(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> Vec6:
        """Returns the 6D velocity vector (ang, lin) from 'other' to 'self'. If 'relative_to' is provided the vector is rotated into that site's local frame."""
        # in world frame
        world_self = self.rt_vel(state)

        if other:
            world_other = other.rt_vel(state)
        else:
            world_other = np.zeros(6)

        assert isinstance(world_self, np.ndarray)
        assert isinstance(world_other, np.ndarray)
        world_rel = world_self - world_other

        if relative_to is None:
            return world_rel

        # rotate into relative_to coordinate frame
        rot_t = rot_t = relative_to.rt_xmat(state).T
        rel_local = np.zeros(6)
        rel_local[0:3] = rot_t @ world_rel[0:3]  # angular
        rel_local[3:6] = rot_t @ world_rel[3:6]  # linear
        return rel_local

    def rt_lin_vx(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime X linear velocity between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_velocities(
                other=other,
                state=state,
                relative_to=relative_to,
            )[3]
        )

    def rt_lin_vy(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime Y linear velocity between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_velocities(
                other=other,
                state=state,
                relative_to=relative_to,
            )[4]
        )

    def rt_lin_vz(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime Z linear velocity between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_velocities(
                other=other,
                state=state,
                relative_to=relative_to,
            )[5]
        )

    def rt_lin_vm(self, other: AnySite | None, state: MjState) -> float:
        """Returns the runtime linear velocity magnitude between two sites. If `other` is None this will just be the position of self."""
        return float(np.linalg.norm(self.rt_velocities(other=other, state=state)[3:6]))

    def rt_ang_vx(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime X angular velocity between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_velocities(
                other=other,
                state=state,
                relative_to=relative_to,
            )[0]
        )

    def rt_ang_vy(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime Y angular velocity between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_velocities(
                other=other,
                state=state,
                relative_to=relative_to,
            )[1]
        )

    def rt_ang_vz(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime Z angular velocity between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_velocities(
                other=other,
                state=state,
                relative_to=relative_to,
            )[2]
        )

    def rt_ang_vm(self, other: AnySite | None, state: MjState) -> float:
        """Returns the runtime angular velocity magnitude between two sites. If `other` is None this will just be the position of self."""
        return float(np.linalg.norm(self.rt_velocities(other=other, state=state)[0:3]))

    def rt_acc(self, state: MjState) -> Vec6:
        """Returns the 6D acceleration vector (ang, lin) in world coordinates."""
        assert self._mjt_obj is not None
        res = np.zeros(6)  # 6 element buffer for angular, linear
        mujoco.mj_objectAcceleration(
            state.model, state.data, self._mjt_obj, self.get_id(state.model), res, 0
        )
        return res

    def rt_lin_acc(self, state: MjState) -> Vec3:
        """Returns the 3D linear acceleration vector in the world frame."""
        return self.rt_acc(state)[3:6]

    def rt_ang_acc(self, state: MjState) -> Vec3:
        """Returns the 3D angular acceleration vector in the world frame."""
        return self.rt_acc(state)[0:3]

    def rt_accelerations(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> Vec6:
        """Returns the 6D acceleration vector (ang, lin) from 'other' to 'self'. If 'relative_to' is provided the vector is rotated into that site's local frame."""
        # in world frame
        world_self = self.rt_acc(state)

        if other:
            world_other = other.rt_acc(state)
        else:
            world_other = np.zeros(6)

        world_rel = world_self - world_other

        if relative_to is None:
            return world_rel

        # rotate into relative_to coordinate frame
        rot_t = relative_to.rt_xmat(state).T
        rel_local = np.zeros(6)
        rel_local[0:3] = rot_t @ world_rel[0:3]  # angular
        rel_local[3:6] = rot_t @ world_rel[3:6]  # linear
        return rel_local

    def rt_lin_ax(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime X linear acceleration between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_accelerations(
                other=other,
                state=state,
                relative_to=relative_to,
            )[3]
        )

    def rt_lin_ay(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime Y linear acceleration between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_accelerations(
                other=other,
                state=state,
                relative_to=relative_to,
            )[4]
        )

    def rt_lin_az(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime Z linear acceleration between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_accelerations(
                other=other,
                state=state,
                relative_to=relative_to,
            )[5]
        )

    def rt_lin_am(self, other: AnySite | None, state: MjState) -> float:
        """Returns the runtime linear acceleration magnitude between two sites. If `other` is None this will just be the position of self."""
        return float(
            np.linalg.norm(self.rt_accelerations(other=other, state=state)[3:6])
        )

    def rt_ang_ax(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime X angular acceleration between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_accelerations(
                other=other,
                state=state,
                relative_to=relative_to,
            )[0]
        )

    def rt_ang_ay(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime Y angular acceleration between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_accelerations(
                other=other,
                state=state,
                relative_to=relative_to,
            )[1]
        )

    def rt_ang_az(
        self,
        other: AnySite | None,
        state: MjState,
        relative_to: AnySite | None = None,
    ) -> float:
        """
        Returns the runtime Z angular acceleration between this site and 'other'.

        If 'relative_to' is provided the coordinate system for that site will be used.
        """
        return float(
            self.rt_accelerations(
                other=other,
                state=state,
                relative_to=relative_to,
            )[2]
        )

    def rt_ang_am(self, other: AnySite | None, state: MjState) -> float:
        """Returns the runtime angular acceleration magnitude between two sites. If `other` is None this will just be the position of self."""
        return float(
            np.linalg.norm(self.rt_accelerations(other=other, state=state)[0:3])
        )

    def request(
        self,
        signal_manager: SignalManager | None = None,
        channels: list[Literal["xpos", "xmat", "xvelp", "xvelr", "quat"]] = [
            "xpos",
            "quat",
            "xvelp",
            "xvelr",
        ],
    ):
        """
        Registers specific channels for logging. Requires a named site.

        | Channel | Description                            | Type |
        |:--------|:---------------------------------------|:-----|
        | `xpos`  | world position of the site             | xyzm |
        | `xmat`  | world rotation matrix                  | mat9 |
        | `xvelp` | linear velocity in world frame         | xyzm |
        | `xvelr` | angular velocity in world frame        | xyzm |
        | `quat`  | world orientation quaternion           | quat |

        Each channel is posted under `subgroups=(site_name, channel)`.

        * An `xyzm` is a cartesian vector, posted as 4 values (`x`, `y`, `z`, and its magnitude `m`).
        * A `mat9` is a flattened 3x3 matrix, posted as 9 values with `attr` set to `0`-`8`.
        * A `quat` is an orientation quaternion, posted as 4 values (`w`, `x`, `y`, `z`).

        If `signal_manager` is omitted, the `SignalManager` of the active `RuntimeManager` `with` block is used.
        """
        from mujoco_mojo.runtime.signal_manager import resolve_signal_manager

        signal_manager = resolve_signal_manager(signal_manager)

        if self.name is None:
            msg = f"Cannot request telemetry for an unnamed {self.tag}. Please assign a 'name' to the site before requesting outputs."
            logger.error(msg)
            raise ValueError(msg)

        def sample(state: MjState):
            for channel in channels:
                # Handle attributes that MuJoCo doesn't pre-calculate in mjData
                match channel:
                    case "xpos":
                        val = self.rt_pos(state)
                    case "xmat":
                        val = self.rt_xmat(state)
                    case "xvelp":
                        val = self.rt_lin_vel(state)
                    case "xvelr":
                        val = self.rt_ang_vel(state)
                    case "quat":
                        val = self.rt_quat(state)

                        for i, attr in enumerate("wxyz"):
                            signal_manager.post(
                                value=float(val[i]),
                                category=SignalCategory.SITES,
                                subgroups=(f"{self.name}", channel),
                                attr=attr,
                            )
                        continue
                    case _:
                        continue

                if val.ndim == 1 and len(val) <= 3:
                    # vector output (x, y, z + magnitude)
                    mag = np.linalg.norm(val)
                    full_vec = np.append(val, mag)

                    for i, attr in enumerate("xyzm"):
                        signal_manager.post(
                            value=float(full_vec[i]),
                            category=SignalCategory.SITES,
                            subgroups=(f"{self.name}", channel),
                            attr=attr,
                        )
                else:
                    # longer arrays (or matrices like xmat), use flattened indices
                    val_flat = val.flatten()
                    for i in range(len(val_flat)):
                        signal_manager.post(
                            value=float(val_flat[i]),
                            category=SignalCategory.SITES,
                            subgroups=(f"{self.name}", channel),
                            attr=str(i),
                        )

        signal_manager.register_sampler(sample)


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


AnySite = Annotated[
    SiteSphere | SiteCapsule | SiteEllipsoid | SiteCylinder | SiteBox,
    Field(discriminator="type"),
]
