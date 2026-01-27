from __future__ import annotations

from typing import Optional, Tuple

from pydantic import field_validator

from mujoco_mojo.base import BuiltIn, XMLModel
from mujoco_mojo.types import Inertia, Vec3, Vec4

__all__ = ["Mesh"]


class BuiltInSphere(BuiltIn):
    """
    Repeated subdivisions of a unit icosahedron (“icosphere”).
    """

    subdivision: int
    """integer in [0-4]: The number of subdivisions to apply to icosahedron faces."""

    @field_validator("subdivision")
    @classmethod
    def validate_subdivision(cls, v: int) -> int:
        if not 0 <= v <= 4:
            raise ValueError("subdivision must be in [0, 4]")
        return v


class BuiltInHemisphere(BuiltIn):
    """
    Quad-projected hemisphere.
    """

    resolution: int
    """integer in [0-10]: Equator discretization of one hemisphere quadrant."""

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, v: int) -> int:
        if not 0 <= v <= 10:
            raise ValueError("resolution must be in [0, 10]")
        return v


class BuiltInCone(BuiltIn):
    """
    Cone mesh from top and bottom polygons.
    """

    nvert: int
    """integer >= 3: The number of vertices in the polygon."""
    radius: float
    """real in [0, 1]: The radius of the top face."""

    @field_validator("nvert")
    @classmethod
    def validate_nvert(cls, v: int) -> int:
        if v < 3:
            raise ValueError("nvert must be >= 3")
        return v

    @field_validator("radius")
    @classmethod
    def validate_radius(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("radius must be in [0, 1]")
        return v


class BuiltInSupersphere(BuiltIn):
    """
    Supersphere (superellipsoid) shape.
    """

    resolution: int
    """integer >= 3: Longitude and latitude discretization."""
    e: float
    """real >= 0: The 'east-west' exponent."""
    n: float
    """real >= 0: The 'north-south' exponent."""

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, v: int) -> int:
        if v < 3:
            raise ValueError("resolution must be >= 3")
        return v

    @field_validator("e", "n")
    @classmethod
    def validate_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("must be >= 0")
        return v


class BuiltInTorus(BuiltIn):
    """
    Supertorus (generalized torus) shape.
    """

    resolution: int
    """integer >= 3: Discretization of both circumferences."""
    radius: float
    """real in (0, 1]: Minor radius of the torus."""
    s: float
    """real > 0: The 'squareness' of minor sections."""
    t: float
    """real > 0: The 'squareness' of major sections."""

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, v: int) -> int:
        if v < 3:
            raise ValueError("resolution must be >= 3")
        return v

    @field_validator("radius")
    @classmethod
    def validate_radius(cls, v: float) -> float:
        if not 0 < v <= 1:
            raise ValueError("radius must be in (0, 1]")
        return v

    @field_validator("s", "t")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("must be > 0")
        return v


