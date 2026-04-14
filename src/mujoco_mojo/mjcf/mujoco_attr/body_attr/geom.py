from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, ClassVar, Literal

import mujoco
import numpy as np
from pydantic import ConfigDict, Field

from mujoco_mojo.mjcf.defaults import SOLIMP_DEFAULT, SOLREF_DEFAULT
from mujoco_mojo.mjcf.orientation import Quat
from mujoco_mojo.mjcf.plugin import Plugin
from mujoco_mojo.mjcf.pose import AnyPose, PoseQuat
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import (
    FluidShape,
    GeomName,
    GeomType,
    HFieldName,
    Mat3,
    MaterialName,
    MeshName,
    RequestCategory,
    Vec2,
    Vec3,
    Vec4,
    Vec5,
    Vec6,
    VecN,
)
from mujoco_mojo.utils.log import get_logger

if TYPE_CHECKING:
    from mujoco_mojo.runtime.results_manager import ResultsManager

logger = get_logger(__name__)

__all__ = [
    "AnyGeom",
    "GeomBox",
    "GeomCapsule",
    "GeomCylinder",
    "GeomEllipsoid",
    "GeomHField",
    "GeomMesh",
    "GeomPlane",
    "GeomSDF",
    "GeomSphere",
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
    "pose",
    "fitscale",
    "rgba",
    "fluidshape",
    "fluidcoef",
    "user",
)


