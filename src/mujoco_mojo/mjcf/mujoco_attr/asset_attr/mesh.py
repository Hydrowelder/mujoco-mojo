from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Optional, Tuple

import numpy as np
from pydantic import field_validator

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.orientation import Quat
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.typing import Inertia, MaterialName, MeshName, Vec3

__all__ = [
    "Mesh",
    "MeshSphere",
    "MeshHemisphere",
    "MeshCone",
    "MeshSupersphere",
    "MeshTorus",
    "MeshWedge",
    "MeshPlate",
]

_mesh_attr = (
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
    "material",
)


class Mesh(XMLModel):
    """This element creates a mesh asset, which can then be referenced from geoms. If the referencing geom type is mesh the mesh is instantiated in the model, otherwise a geometric primitive is automatically fitted to it; see the geom element below.

    MuJoCo works with triangulated meshes. They can be loaded from binary STL files, OBJ files or MSH files with custom format described below, or vertex and face data specified directly in the XML. Software such as MeshLab can be used to convert from other mesh formats to STL or OBJ. While any collection of triangles can be loaded as a mesh and rendered, collision detection works with the convex hull of the mesh as explained in Collision detection. The mesh appearance (including texture mapping) is controlled by the material and rgba attributes of the referencing geom, similarly to height fields.

    Meshes can have explicit texture coordinates instead of relying on the automated texture mapping mechanism. When provided, these explicit coordinates have priority. Note that texture coordinates can be specified with OBJ files and MSH files, as well as explicitly in the XML with the texcoord attribute, but not via STL files. These mechanism cannot be mixed. So if you have an STL mesh, the only way to add texture coordinates to it is to convert to one of the other supported formats.

    Poorly designed meshes can display rendering artifacts. In particular, the shadow mapping mechanism relies on having some distance between front and back-facing triangle faces. If the faces are repeated, with opposite normals as determined by the vertex order in each triangle, this causes shadow aliasing. The solution is to remove the repeated faces (which can be done in MeshLab) or use a better designed mesh. Flipped faces are checked by MuJoCo for meshes specified as OBJ or XML and an error message is returned.

    The size of the mesh is determined by the 3D coordinates of the vertex data in the mesh file, multiplied by the components of the scale attribute below. Scaling is applied separately for each coordinate axis. Note that negative scaling values can be used to flip the mesh; this is a legitimate operation. The size parameters of the referencing geoms are ignored, similarly to height fields. We also provide a mechanism to translate and rotate the 3D coordinates, using the attributes refpos and refquat.

    A mesh can also be defined without faces (a point cloud essentially). In that case the convex hull is constructed automatically.This makes it easy to construct simple shapes directly in the XML. For example, a pyramid can be created as follows:

    ```xml
    <asset>
        <mesh name="tetrahedron" vertex="0 0 0  1 0 0  0 1 0  0 0 1"/>
    </asset>
    ```

    Positioning and orienting is complicated by the fact that vertex data in the source asset are often relative to coordinate frames whose origin is not inside the mesh. In contrast, MuJoCo expects the origin of a geom's local frame to coincide with the geometric center of the shape. We resolve this discrepancy by pre-processing the mesh in the compiler, so that it is centered around (0,0,0) and its principal axes of inertia are the coordinate axes. We save the translation and rotation offsets applied to the source asset in mjModel.mesh_pos and mjModel.mesh_quat; these are required if one reads vertex data from the source and needs to re-apply the transform. These offsets are then composed with the referencing geom's position and orientation; see also the mesh attribute of geom below. Fortunately most meshes used in robot models are designed in a coordinate frame centered at the joint. This makes the corresponding MJCF model intuitive: we set the body frame at the joint, so that the joint position is (0,0,0) in the body frame, and simply reference the mesh. Below is an MJCF model fragment of a forearm, containing all the information needed to put the mesh where one would expect it to be. The body position is specified relative to the parent body, namely the upper arm (not shown). It is offset by 35 cm which is the typical length of the human upper arm. If the mesh vertex data were not designed in the above convention, we would have to use the geom position and orientation (or the refpos, refquat mechanism) to compensate, but in practice this is rarely needed.

    ```xml
    <asset>
        <mesh file="forearm.stl"/>
    </asset>

    <body pos="0 0 0.35"/>
        <joint type="hinge" axis="1 0 0"/>
        <geom type="mesh" mesh="forearm"/>
    </body>
    ```

    The inertial computation mentioned above is part of an algorithm used not only to center and align the mesh, but also to infer the mass and inertia of the body to which it is attached. This is done by computing the centroid of the triangle faces, connecting each face with the centroid to form a triangular pyramid, computing the mass and signed inertia of all pyramids (considered solid, or hollow if shellinertia is true) and accumulating them. The sign ensures that pyramids on the outside of the surfaces are subtracted, as can occur with concave geometries. This algorithm can be found in section 1.3.8 of Computational Geometry in C (Second Edition) by Joseph O'Rourke.

    The full list of processing steps applied by the compiler to each mesh is as follows:

    1. For STL meshes, remove any repeated vertices and re-index the faces if needed. If the mesh is not STL, we assume that the desired vertices and faces have already been generated and do not apply removal or re-indexing;
    2. If vertex normals are not provided, generate normals automatically, using a weighted average of the surrounding face normals. If sharp edges are encountered, the renderer uses the face normals to preserve the visual information about the edge, unless smoothnormal is true. Note that normals cannot be provided with STL meshes;
    3. Scale, translate and rotate the vertices and normals, re-normalize the normals in case of scaling. Save these transformations in mjModel.mesh_{pos, quat, scale}.
    4. Construct the convex hull if specified;
    5. Find the centroid of all triangle faces, and construct the union-of-pyramids representation. Triangles whose area is too small (below the mjMINVAL value of 1E-14) result in compile error;
    6. Compute the center of mass and inertia matrix of the union-of-pyramids. Use eigenvalue decomposition to find the principal axes of inertia. Center and align the mesh, saving the translational and rotational offsets for subsequent geom-related computations.
    """

    tag = "mesh"

    attributes = _mesh_attr

    name: Optional[MeshName] = None
    """Name of the mesh, used for referencing. If omitted, the mesh name equals the file name without the path and extension."""

    class_: Optional[str] = None
    """Defaults class for setting unspecified attributes (only scale in this case)."""

    content_type: Optional[str] = None
    """If the file attribute is specified, then this sets the Media Type (formerly known as MIME type) of the file to be loaded. Any filename extensions will be overloaded. Currently model/vnd.mujoco.msh, model/obj, and model/stl are supported."""

    file: Optional[Path] = None
    """The file from which the mesh will be loaded. The path is determined as described in the meshdir attribute of compiler. The file extension must be "stl", "msh", or "obj" (not case sensitive) specifying the file type. If the file name is omitted, the vertex attribute becomes required."""

    scale: Vec3 = np.array((1, 1, 1))
    """This attribute specifies the scaling that will be applied to the vertex data along each coordinate axis. Negative values are allowed, resulting in flipping the mesh along the corresponding axis."""

    inertia: Inertia = Inertia.CONVEX  # Gable Jan 2026 - I have elected to get out ahead of the upcoming change to convex.
    """This attribute controls how the mesh is used when mass and inertia are inferred from geometry.

    * convex: Use the mesh's convex hull to compute volume and inertia, assuming uniform density.
    * exact: Compute volume and inertia exactly, even for non-convex meshes. This algorithm requires a well-oriented, watertight mesh and will error otherwise.
    * legacy: Use the legacy algorithm, leads to volume overcounting for non-convex meshes. Though currently the default to avoid breakages, it is not recommended.
    * shell: Assume mass is concentrated on the surface of the mesh. Use the mesh's surface to compute the inertia, assuming uniform surface density.
    """

    smoothnormal: bool = False
    """Controls the automatic generation of vertex normals when normals are not given explicitly. If true, smooth normals are generated by averaging the face normals at each vertex, with weight proportional to the face area. If false, faces at large angles relative to the average normal are excluded from the average. In this way, sharp edges (as in cube edges) are not smoothed."""

    maxhullvert: int = -1
    """Maximum number of vertices in a mesh's convex hull. Currently this is implemented by asking qhull to terminate after maxhullvert vertices. The default value of -1 means "unlimited". Positive values must be larger than 3."""

    vertex: Optional[Tuple[Tuple[float, float, float], ...]] = None
    """Vertex 3D position data. You can specify position data in the XML using this attribute, or using a binary file, but not both."""

    normal: Optional[Tuple[Tuple[float, float, float], ...]] = None
    """Vertex 3D normal data. If specified, the number of normals must equal the number of vertices. The model compiler normalizes the normals automatically."""

    texcoord: Optional[Tuple[Tuple[float, float], ...]] = None
    """Vertex 2D texture coordinates, which are numbers between 0 and 1. If specified, the number of texture coordinate pairs must equal the number of vertices."""

    face: Optional[Tuple[Tuple[float, float, float], ...]] = None
    """Faces of the mesh. Each face is a sequence of 3 vertex indices, in counter-clockwise order. The indices must be integers between 0 and nvert-1."""

    refpos: Pos = Pos(pos=np.array((1, 1, 1)))
    """Reference position relative to which the 3D vertex coordinates are defined. This vector is subtracted from the positions."""

    refquat: Quat = Quat()
    """Reference orientation relative to which the 3D vertex coordinates and normals are defined. The conjugate of this quaternion is used to rotate the positions and normals. The model compiler normalizes the quaternion automatically."""

    material: Optional[MaterialName] = None
    """Fallback material for mesh geoms that do not specify their own material."""


