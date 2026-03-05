from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal, Self, overload

import mujoco
import numpy as np
from pydantic import field_validator, model_validator

from mujoco_mojo.mjcf.dependency_path import DepPath
from mujoco_mojo.mjcf.orientation import Quat
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import Inertia, MaterialName, MeshName, Vec3
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = [
    "Mesh",
    "MeshCone",
    "MeshHemisphere",
    "MeshPlate",
    "MeshSphere",
    "MeshSupersphere",
    "MeshTorus",
    "MeshWedge",
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
    """
    This element creates a mesh asset, which can then be referenced from geoms. If the referencing geom type is mesh the mesh is instantiated in the model, otherwise a geometric primitive is automatically fitted to it; see the geom element below.

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
    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_MESH

    name: MeshName | None = None
    """Name of the mesh, used for referencing. If omitted, the mesh name equals the file name without the path and extension."""

    class_: str | None = None
    """Defaults class for setting unspecified attributes (only scale in this case)."""

    content_type: str | None = None
    """If the file attribute is specified, then this sets the Media Type (formerly known as MIME type) of the file to be loaded. Any filename extensions will be overloaded. Currently model/vnd.mujoco.msh, model/obj, and model/stl are supported."""

    file: DepPath | None = None
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

    vertex: tuple[tuple[float, float, float], ...] | None = None
    """Vertex 3D position data. You can specify position data in the XML using this attribute, or using a binary file, but not both."""

    normal: tuple[tuple[float, float, float], ...] | None = None
    """Vertex 3D normal data. If specified, the number of normals must equal the number of vertices. The model compiler normalizes the normals automatically."""

    texcoord: tuple[tuple[float, float], ...] | None = None
    """Vertex 2D texture coordinates, which are numbers between 0 and 1. If specified, the number of texture coordinate pairs must equal the number of vertices."""

    face: tuple[tuple[int, int, int], ...] | None = None
    """Faces of the mesh. Each face is a sequence of 3 vertex indices, in counter-clockwise order. The indices must be integers between 0 and nvert-1."""

    refpos: Pos = Pos(pos=np.array((1, 1, 1)))
    """Reference position relative to which the 3D vertex coordinates are defined. This vector is subtracted from the positions."""

    refquat: Quat = Quat()
    """Reference orientation relative to which the 3D vertex coordinates and normals are defined. The conjugate of this quaternion is used to rotate the positions and normals. The model compiler normalizes the quaternion automatically."""

    material: MaterialName | None = None
    """Fallback material for mesh geoms that do not specify their own material."""

    @model_validator(mode="after")
    def validate_file(self) -> Self:
        # make the file extension lowercase
        if self.file is not None and self.file.suffix not in [".stl", ".msh", ".obj"]:
            msg = f'Mesh {self.name}: Invalid file suffix ({self.file.suffix}). Must be ".stl", ".msh", or ".obj".'
            logger.error(msg)
            raise ValueError(msg)

        # assert that only one or none are defined
        file_provided = self.file is not None
        vertex_provided = self.vertex is not None
        if not (file_provided ^ vertex_provided):
            msg = f"Mesh {self.name}: One of file or vertex may be provided ({file_provided=}, {vertex_provided=})."
            logger.error(msg)
            raise ValueError(msg)
        return self

    @overload
    @classmethod
    def decompose_mesh(
        cls,
        path: Path,
        threshold: float = 0.05,
        max_convex_hulls: int = -1,
        vertex: Literal[False] = False,
        save_dir: DepPath = ...,
        save_preview: Path | None = None,
        **kwargs,
    ) -> list[Self]: ...

    @classmethod
    @overload
    def decompose_mesh(
        cls,
        path: Path,
        threshold: float = 0.05,
        max_convex_hulls: int = -1,
        vertex: Literal[True] = ...,
        save_dir: None = None,
        save_preview: Path | None = None,
        **kwargs,
    ) -> list[Self]: ...

    @classmethod
    def decompose_mesh(
        cls,
        path: Path,
        threshold: float = 0.05,
        max_convex_hulls: int = -1,
        vertex: bool = False,
        save_dir: DepPath | None = None,
        save_preview: Path | None = None,
        **kwargs,
    ) -> list[Self]:
        """
        Loads a mesh using trimesh before decomposing it using [CoACD](https://github.com/SarahWeiii/CoACD).

        This comes at the cost of file space, import speed, and runtime (especially for calculating minimum geometric distances).

        Note:
            This may be a good method to wrap in a memory cache as it can be expensive. It is also recommended to use `vertex=False` and `save_dir` if running Monte Carlo.

        Args:
            path (Path): Path to the input STL/OBJ file.
            threshold (float, optional): Surface distance threshold (lower = more parts/more accurate). Defaults to 0.05.
            max_convex_hulls (int, optional): Hard limit on number of hulls. -1 for no limit.
            vertex (bool, optional): If True, the generated meshes will be the vertex type (this is not really suitable for multi-run jobs since the XML file becomes quite large). If False, the save_as parameter becomes required and will save
            save_dir (DepPath, optional): Required when vertex is False. Where to save resulting mesh files if vertex is False. Mesh files are saved with the format `f"{path.stem}_{i}{[path.suffix]}"`.
            save_preview (Path, optional): Where to save a preview of the generated meshes. The meshes are filled with a random color. Example is `Path("mesh_decomposed.obj")`.
            kwargs: Keyword arguments to pass to CoACD.

        Returns:
            list[Mesh]: Resulting mesh objects.

        Example:
            Default settings (threshold=0.05, max_convex_hulls=-1), using [Bottle.obj](https://github.com/SarahWeiii/CoACD/blob/main/examples/Bottle.obj)

            | Without | With    |
            |:-------:|:-------:|
            | 48 KB   | 1.13 MB |
            | <img src="https://raw.githubusercontent.com/Hydrowelder/mujoco-mojo/refs/heads/master/docs/assets/mesh/without_coacd.jpg" width="300" /> | <img src="https://raw.githubusercontent.com/Hydrowelder/mujoco-mojo/refs/heads/master/docs/assets/mesh/with_coacd.jpg" width="300" /> |


        """
        # make sure inputs are valid and mkdir
        if save_dir is None and not vertex:
            msg = f"Mesh {path.stem}: save_dir is required when vertex=False."
            logger.exception(msg)
            raise ValueError(msg)

        try:
            import coacd
            import trimesh
        except ModuleNotFoundError:
            msg = "The `coacd` and `trimesh` packages are required. Install with `uv add coacd trimesh` or `pip install coacd trimesh`"
            logger.exception(msg)
            raise ModuleNotFoundError(msg)

        logger.info(f"Decomposing {path} with {threshold=} and {max_convex_hulls=}")

        # load the original mesh
        t_mesh = trimesh.load(path, force="mesh")

        # prepare the CoACD mesh
        coacd_mesh = coacd.Mesh(t_mesh.vertices, t_mesh.faces)  # pyright: ignore[reportAttributeAccessIssue]

        # decompose
        result = coacd.run_coacd(
            mesh=coacd_mesh,
            threshold=threshold,
            max_convex_hull=max_convex_hulls,
            **kwargs,
        )

        # convert meshes into Mesh objects
        decomposed_mojo_meshes = []
        base_name = path.stem

        if vertex:
            for i, (verts, faces) in enumerate(result):
                part_mesh = cls(
                    name=MeshName(f"{base_name}_{i}"),
                    vertex=tuple(map(tuple, verts.tolist())),
                    face=tuple(map(tuple, faces.tolist())),
                    inertia=Inertia.CONVEX,  # Guaranteed convex by CoACD
                )
                decomposed_mojo_meshes.append(part_mesh)
        else:
            assert save_dir is not None  # this is checked at the top of the function
            save_dir.mkdir(parents=True, exist_ok=True)

            # save meshes to dir
            for i, (vs, fs) in enumerate(result):
                # construct mesh and export
                name = f"{base_name}_{i}"
                export_path = save_dir / f"{name}{path.suffix}"

                part_trimesh = trimesh.Trimesh(vs, fs)
                part_trimesh.export(export_path)

                # create mojo mesh
                decomposed_mojo_meshes.append(
                    cls(
                        name=MeshName(f"{base_name}_{i}"),
                        file=export_path,
                        inertia=Inertia.CONVEX,
                    )
                )

        if save_preview is not None:
            scene = trimesh.Scene()
            rng = np.random.default_rng(42)
            for i, (vs, fs) in enumerate(result):
                p = trimesh.Trimesh(vs, fs)

                p.visual.vertex_colors[:, :3] = (rng.random(3) * 255).astype(  # type: ignore
                    np.uint8
                )
                scene.add_geometry(p)
            scene.export(save_preview)
            logger.info(f"Saved decomposition preview to {save_preview}")
        return decomposed_mojo_meshes


class MeshSphere(Mesh):
    """
    Repeated subdivisions of a unit icosahedron ("icosphere").

    <img src="https://raw.githubusercontent.com/google-deepmind/mujoco/refs/heads/main/doc/images/XMLreference/s.png" width="300" />
    """

    builtin: ClassVar[str] = "sphere"

    attributes = (*_mesh_attr, "builtin", "subdivision")

    subdivision: int
    """integer in [0-4]: The number of subdivisions to apply to icosahedron faces."""

    @field_validator("subdivision")
    @classmethod
    def validate_subdivision(cls, v: int) -> int:
        if not 0 <= v <= 4:
            msg = "subdivision must be in [0, 4]"
            logger.error(msg)
            raise ValueError(msg)
        return v


class MeshHemisphere(Mesh):
    """
    Quad-projected hemisphere.

    <img src="https://raw.githubusercontent.com/google-deepmind/mujoco/refs/heads/main/doc/images/XMLreference/h.png" width="300" />
    """

    builtin: ClassVar[str] = "hemisphere"

    attributes = (*_mesh_attr, "builtin", "resolution")

    resolution: int
    """integer in [0-10]: Equator discretization of one hemisphere quadrant."""

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, v: int) -> int:
        if not 0 <= v <= 10:
            msg = "resolution must be in [0, 10]"
            logger.error(msg)
            raise ValueError(msg)
        return v


class MeshCone(Mesh):
    """
    Cone mesh from top and bottom polygons.

    <img src="https://raw.githubusercontent.com/google-deepmind/mujoco/refs/heads/main/doc/images/XMLreference/c.png" width="300" />
    """

    builtin: ClassVar[str] = "cone"

    attributes = (*_mesh_attr, "builtin", "nvert", "radius")

    nvert: int
    """integer >= 3: The number of vertices in the polygon."""

    radius: float
    """real in [0, 1]: The radius of the top face."""

    @field_validator("nvert")
    @classmethod
    def validate_nvert(cls, v: int) -> int:
        if v < 3:
            msg = "nvert must be >= 3"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @field_validator("radius")
    @classmethod
    def validate_radius(cls, v: float) -> float:
        if not 0 <= v <= 1:
            msg = "radius must be in [0, 1]"
            logger.error(msg)
            raise ValueError(msg)
        return v


class MeshSupersphere(Mesh):
    """
    Supersphere (superellipsoid) shape.

    <img src="https://raw.githubusercontent.com/google-deepmind/mujoco/refs/heads/main/doc/images/XMLreference/ss.png" width="300" />
    """

    builtin: ClassVar[str] = "supersphere"

    attributes = (*_mesh_attr, "builtin", "resolution", "e", "n")

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
            msg = "resolution must be >= 3"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @field_validator("e", "n")
    @classmethod
    def validate_non_negative(cls, v: float) -> float:
        if v < 0:
            msg = "must be >= 0"
            logger.error(msg)
            raise ValueError(msg)
        return v


class MeshTorus(Mesh):
    """
    Supertorus (generalized torus) shape.

    <img src="https://raw.githubusercontent.com/google-deepmind/mujoco/refs/heads/main/doc/images/XMLreference/st.png" width="300" />
    """

    builtin: ClassVar[str] = "torus"

    attributes = (*_mesh_attr, "builtin", "resolution", "radius", "s", "t")

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
            msg = "resolution must be >= 3"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @field_validator("radius")
    @classmethod
    def validate_radius(cls, v: float) -> float:
        if not 0 < v <= 1:
            msg = "radius must be in (0, 1]"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @field_validator("s", "t")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v <= 0:
            msg = "must be > 0"
            logger.error(msg)
            raise ValueError(msg)
        return v


class MeshWedge(Mesh):
    """
    Slice of a unit spherical shell.

    <img src="https://raw.githubusercontent.com/google-deepmind/mujoco/refs/heads/main/doc/images/XMLreference/w.png" width="300" />
    """

    builtin: ClassVar[str] = "wedge"

    attributes = (
        *_mesh_attr,
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
            msg = "must be >= 0"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @field_validator("fov_phi")
    @classmethod
    def validate_fov_phi(cls, v: float) -> float:
        if not 0 < v <= 180:
            msg = "fov_phi must be in (0, 180]"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @field_validator("fov_theta")
    @classmethod
    def validate_fov_theta(cls, v: float) -> float:
        if not 0 < v < 90:
            msg = "fov_theta must be in (0, 90)"
            logger.error(msg)
            raise ValueError(msg)
        return v

    @field_validator("gamma")
    @classmethod
    def validate_gamma(cls, v: float) -> float:
        if not 0 <= v <= 1:
            msg = "gamma must be in [0, 1]"
            logger.error(msg)
            raise ValueError(msg)
        return v


class MeshPlate(Mesh):
    """A rectangular plate with given resolution in each dimension. This mesh is designed to be used by the tactile sensor, which reports data at the vertices."""

    builtin: ClassVar[str] = "plate"

    attributes = (*_mesh_attr, "builtin", "res_x", "res_y")

    res_x: int
    """integer > 0: Horizontal resolution of the plate."""

    res_y: int
    """integer > 0: Vertical resolution of the plate."""

    @field_validator("res_x", "res_y")
    @classmethod
    def validate_positive(cls, v: int) -> int:
        if v <= 0:
            msg = "must be > 0"
            logger.error(msg)
            raise ValueError(msg)
        return v


if __name__ == "__main__":
    MeshPlate(res_x=1, res_y=2)

    Mesh.decompose_mesh(path=Path())
    breakpoint()
