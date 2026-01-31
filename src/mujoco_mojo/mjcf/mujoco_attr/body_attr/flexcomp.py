from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.orientation import Orientation
from mujoco_mojo.typing import FlexCompDOF, FlexCompType, MaterialName, Vec3, Vec4, VecN
from mujoco_mojo.utils import is_empty_list

__all__ = ["FlexComp"]


class FlexComp(XMLModel):
    """Similar to composite, this element (new in MuJoCo 3.0) is not a model element, but rather a macro which expands into multiple model elements representing a deformable entity. In particular this macro creates one flex element, a number of bodies that are children of the body in which the flexcomp is defined, and optionally one flex equality which constrains all flex edges to their initial length. A number of attributes are specified here and then passed through to the automatically-constructed flex. The primary role of flexcomp is to automate the creation of a (possibly large) collection of moving bodies with corresponding joints, and connect them with stretchable flex elements. See flex and deformable objects documentation for specifics on how flexes work. Here we only describe the automated construction process.

    An important distinction between flex and flexcomp is that the flex references bodies and specifies vertex coordinates in the frames of those bodies, while the flexcomp defines points. Each flexcomp point corresponds to one body and one vertex in the underlying flex. If the flexcomp point is pinned, the corresponding flex body is the parent body of the flexcomp, while the corresponding flex vertex coordinates equal the flexcomp point coordinates. If the flexcomp point is not pinned, a new child body is created at the coordinates of the flexcomp point (within the flexcomp parent body), and then the coordinates of the flex vertex within that new body are (0,0,0). The mechanism for pinning flexcomp points is explained below.

    Composite objects (available prior to MuJoCo 3.0) needed bodies with geoms for collisions, and sites for connecting tendons which generated shape-preserving forces. In contrast, flexes generate their own collisions and shape-preserving forces (as well as rendering), thus the bodies created here are much simpler: no geoms, sites or tendons are needed. Most of the bodies created here have 3 orthogonal slider joints, corresponding to freely moving point masses. In some cases we generate radial slider joints, allowing only expansion and contraction. Since no geoms are generated, the bodies need to have explicit inertial parameters.

    Below is a simple example of a flexcomp, modeling a (somewhat flexible) double pendulum with one end pinned to the world:

    ```xml
    <mujoco>
        <worldbody>
            <flexcomp name="FL" type="grid" dim="1" count="3 1 1" mass="3" spacing="0.2 0.2 0.2">
                <pin id="0"/>
            </flexcomp>
        </worldbody>
    </mujoco>
    ```

    This flexcomp has 3 points, however the first point is pinned to the world (i.e. the parent of the flexcomp) and so only two bodies are automatically created, namely FL_1 and FL_2. Here is what this flexcomp generates after loading and saving the XML:

    ```xml
    <mujoco>
        <worldbody>
            <body name="FL_1">
                <inertial pos="0 0 0" mass="1" diaginertia="1.66667e-05 1.66667e-05 1.66667e-05"/>
                <joint pos="0 0 0" axis="1 0 0" type="slide"/>
                <joint pos="0 0 0" axis="0 1 0" type="slide"/>
                <joint pos="0 0 0" axis="0 0 1" type="slide"/>
            </body>
            <body name="FL_2" pos="0.2 0 0">
                <inertial pos="0 0 0" mass="1" diaginertia="1.66667e-05 1.66667e-05 1.66667e-05"/>
                <joint pos="0 0 0" axis="1 0 0" type="slide"/>
                <joint pos="0 0 0" axis="0 1 0" type="slide"/>
                <joint pos="0 0 0" axis="0 0 1" type="slide"/>
            </body>
        </worldbody>
        <deformable>
            <flex name="FL" dim="1" body="world FL_1 FL_2" vertex="-0.2 0 0 0 0 0 0 0 0" element="0 1 1 2"/>
        </deformable>
        <equality>
            <flex flex="FL"/>
        </equality>
    </mujoco>
    ```
    """

    tag = "flexcomp"
    attributes = (
        "name",
        "type",
        "group",
        "dim",
        "dof",
        "count",
        "spacing",
        "radius",
        "rigid",
        "mass",
        "inertiabox",
        "scale",
        "file",
        "point",
        "element",
        "texcoord",
        "material",
        "rgba",
        "flatskin",
        "pos",
        "orientation",
        "origin",
    )

    children = ("contacts", "edges", "elasticities", "pins", "plugins")

    name: str
    """The name of the flex element being generated automatically. This name is used as a prefix for all bodies that are automatically generated here, and is also referenced by the corresponding flex equality constraint (if applicable)."""

    dim: Optional[int] = None
    """Dimensionality of the flex object. This value must be 1, 2 or 3. The flex elements are capsules in 1D, triangles with radius in 2D, and tetrahedra with radius in 3D. Certain flexcomp types imply a dimensionality, in which case the value specified here is ignored."""

    dof: Optional[FlexCompDOF] = None
    """The parametrization of the flex's degrees of freedom (dofs). See the video on the right illustrating the different parametrizations with deformable spheres. The three models in the video are respectively sphere_full, sphere_radial and sphere_trilinear.

    * `full`: Three translational dofs per vertex. This is the most expressive but also the most expensive option.
    * `radial`: A single radial translational dof per vertex. Note that unlike in the "full" case, the radial parametrization requires a free joint at the flex's parent in order for free body motion to be possible. This type of parametrization is appropriate for shapes that are relatively spherical.
    * `trilinear`: Three translational dofs at each corner of the bounding box of the flex, for a total of 24 dofs for the entire flex, independent of the number of vertices. The positions of the vertices are updated using trilinear interpolation over the bounding box.

    Trilinear and quadratic flexes are much faster than the previous two options, and are the preferred choice if the expected deformations can be captured by the reduced parametriation. For example, see the video on the right comparing full and trilinear flexes for modeling deformable gripper pads.

    Note that the choice of dof parametrization affects the deformation modes of the flex but has no effect on the accuracy of the collision geometry, which always takes into account the high-resolution mesh of the flex.

    * `quadratic`: Three translational dofs per corner, edge, face, and volume of the bounding box of the flex, for a total of 81 dofs for the entire flex, independent of the number of vertices. The positions of the vertices are updated using quadratic interpolation over the bounding box. While this option requires more degrees of freedom than trilinear flexes, it enables curved deformation modes, while the only modes achievable for trilinear flexes are strech/compression and shear.

    Note that a higher interpolation order generally requires a smaller time step for stability, although usually not as large as with the "full" option and a fine mesh.
    """

    type: Optional[FlexCompType] = None
    """This attribute determines the type of flexcomp object. The remaining attributes and sub-elements are then interpreted according to the type. Default settings are also adjusted depending on the type. Different types correspond to different methods for specifying the flexcomp points and the stretchable elements that connect them. They fall in three categories: direct specification entered in the XML, direct specification loaded from file, and automated generation from higher-level specification.

    `grid` generates a rectangular grid of points in 1D, 2D or 3D as specified by dim. The number of points in each dimension is determined by count while the grid spacing in each dimension is determined by spacing. Make sure the spacing is sufficiently large relative to radius to avoid permanent contacts. In 2D and 3D the grid is automatically triangulated, and corresponding flex elements are created (triangles or tetrahedra). In 1D the elements are capsules connecting consecutive pairs of points.

    `box` generates a 3D box object, however flex bodies are only generated on the outer shell. Each flex body has a radial slider joint allowing it to move in and out from the center of the box. The parent body would normally be a floating body. The box surface is triangulated, and each flex element is a tetrahedron connecting the center of the box with one triangle face. count and spacing determine the count and spacing of the flex bodies, similar to the grid type in 3D. Note that the resulting flex has the same topology as the box generated by composite.

    `cylinder` is the same as box, except the points are projected on the surface of a cylinder.

    `ellipsoid` is the same as box, except the points are projected on the surface of an ellipsoid.

    `disc` is the same as box, except the points are projected on the surface of a disc. It is only compatible with dim=2.

    `circle` is the same as grid, except the points are sampled along a circle so that the first and last points are the same. The radius of the circle is computed such that each segment has the requested spacing. It is only compatible with dim=1.

    `mesh` loads the flexcomp points and elements (i.e. triangles) from a mesh file, in the same file formats as mesh assets, excluding the legacy .msh format. A mesh asset is not actually added to the model. Instead the vertex and face data from the mesh file are used to populate the point and element data of the flexcomp. dim is automatically set to 2. Recall that a mesh asset in MuJoCo can be used as a rigid geom attached to a single body. In contrast, the flex generated here corresponds to a soft mesh with the same initial shape, where each vertex is a separate moving body (unless pinned).

    `gmsh` is similar to mesh, but it loads a GMSH file in format 4.1 and format 2.2 (ascii or binary). The file extension can be anything; the parser recognizes the format by examining the file header. This is a very rich file format, allowing all kinds of elements with different dimensionality and topology. MuJoCo only supports GMSH element types 1, 2, 4 which happen to correspond to our 1D, 2D and 3D flexes and assumes that the nodes are specified in a single block. Only the Nodes and Elements sections of the GMHS file are processed, and used to populate the point and element data of the flexcomp. The parser will generate an error if the GMSH file contains meshes that are not supported by MuJoCo. dim is automatically set to the dimensionality specified in the GMSH file. Presently this is the only mechanism to load a large tetrahedral mesh in MuJoCo and generate a corresponding soft entity. If such a mesh is available in a different file format, use the freely available GMSH software to convert it to GMSH in one of the supported versions.

    `direct` allows the user to specify the point and element data of the flexcomp directly in the XML. Note that flexcomp will still generate moving bodies automatically, as well as automate other settings; so it still provides convenience compared to specifing the corresponding flex directly.
    """
    count: Optional[Tuple[int, int, int]] = None
    """The number of automatically generated points in each dimension. This and the next attribute only apply to types grid, box, cylinder, ellipsoid."""

    spacing: Optional[Vec3] = None
    """The spacing between the automatically generated points in each dimension. The spacing should be sufficiently large compared to the radius, to avoid permanent contacts."""

    point: Optional[VecN] = None
    """The 3D coordinates of the points. This attribute is only used with type direct. All other flexcomp types generate their own points. The points are used to construct bodies and vertices as explained earlier."""

    element: Optional[Tuple[int, ...]] = None
    """The zero-based point ids forming each flex elements. This attribute is only used with type direct. All other flexcomp types generate their own elements. This data is passed through to the automatically-generated flex."""

    texcoord: Optional[VecN] = None
    """Texture coordinates of each point, passed through to the automatically-generated flex. Note that flexcomp does not generate texture coordinates automatically, except for 2D grids, box, cylinder and ellipsoid. For all other types, the user can specify explicit texture coordinates here, even if the points themselves were generated automatically. This requires understanding of the layout of the automatically-generated points and how they correspond to the texture referenced by the material."""

    mass: Optional[float] = None
    """The mass of each automatically-generated body equals this value divided by the number of points. Note that pinning some points does not affect the mass of the other bodies."""

    inertiabox: Optional[float] = None
    """Even though the automatically-generated bodies have the physics of point masses, with slider joints, MuJoCo still requires each body to have rotational inertia. The inertias generated here are diagonal, and are computed such that the corresponding equivalent-inertia boxes have sides equal to this value."""

    file: Optional[Path] = None
    """The name of the file from which a surface (triangular) or volumetric (tetrahedral) mesh is loaded. For surface meshes, the file extension is used to determine the file format. Supported formats are GMSH and the formats specified in mesh assets, excluding the legacy .msh format. Volumetric meshes are supported only in GMSH format. See here for more information on GMSH files."""

    rigid: Optional[bool] = None
    """If this is true, all points correspond to vertices within the parent body, and no new bodies are created. This is equivalent to pinning all points. Note that if all points are indeed pinned, the model compiler will detect that the flex is rigid (which behaves is a non-convex mesh in collision detection)."""

    pos: Optional[Vec3] = None
    """This 3D vector translates all points relative to the frame of the parent body."""

    orientation: Optional[Orientation] = None
    """If using a quaternion, rotation of all points around the pos vector specified above. Together these two vectors define a pose transformation, used to position and orient the points as needed.

    Other orientations are options in place of quat."""

    scale: Optional[Vec3] = None
    """Scaling of all point coordinates, for types that specify coordinates explicitly. Scaling is applied after the pose transformation."""

    radius: Optional[float] = None
    """Radius of all flex elements. It can be zero in 3D, but must be positive in 1D and 2D. The radius affects both collision detection and rendering. In 1D and 2D it is needed to make the elements volumetric.

    Directly passed through to the automatically-generated flex object and have the same meaning."""

    material: Optional[MaterialName] = None
    """If specified, this attribute applies a material to the flex. Note that textures specified in the material will be applied only if the flex has explicit texture coordinates.

    Directly passed through to the automatically-generated flex object and have the same meaning."""

    rgba: Optional[Vec4] = None
    """Instead of creating material assets and referencing them, this attribute can be used to set color and transparency only. This is not as flexible as the material mechanism, but is more convenient and is often sufficient. If the value of this attribute is different from the internal default, it takes precedence over the material.

    Directly passed through to the automatically-generated flex object and have the same meaning."""

    group: Optional[int] = None
    """Integer group to which the flex belongs. This attribute can be used for custom tags. It is also used by the visualizer to enable and disable the rendering of entire groups of flexes.

    Directly passed through to the automatically-generated flex object and have the same meaning."""

    flatskin: Optional[bool] = None
    """This attribute determines whether 2D and 3D flexes that are rendered in flexskin mode will use smooth or flat shading. The default smooth shading is suitable in most cases, however if the object is intended to have visible sharp edges (such as a cube) then flat shading is more natural.

    Directly passed through to the automatically-generated flex object and have the same meaning."""

    origin: Optional[Vec3] = None
    """The origin of the flexcomp. Used for generating a volumetric mesh from an OBJ surface mesh. Each surface triangle is connected to the origin to create a tetrahedron, so the resulting volumetric mesh is guaranteed to be well-formed only for convex shapes."""

    contacts: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO these are mainly built off flex so Im gonna do those first
    edges: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO these are mainly built off flex so Im gonna do those first
    elasticities: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO these are mainly built off flex so Im gonna do those first
    pins: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO these are mainly built off flex so Im gonna do those first
    plugins: Sequence[float] = Field(
        default_factory=list, exclude_if=is_empty_list
    )  # TODO these are mainly built off flex so Im gonna do those first