class MeshSphere(Mesh):
    """

    Repeated subdivisions of a unit icosahedron ("icosphere").
    """

    builtin: ClassVar[str] = "sphere"

    attributes = _mesh_attr + ("builtin", "subdivision")

    subdivision: int
    """integer in [0-4]: The number of subdivisions to apply to icosahedron faces."""

    @field_validator("subdivision")
    @classmethod
    def validate_subdivision(cls, v: int) -> int:
        if not 0 <= v <= 4:
            raise ValueError("subdivision must be in [0, 4]")
        return v


class MeshHemisphere(Mesh):
    """

    Quad-projected hemisphere.
    """

    builtin: ClassVar[str] = "hemisphere"

    attributes = _mesh_attr + ("builtin", "resolution")

    resolution: int
    """integer in [0-10]: Equator discretization of one hemisphere quadrant."""

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, v: int) -> int:
        if not 0 <= v <= 10:
            raise ValueError("resolution must be in [0, 10]")
        return v


class MeshCone(Mesh):
    """

    Cone mesh from top and bottom polygons.
    """

    builtin: ClassVar[str] = "cone"

    attributes = _mesh_attr + ("builtin", "nvert", "radius")

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


class MeshSupersphere(Mesh):
    """

    Supersphere (superellipsoid) shape.
    """

    builtin: ClassVar[str] = "supersphere"

    attributes = _mesh_attr + ("builtin", "resolution", "e", "n")

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


class MeshTorus(Mesh):
    """

    Supertorus (generalized torus) shape.
    """

    builtin: ClassVar[str] = "torus"

    attributes = _mesh_attr + ("builtin", "resolution", "radius", "s", "t")

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


class MeshWedge(Mesh):
    """

    Slice of a unit spherical shell.
    """

    builtin: ClassVar[str] = "wedge"

    attributes = _mesh_attr + (
        "builtin",
        "res_phi",
        "res_theta",
        "fov_phi",
        "fov_theta",
        "gamma",
    )

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


class MeshPlate(Mesh):
    """

    Rectangular plate mesh.
    """

    builtin: ClassVar[str] = "plate"

    attributes = _mesh_attr + ("builtin", "res_x", "res_y")

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


if __name__ == "__main__":
    MeshPlate(res_x=1, res_y=2)
    breakpoint()