class BuiltInWedge(BuiltIn):
    """
    Slice of a unit spherical shell.
    """

    res_phi: int
    """integer >= 0: Vertical resolution of the slice."""
    res_theta: int
    """integer >= 0: Horizontal resolution of the slice."""
    fov_phi: float
    """real in (0, 180]: Horizontal field of view (degrees)."""
    fov_theta: float
    """real in (0, 90): Vertical field of view (degrees)."""
    gamma: float
    """real in [0, 1]: Foveal deformation of the discretization."""

    @field_validator("res_phi", "res_theta")
    @classmethod
    def validate_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("must be >= 0")
        return v

    @field_validator("fov_phi")
    @classmethod
    def validate_fov_phi(cls, v: float) -> float:
        if not 0 < v <= 180:
            raise ValueError("fov_phi must be in (0, 180]")
        return v

    @field_validator("fov_theta")
    @classmethod
    def validate_fov_theta(cls, v: float) -> float:
        if not 0 < v < 90:
            raise ValueError("fov_theta must be in (0, 90)")
        return v

    @field_validator("gamma")
    @classmethod
    def validate_gamma(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("gamma must be in [0, 1]")
        return v


class BuiltInPlate(BuiltIn):
    """
    Rectangular plate mesh.
    """

    res_x: int
    """integer > 0: Horizontal resolution of the plate."""
    res_y: int
    """integer > 0: Vertical resolution of the plate."""

    @field_validator("res_x", "res_y")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("must be > 0")
        return v


class Mesh(XMLModel):
    """This element creates a mesh asset, which can then be referenced from geoms. If the referencing geom type is mesh the mesh is instantiated in the model, otherwise a geometric primitive is automatically fitted to it; see the geom element below."""

    tag = "mesh"

    attributes = (
        "name",
        "class_",
        "content_type",
        "file",
        "vertex",
        "normal",
        "texcoord",
        "face",
        "refpos",
        "refquat",
        "scale",
        "smoothnormal",
        "maxhullvert",
        "inertia",
        "builtin",
        "params",
        "material",
    )
    children = ("plugins",)

    name: Optional[str] = None
    """Name of the mesh, used for referencing. If omitted, the mesh name equals the file name without the path and extension."""
    class_: Optional[str] = None
    """Defaults class for setting unspecified attributes (only scale in this case)."""
    content_type: Optional[str] = None
    """If the file attribute is specified, then this sets the Media Type (formerly known as MIME type) of the file to be loaded. Any filename extensions will be overloaded. Currently model/vnd.mujoco.msh, model/obj, and model/stl are supported."""
    file: Optional[str] = None
    """The file from which the mesh will be loaded. The path is determined as described in the meshdir attribute of compiler. The file extension must be “stl”, “msh”, or “obj” (not case sensitive) specifying the file type. If the file name is omitted, the vertex attribute becomes required."""
    scale: Optional[Vec3] = None
    """This attribute specifies the scaling that will be applied to the vertex data along each coordinate axis. Negative values are allowed, resulting in flipping the mesh along the corresponding axis."""
    inertia: Optional[Inertia] = None
    """This attribute controls how the mesh is used when mass and inertia are inferred from geometry. The current default value legacy will be changed to convex in a future release.

    * convex: Use the mesh’s convex hull to compute volume and inertia, assuming uniform density.
    * exact: Compute volume and inertia exactly, even for non-convex meshes. This algorithm requires a well-oriented, watertight mesh and will error otherwise.
    * legacy: Use the legacy algorithm, leads to volume overcounting for non-convex meshes. Though currently the default to avoid breakages, it is not recommended.
    * shell: Assume mass is concentrated on the surface of the mesh. Use the mesh’s surface to compute the inertia, assuming uniform surface density.
    """
    smoothnormal: Optional[bool] = None
    """Controls the automatic generation of vertex normals when normals are not given explicitly. If true, smooth normals are generated by averaging the face normals at each vertex, with weight proportional to the face area. If false, faces at large angles relative to the average normal are excluded from the average. In this way, sharp edges (as in cube edges) are not smoothed."""
    maxhullvert: Optional[int] = None
    """Maximum number of vertices in a mesh’s convex hull. Currently this is implemented by asking qhull to terminate after maxhullvert vertices. The default value of -1 means “unlimited”. Positive values must be larger than 3."""
    vertex: Optional[Tuple[Tuple[float, float, float], ...]] = None
    """Vertex 3D position data. You can specify position data in the XML using this attribute, or using a binary file, but not both."""
    normal: Optional[Tuple[Tuple[float, float, float], ...]] = None
    """Vertex 3D normal data. If specified, the number of normals must equal the number of vertices. The model compiler normalizes the normals automatically."""
    texcoord: Optional[Tuple[Tuple[float, float], ...]] = None
    """Vertex 2D texture coordinates, which are numbers between 0 and 1. If specified, the number of texture coordinate pairs must equal the number of vertices."""
    face: Optional[Tuple[Tuple[float, float, float], ...]] = None
    """Faces of the mesh. Each face is a sequence of 3 vertex indices, in counter-clockwise order. The indices must be integers between 0 and nvert-1."""
    refpos: Optional[Vec3] = None
    """Reference position relative to which the 3D vertex coordinates are defined. This vector is subtracted from the positions."""
    refquat: Optional[Vec4] = None
    """Reference orientation relative to which the 3D vertex coordinates and normals are defined. The conjugate of this quaternion is used to rotate the positions and normals. The model compiler normalizes the quaternion automatically."""
    builtin_: Optional[BuiltIn] = None
    """The mesh is generated by the compiler from a set of parameters specified in params. When saved to XML, meshes produced this way are converted to explicit vertices. The Python bindings include convenience methods for generating these meshes."""
    builtin: Optional[str] = None  # BUG make this a computed field
    # params: real(nparam), optional # BUG make this a computed field
    """The parameters used to generate a builtin mesh. The number and type of parameters and their semantic depends on the mesh type. See mesh/builtin for details."""
    material: Optional[str] = None
    """Fallback material for mesh geoms that do not specify their own material."""