class GeomBase(XMLModel):
    """
    This element creates a geom, and attaches it rigidly to the body within which the geom is defined. Multiple geoms can be attached to the same body. At runtime they determine the appearance and collision properties of the body. At compile time they can also determine the inertial properties of the body, depending on the presence of the inertial element and the setting of the inertiafromgeom attribute of compiler. This is done by summing the masses and inertias of all geoms attached to the body with geom group in the range specified by the inertiagrouprange attribute of compiler. The geom masses and inertias are computed using the geom shape, a specified density or a geom mass which implies a density, and the assumption of uniform density.

    Geoms are not strictly required for physics simulation. One can create and simulate a model that only has bodies and joints. Such a model can even be visualized, using equivalent inertia boxes to represent bodies. Only contact forces would be missing from such a simulation. We do not recommend using such models, but knowing that this is possible helps clarify the role of bodies and geoms in MuJoCo.

    This is also used to determine the `SensorObjectType` using the `Sensor.get_sensor_object_type` staticmethod.
    """

    model_config = ConfigDict(extra="forbid")

    tag = "geom"

    children = ("plugin",)

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_GEOM

    name: GeomName | None = None
    """Name of the geom."""

    class_: str | None = None
    """Defaults class for setting unspecified attributes."""

    contype: int = 1
    """This attribute and the next specify 32-bit integer bitmasks used for contact filtering of dynamically generated contact pairs. See Collision detection in the Computation chapter. Two geoms can collide if the contype of one geom is compatible with the conaffinity of the other geom or vice versa. Compatible means that the two bitmasks have a common bit set to 1."""

    conaffinity: int = 1
    """Bitmask for contact filtering; see contype above."""

    condim: Literal[1, 3, 4, 6] = 3
    """The dimensionality of the contact space for a dynamically generated contact pair is set to the maximum of the condim values of the two participating geoms. See Contact in the Computation chapter. The allowed values and their meaning are:

    | condim | Description                                                                                                                                                                                                                                 |
    |:-------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
    | 1      | Frictionless contact.                                                                                                                                                                                                                       |
    | 3      | Regular frictional contact, opposing slip in the tangent plane.                                                                                                                                                                             |
    | 4      | Frictional contact, opposing slip in the tangent plane and rotation around the contact normal. This is useful for modeling soft contacts (independent of contact penetration).                                                              |
    | 6      | Frictional contact, opposing slip in the tangent plane, rotation around the contact normal and rotation around the two axes of the tangent plane. The latter frictional effects are useful for |preventing objects from indefinite rolling. |"""

    group: int = 0
    """This attribute specifies an integer group to which the geom belongs. The only effect on the physics is at compile time, when body masses and inertias are inferred from geoms selected based on their group; see inertiagrouprange attribute of compiler. At runtime this attribute is used by the visualizer to enable and disable the rendering of entire geom groups. By default, groups 0, 1 and 2 are visible, while all other groups are invisible. The group attribute can also be used as a tag for custom computations."""

    priority: int = 0
    """The geom priority determines how the properties of two colliding geoms are combined to form the properties of the contact. This interacts with the solmix attribute. See Contact parameters."""

    material: MaterialName | None = None
    """If specified, this attribute applies a material to the geom. Otherwise, if unspecified and the type of the geom is a mesh the compiler will apply the mesh asset material if present.

    The material determines the visual properties of the geom. The only exception is color: if the rgba attribute below is different from its internal default, it takes precedence while the remaining material properties are still applied. Note that if the same material is referenced from multiple geoms (as well as sites and tendons) and the user changes some of its properties at runtime, these changes will take effect immediately for all model elements referencing the material. This is because the compiler saves the material and its properties as a separate element in mjModel, and the elements using this material only keep a reference to it."""

    rgba: Vec4 = np.array((0.5, 0.5, 0.5, 1))
    """Instead of creating material assets and referencing them, this attribute can be used to set color and transparency only. This is not as flexible as the material mechanism, but is more convenient and is often sufficient. If the value of this attribute is different from the internal default, it takes precedence over the material."""

    friction: Vec3 = np.array((1, 0.005, 0.0001))
    """Contact friction parameters for dynamically generated contact pairs. The first number is the sliding friction, acting along both axes of the tangent plane. The second number is the torsional friction, acting around the contact normal. The third number is the rolling friction, acting around both axes of the tangent plane. The friction parameters for the contact pair are combined depending on the solmix and priority attributes, as explained in Contact parameters. See the general Contact section for descriptions of the semantics of this attribute."""

    mass: float | None = None
    """If this attribute is specified, the density attribute below is ignored and the geom density is computed from the given mass, using the geom shape and the assumption of uniform density. The computed density is then used to obtain the geom inertia. Recall that the geom mass and inertia are only used during compilation, to infer the body mass and inertia if necessary. At runtime only the body inertial properties affect the simulation; the geom mass and inertia are not saved in mjModel."""

    density: float = 1000
    """Material density used to compute the geom mass and inertia. The computation is based on the geom shape and the assumption of uniform density. The internal default of 1000 is the density of water in SI units. This attribute is used only when the mass attribute above is unspecified. If shellinertia is "false" (the default), density has semantics of mass/volume; if "true", it has semantics of mass/area."""

    shellinertia: bool = False
    """If true, the geom's inertia is computed assuming that all the mass is concentrated on the surface. In this case density is interpreted as surface rather than volumetric density. This attribute only applies to primitive geoms and is ignored for meshes. Surface inertia for meshes can be specified by setting the asset/mesh/inertia attribute to "shell"."""

    solmix: float = 1
    """This attribute specifies the weight used for averaging of contact parameters, and interacts with the priority attribute. See Contact parameters."""

    solref: Vec2 = SOLREF_DEFAULT
    """Constraint solver parameters for contact simulation. See Solver parameters."""

    solimp: Vec5 = SOLIMP_DEFAULT
    """Constraint solver parameters for contact simulation. See Solver parameters."""

    margin: float = 0
    """Distance threshold below which contacts are detected and included in the global array mjData.contact. This however does not mean that contact force will be generated. A contact is considered active only if the distance between the two geom surfaces is below margin-gap. Recall that constraint impedance can be a function of distance, as explained in Solver parameters. The quantity this function is applied to is the distance between the two geoms minus the margin plus the gap."""

    gap: float = 0
    """This attribute is used to enable the generation of inactive contacts, i.e., contacts that are ignored by the constraint solver but are included in mjData.contact for the purpose of custom computations. When this value is positive, geom distances between margin and margin-gap correspond to such inactive contacts."""

    fromto: Vec6 | None = None
    """This attribute can only be used with capsule, box, cylinder and ellipsoid geoms. It provides an alternative specification of the geom length as well as the frame position and orientation. The six numbers are the 3D coordinates of one point followed by the 3D coordinates of another point. The elongated part of the geom connects these two points, with the +Z axis of the geom's frame oriented from the first towards the second point, while in the perpendicular direction, the geom sizes are both equal to the first value of the size attribute. The frame orientation is obtained with the same procedure as the zaxis attribute described in Frame orientations. The frame position is in the middle between the end points. If this attribute is specified, the remaining position and orientation-related attributes are ignored. The image on the right demonstrates use of fromto with the four supported geoms, using identical Z values. The model is here. Note that the fromto semantics of capsule are unique: the two end points specify the segment around which the radius defines the capsule surface."""

    pose: AnyPose = PoseQuat()
    """Position and orientation of the geom, specified in the frame of the body where the geom is defined."""

    fitscale: float = 1
    """This attribute is used only when a primitive geometric type is being fitted to a mesh asset. The scale specified here is relative to the output of the automated fitting procedure. The default value of 1 leaves the result unchanged, a value of 2 makes all sizes of the fitted geom two times larger."""

    fluidshape: FluidShape = FluidShape.NONE
    """"ellipsoid" activates the geom-level fluid interaction model based on an ellipsoidal approximation of the geom shape. When active, the model based on body inertia sizes is disabled for the body in which the geom is defined. See section on ellipsoid-based fluid interaction model for details."""

    fluidcoef: Vec5 = np.array((0.5, 0.25, 1.5, 1.0, 1.0))
    """Dimensionless coefficients of fluid interaction model, as follows. See section on ellipsoid-based fluid interaction model for details.

    | Index | Description              | Symbol     | Default |
    |:------|:-------------------------|:-----------|:--------|
    | 0     | Blunt drag coefficient   | CD,blunt   | 0.5     |
    | 1     | Slender drag coefficient | CD,slender | 0.25    |
    | 2     | Angular drag coefficient | CD,angular | 1.5     |
    | 3     | Kutta lift coefficient   | CK         | 1.0     |
    | 4     | Magnus lift coefficient  | CM         | 1.0     |"""

    user: VecN | None = None
    """See User parameters."""

    plugin: Plugin | None = None
    """Associate this geom with an engine plugin. Either plugin or instance are required."""

    def geom_xpos(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        """Returns the position of the center of the geom."""
        return mj_data.geom_xpos[self.get_id(mj_model)]

    def geom_aabb_radius(self, mj_model: mujoco.MjModel) -> float:
        """Returns the radius of a bounding sphere of the geom."""
        return np.max(mj_model.geom_size[self.get_id(mj_model)])

    @classmethod
    def _get_geom_dist_between_geom(
        cls,
        geom_1: AnyGeom,
        geom_2: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Vec6,
    ) -> float:
        return mujoco.mj_geomDistance(
            m=mj_model,
            d=mj_data,
            geom1=geom_1.get_id(mj_model=mj_model),
            geom2=geom_2.get_id(mj_model=mj_model),
            distmax=dist_max,
            fromto=fromto,
        )

    @classmethod
    def _get_geom_dist_between_geoms_acc(
        cls,
        geom_1: AnyGeom | list[AnyGeom],
        geom_2: AnyGeom | list[AnyGeom],
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Vec6,
    ) -> float:
        """The brute force, but accurate method which checks every pair and returns the minimum distance."""
        list_1 = geom_1 if isinstance(geom_1, list) else [geom_1]
        list_2 = geom_2 if isinstance(geom_2, list) else [geom_2]

        min_dist = dist_max
        temp_fromto = np.zeros(6)
        fromto = temp_fromto

        for g1 in list_1:
            for g2 in list_2:
                d = cls._get_geom_dist_between_geom(
                    geom_1=g1,
                    geom_2=g2,
                    mj_model=mj_model,
                    mj_data=mj_data,
                    dist_max=min_dist,  # use min_dist
                    fromto=temp_fromto,
                )
                if d < min_dist:
                    min_dist = d
                    fromto[:] = temp_fromto

                # early exit if contacting
                if min_dist < 0.0:
                    return min_dist
        return min_dist

    @classmethod
    def _get_geom_dist_between_geoms_auto(
        cls,
        geom_1: AnyGeom | list[AnyGeom],
        geom_2: AnyGeom | list[AnyGeom],
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Vec6,
    ) -> float:
        """
        Broadphase and narrowphase method to calculate geometric distance.

        Uses bounding spheres (like an Axis-Aligned Bounding Box) to set the threshold at which the full accuracy calculation is performed. If the center to center distance between the geoms minus their radii is less than dist_max the explicit calculation is performed.
        """
        list_1 = geom_1 if isinstance(geom_1, list) else [geom_1]
        list_2 = geom_2 if isinstance(geom_2, list) else [geom_2]

        min_dist = dist_max
        temp_fromto = np.zeros(6)
        fromto = temp_fromto

        for g1 in list_1:
            # center of the geom and its max radius
            pos1 = g1.geom_xpos(mj_model=mj_model, mj_data=mj_data)
            rad1 = g1.geom_aabb_radius(mj_model=mj_model)

            for g2 in list_2:
                pos2 = g2.geom_xpos(mj_model=mj_model, mj_data=mj_data)
                rad2 = g2.geom_aabb_radius(mj_model=mj_model)

                d_centers = float(np.linalg.norm(pos1 - pos2))
                d_approx = d_centers - (rad1 + rad2)

                # broad phase elimination
                if d_approx > min_dist:
                    continue

                # candidate pair for min distance
                d_real = cls._get_geom_dist_between_geom(
                    geom_1=g1,
                    geom_2=g2,
                    mj_model=mj_model,
                    mj_data=mj_data,
                    dist_max=min_dist,  # use min_dist
                    fromto=temp_fromto,
                )

                if d_real < min_dist:
                    min_dist = d_real
                    fromto[:] = temp_fromto

                if min_dist < 0.0:
                    return min_dist

        return min_dist

    @classmethod
    def get_geom_dist_between_geoms(
        cls,
        geom_1: AnyGeom | list[AnyGeom],
        geom_2: AnyGeom | list[AnyGeom],
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Vec6 | None = None,
        auto: bool = True,
    ) -> float:
        """
        Calculates the shortest distance between a geometry (or geometries) and geometry (or geometries).

        This method is intended for use with geometry which has been decomposed to get around the limitation that all geometries are convex hulls. This method wraps the low-level `mujoco.mj_geomDistance` function. It computes the signed distance between two geoms based on their current poses in `mj_data`.

        Args:
            geom_1 (Geom | list[Geom]): First Geom/collection of Geom to check.
            geom_2 (Geom): Second Geom/collection of Geom to check against.
            mj_model (mujoco.MjModel): The compiled MuJoCo model instance.
            mj_data (mujoco.MjData): The current simulation state.
            dist_max (float): The maximum search distance. If geoms are further apart than this, the function returns `dist_max`.
            fromto (Vec6 | None, optional): A 6-element NumPy array (float64) used as an output buffer. After execution, it contains the global coordinates of the two closest points: [x1, y1, z1, x2, y2, z2]. These values are mutated **in place**. Defaults to None.
            auto (bool, optional): If True, an Axis-Aligned Bounding Box (AABB) like method is used where bounding spheres approximate clearances if the geoms are distant from one another (dist_max < distance between centers minus the bounding radii). When set to True, will use a brute force method to calculate geometric distance. Defaults to True.

        Returns:
            float: The shortest distance between the two geoms. A negative value indicates penetration (overlap). Returns `dist_max` if no intersection is found within the specified range.

        Note:
            Both geoms must belong to the provided `mj_model`. This calculation is computationally more expensive than bounding box checks as it accounts for the specific shapes (mesh, primitive, etc.).

        """
        if fromto is None:
            fromto = np.zeros(6)
        else:
            fromto = fromto
        if auto:
            return cls._get_geom_dist_between_geoms_auto(
                geom_1=geom_1,
                geom_2=geom_2,
                mj_model=mj_model,
                mj_data=mj_data,
                dist_max=dist_max,
                fromto=fromto,
            )
        else:
            return cls._get_geom_dist_between_geoms_acc(
                geom_1=geom_1,
                geom_2=geom_2,
                mj_model=mj_model,
                mj_data=mj_data,
                dist_max=dist_max,
                fromto=fromto,
            )

    def get_geom_dist(
        self,
        other: AnyGeom,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        dist_max: float,
        fromto: Vec6 | None = None,
        auto: bool = True,
    ) -> float:
        """
        Calculates the shortest distance between this geometry and another.

        This method wraps the low-level `mujoco.mj_geomDistance` function. It computes the signed distance between two geoms based on their current poses in `mj_data`.

        Args:
            other (Geom): The target Geom to check against.
            mj_model (mujoco.MjModel): The compiled MuJoCo model instance.
            mj_data (mujoco.MjData): The current simulation state.
            dist_max (float): The maximum search distance. If geoms are further apart than this, the function returns `dist_max`.
            fromto (Vec6 | None, optional): A 6-element NumPy array (float64) used as an output buffer. After execution, it contains the global coordinates of the two closest points: [x1, y1, z1, x2, y2, z2]. These values are mutated **in place**. Defaults to None.
            auto (bool, optional): If True, an Axis-Aligned Bounding Box (AABB) like method is used where bounding spheres approximate clearances if the geoms are distant from one another (dist_max < distance between centers minus the bounding radii). When set to True, will use a brute force method to calculate geometric distance. Defaults to True.

        Returns:
            float: The shortest distance between the two geoms. A negative value indicates penetration (overlap). Returns `dist_max` if no intersection is found within the specified range.

        Note:
            Both geoms must belong to the provided `mj_model`. This calculation is computationally more expensive than bounding box checks as it accounts for the specific shapes (mesh, primitive, etc.).

        """
        if fromto is None:
            fromto = np.zeros(6)
        else:
            fromto = fromto
        return self.get_geom_dist_between_geoms(
            mj_model=mj_model,
            mj_data=mj_data,
            geom_1=self,  # self is a Geom # pyright: ignore[reportArgumentType]
            geom_2=other,
            dist_max=dist_max,
            fromto=fromto,
            auto=auto,
        )

    def rt_xpos(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        """Returns the world position of the center of the geom."""
        return mj_data.geom_xpos[self.get_id(mj_model)]

    def rt_xmat(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Mat3:
        """Returns the world orientation matrix of the geom."""
        return mj_data.geom_xmat[self.get_id(mj_model)].reshape(3, 3)

    def rt_quat(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Quat:
        return Quat.from_matrix(self.rt_xmat(mj_model, mj_data))

    def rt_xvel(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec6:
        """Returns the 6D velocity vector (ang, lin) in world coordinates."""
        assert self._mjt_obj is not None
        res = np.zeros(6)
        mujoco.mj_objectVelocity(
            mj_model, mj_data, self._mjt_obj, self.get_id(mj_model), res, 0
        )
        return res

    def rt_xvelp(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        """Returns 3D linear velocity in world frame."""
        return self.rt_xvel(mj_model, mj_data)[3:6]

    def rt_xvelr(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        """Returns 3D angular velocity in world frame."""
        return self.rt_xvel(mj_model, mj_data)[0:3]

    def rt_xacc(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec6:
        """Returns the 6D acceleration vector (ang, lin) in world coordinates."""
        assert self._mjt_obj is not None
        res = np.zeros(6)
        mujoco.mj_objectAcceleration(
            mj_model, mj_data, self._mjt_obj, self.get_id(mj_model), res, 0
        )
        return res

    def rt_xaccp(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        """Returns 3D linear acceleration in world frame."""
        return self.rt_xacc(mj_model, mj_data)[3:6]

    def rt_xaccr(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Vec3:
        """Returns 3D angular acceleration in world frame."""
        return self.rt_xacc(mj_model, mj_data)[0:3]

    def request(
        self,
        results_manager: ResultsManager,
        attrs: list[
            Literal["xpos", "xmat", "xvelp", "xvelr", "xaccp", "xaccr", "quat"]
        ] = [
            "xpos",
            "quat",
        ],
    ):
        """Registers specific geom attributes for logging."""
        if self.name is None:
            msg = f"Cannot request telemetry for an unnamed {self.tag}."
            logger.error(msg)
            raise ValueError(msg)

        def harvest(mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
            for attr in attrs:
                # Manual mapping to avoid getattr
                match attr:
                    case "xpos":
                        val = self.rt_xpos(mj_model, mj_data)
                    case "xmat":
                        val = self.rt_xmat(mj_model, mj_data)
                    case "xvelp":
                        val = self.rt_xvelp(mj_model, mj_data)
                    case "xvelr":
                        val = self.rt_xvelr(mj_model, mj_data)
                    case "xaccp":
                        val = self.rt_xaccp(mj_model, mj_data)
                    case "xaccr":
                        val = self.rt_xaccr(mj_model, mj_data)
                    case "quat":
                        val = self.rt_quat(mj_model, mj_data)
                    case _:
                        continue

                # handle quaternion
                if isinstance(val, Quat):
                    for i, k in enumerate("wxyz"[: len(val.quat)]):
                        results_manager.post(
                            value=float(val.quat[i]),
                            category=RequestCategory.GEOMS,
                            subgroup=f"{self.name}/{attr}",
                            attr=k,
                        )
                # Handle 3-vectors (pos, vel, acc)
                elif val.ndim == 1 and len(val) <= 3:
                    for i, k in enumerate("xyz"[: len(val)]):
                        results_manager.post(
                            value=float(val[i]),
                            category=RequestCategory.GEOMS,
                            subgroup=f"{self.name}/{attr}",
                            attr=k,
                        )
                else:
                    # Handle flattened matrices (xmat)
                    val_flat = val.flatten()
                    for i in range(len(val_flat)):
                        results_manager.post(
                            value=float(val_flat[i]),
                            category=RequestCategory.GEOMS,
                            subgroup=f"{self.name}/{attr}",
                            attr=str(i),
                        )

        results_manager.schedule_harvest_task(harvest)


class GeomPlane(GeomBase):
    """This element creates a plane geometry."""

    attributes = (*_geom_attr, "type", "size")
    type: Literal[GeomType.PLANE] = GeomType.PLANE
    """Type of geometric shape.

    The `plane` type defines a plane which is infinite for collision detection purposes. It can only be attached to the world body or static children of the world. The plane passes through a point specified via the pos attribute. It is normal to the Z axis of the geom's local frame. The +Z direction corresponds to empty space. Thus the position and orientation defaults of (0,0,0) and (1,0,0,0) would create a ground plane at Z=0 elevation, with +Z being the vertical direction in the world (which is MuJoCo's convention). Since the plane is infinite, it could have been defined using any other point in the plane. The specified position however has additional meaning with regard to rendering. If either of the first two size parameters are positive, the plane is rendered as a rectangle of finite size (in the positive dimensions). This rectangle is centered at the specified position. Three size parameters are required. The first two specify the half- size of the rectangle along the X and Y axes. The third size parameter is unusual: it specifies the spacing between the grid subdivisions of the plane for rendering purposes. The subdivisions are revealed in wireframe rendering mode, but in general they should not be used to paint a grid over the ground plane (textures should be used for that purpose). Instead their role is to improve lighting and shadows, similar to the subdivisions used to render boxes. When planes are viewed from the back, the are automatically made semi-transparent. Planes and the +Z faces of boxes are the only surfaces that can show reflections, if the material applied to the geom has positive reflection. To render an infinite plane, set the first two size parameters to zero.
    """

    size: Vec3
    """X half-size; Y half-size; spacing between square grid lines for rendering. If either the X or Y half-size is 0, the plane is rendered as infinite in the dimension(s) with 0 size.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """


class GeomHField(GeomBase):
    """This element creates a height field geometry."""

    attributes = (*_geom_attr, "type", "hfield")
    type: Literal[GeomType.HFIELD] = GeomType.HFIELD
    """Type of geometric shape.

    The `hfield` type defines a height field geom. The geom must reference the desired height field asset with the hfield attribute below. The position and orientation of the geom set the position and orientation of the height field. The size of the geom is ignored, and the size parameters of the height field asset are used instead. See the description of the hfield element. Similar to planes, height field geoms can only be attached to the world body or to static children of the world.
    """

    hfield: HFieldName
    """This attribute must be specified if and only if the geom type is "hfield". It references the height field asset to be instantiated at the position and orientation of the geom frame."""


class GeomSphere(GeomBase):
    """This element creates a sphere geometry."""

    attributes = (*_geom_attr, "type", "size", "mesh")
    type: Literal[GeomType.SPHERE] = GeomType.SPHERE
    """Type of geometric shape. The keywords have the following meaning:

    The `sphere` type defines a sphere. This and the next four types correspond to built-in geometric primitives. These primitives are treated as analytic surfaces for collision detection purposes, in many cases relying on custom pair- wise collision routines. Models including only planes, spheres, capsules and boxes are the most efficient in terms of collision detection. Other geom types invoke the general-purpose convex collider. The sphere is centered at the geom's position. Only one size parameter is used, specifying the radius of the sphere. Rendering of geometric primitives is done with automatically generated meshes whose density can be adjusted via quality. The sphere mesh is triangulated along the lines of latitude and longitude, with the Z axis passing through the north and south pole. This can be useful in wireframe mode for visualizing frame orientation."""

    size: float
    """Radius of the sphere.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """

    mesh: MeshName | None = None
    """If the geom type is "mesh", this attribute is required. It references the mesh asset to be instantiated. This attribute can also be specified if the geom type corresponds to a geometric primitive, namely one of "sphere", "capsule", "cylinder", "ellipsoid", "box". In that case the primitive is automatically fitted to the mesh asset referenced here. The fitting procedure uses either the equivalent inertia box or the axis-aligned bounding box of the mesh, as determined by the attribute fitaabb of compiler. The resulting size of the fitted geom is usually what one would expect, but if not, it can be further adjusted with the fitscale attribute below. In the compiled mjModel the geom is represented as a regular geom of the specified primitive type, and there is no reference to the mesh used for fitting."""


class GeomCapsule(GeomBase):
    """This element creates a capsule geometry."""

    attributes = (*_geom_attr, "type", "size", "mesh")
    type: Literal[GeomType.CAPSULE] = GeomType.CAPSULE
    """Type of geometric shape.

    The `capsule` type defines a capsule, which is a cylinder capped with two half-spheres. It is oriented along the Z axis of the geom's frame. When the geom frame is specified in the usual way, two size parameters are required: the radius of the capsule followed by the half-height of the cylinder part. However capsules as well as cylinders can also be thought of as connectors, allowing an alternative specification with the fromto attribute below. In that case only one size parameter is required, namely the radius of the capsule.
    """

    size: Vec2 | float
    """Radius of the capsule; half-length of the cylinder part when not using the fromto specification.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """

    mesh: MeshName | None = None
    """If the geom type is "mesh", this attribute is required. It references the mesh asset to be instantiated. This attribute can also be specified if the geom type corresponds to a geometric primitive, namely one of "sphere", "capsule", "cylinder", "ellipsoid", "box". In that case the primitive is automatically fitted to the mesh asset referenced here. The fitting procedure uses either the equivalent inertia box or the axis-aligned bounding box of the mesh, as determined by the attribute fitaabb of compiler. The resulting size of the fitted geom is usually what one would expect, but if not, it can be further adjusted with the fitscale attribute below. In the compiled mjModel the geom is represented as a regular geom of the specified primitive type, and there is no reference to the mesh used for fitting."""


class GeomEllipsoid(GeomBase):
    """This element creates a ellipsoid geometry."""

    attributes = (*_geom_attr, "type", "size", "mesh")
    type: Literal[GeomType.ELLIPSOID] = GeomType.ELLIPSOID
    """Type of geometric shape.

    The `ellipsoid` type defines a ellipsoid. This is a sphere scaled separately along the X, Y and Z axes of the local frame. It requires three size parameters, corresponding to the three radii. Note that even though ellipsoids are smooth, their collisions are handled via the general-purpose convex collider. The only exception are plane-ellipsoid collisions which are computed analytically.
    """

    size: Vec3
    """X radius; Y radius; Z radius.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """

    mesh: MeshName | None = None
    """If the geom type is "mesh", this attribute is required. It references the mesh asset to be instantiated. This attribute can also be specified if the geom type corresponds to a geometric primitive, namely one of "sphere", "capsule", "cylinder", "ellipsoid", "box". In that case the primitive is automatically fitted to the mesh asset referenced here. The fitting procedure uses either the equivalent inertia box or the axis-aligned bounding box of the mesh, as determined by the attribute fitaabb of compiler. The resulting size of the fitted geom is usually what one would expect, but if not, it can be further adjusted with the fitscale attribute below. In the compiled mjModel the geom is represented as a regular geom of the specified primitive type, and there is no reference to the mesh used for fitting."""


class GeomCylinder(GeomBase):
    """This element creates a cylinder geometry."""

    attributes = (*_geom_attr, "type", "size", "mesh")
    type: Literal[GeomType.CYLINDER] = GeomType.CYLINDER
    """Type of geometric shape.

    The `cylinder` type defines a cylinder. It requires two size parameters: the radius and half-height of the cylinder. The cylinder is oriented along the Z axis of the geom's frame. It can alternatively be specified with the fromto attribute below.
    """

    size: Vec2 | float
    """Radius of the cylinder; half-length of the cylinder when not using the fromto specification.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """

    mesh: MeshName | None = None
    """If the geom type is "mesh", this attribute is required. It references the mesh asset to be instantiated. This attribute can also be specified if the geom type corresponds to a geometric primitive, namely one of "sphere", "capsule", "cylinder", "ellipsoid", "box". In that case the primitive is automatically fitted to the mesh asset referenced here. The fitting procedure uses either the equivalent inertia box or the axis-aligned bounding box of the mesh, as determined by the attribute fitaabb of compiler. The resulting size of the fitted geom is usually what one would expect, but if not, it can be further adjusted with the fitscale attribute below. In the compiled mjModel the geom is represented as a regular geom of the specified primitive type, and there is no reference to the mesh used for fitting."""


class GeomBox(GeomBase):
    """This element creates a box geometry."""

    attributes = (*_geom_attr, "type", "size", "mesh")
    type: Literal[GeomType.BOX] = GeomType.BOX
    """Type of geometric shape.

    The `box` type defines a box. Three size parameters are required, corresponding to the half-sizes of the box along the X, Y and Z axes of the geom's frame. Note that box-box collisions can generate up to 8 contact points.
    """

    size: Vec3
    """X half-size; Y half-size; Z half-size.

    Geom size parameters. The number of required parameters and their meaning depends on the geom type as documented under the type attribute. Here we only provide a summary. All required size parameters must be positive; the internal defaults correspond to invalid settings. Note that when a non-mesh geom type references a mesh, a geometric primitive of that type is fitted to the mesh. In that case the sizes are obtained from the mesh, and the geom size parameters are ignored. Thus the number and description of required size parameters in the table below only apply to geoms that do not reference meshes.
    """

    mesh: MeshName | None = None
    """If the geom type is "mesh", this attribute is required. It references the mesh asset to be instantiated. This attribute can also be specified if the geom type corresponds to a geometric primitive, namely one of "sphere", "capsule", "cylinder", "ellipsoid", "box". In that case the primitive is automatically fitted to the mesh asset referenced here. The fitting procedure uses either the equivalent inertia box or the axis-aligned bounding box of the mesh, as determined by the attribute fitaabb of compiler. The resulting size of the fitted geom is usually what one would expect, but if not, it can be further adjusted with the fitscale attribute below. In the compiled mjModel the geom is represented as a regular geom of the specified primitive type, and there is no reference to the mesh used for fitting."""


class GeomMesh(GeomBase):
    """This element creates a mesh geometry."""

    attributes = (*_geom_attr, "type", "mesh")
    type: Literal[GeomType.MESH] = GeomType.MESH
    """Type of geometric shape.

    The `mesh` type defines a mesh. The geom must reference the desired mesh asset with the mesh attribute. Note that mesh assets can also be referenced from other geom types, causing primitive shapes to be fitted; see below. The size is determined by the mesh asset and the geom size parameters are ignored. Unlike all other geoms, the position and orientation of mesh geoms after compilation do not equal the settings of the corresponding attributes here. Instead they are offset by the translation and rotation that were needed to center and align the mesh asset in its own coordinate frame. Recall the discussion of centering and alignment in the mesh element.
    """

    mesh: MeshName
    """If the geom type is "mesh", this attribute is required. It references the mesh asset to be instantiated. This attribute can also be specified if the geom type corresponds to a geometric primitive, namely one of "sphere", "capsule", "cylinder", "ellipsoid", "box". In that case the primitive is automatically fitted to the mesh asset referenced here. The fitting procedure uses either the equivalent inertia box or the axis-aligned bounding box of the mesh, as determined by the attribute fitaabb of compiler. The resulting size of the fitted geom is usually what one would expect, but if not, it can be further adjusted with the fitscale attribute below. In the compiled mjModel the geom is represented as a regular geom of the specified primitive type, and there is no reference to the mesh used for fitting."""


class GeomSDF(GeomBase):
    attributes = (*_geom_attr, "type")
    type: Literal[GeomType.SDF] = GeomType.SDF
    """Type of geometric shape.

    The `sdf` type defines a signed distance field (SDF, also referred to as signed distance function). In order to visualize the SDF, a custom mesh must be specified using the mesh/plugin attribute. See the model/plugin/sdf/ directory for example models with SDF geometries. For more details regarding SDF plugins, see the Extensions chapter.
    """


AnyGeom = Annotated[
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
