from __future__ import annotations

import numpy as np

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.flex_attr.contact import FlexContact
from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.flex_attr.edge import FlexEdge
from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.flex_attr.elasticity import (
    FlexElasticity,
)
from mujoco_mojo.typing import FlexName, MaterialName, Vec4, VecN

__all__ = ["Flex"]


class Flex(XMLModel):
    """Flexible objects (or flexes) were added in MuJoCo 3.0. These are collections of massless stretchable geometric elements (capsules, triangles or tetrahedra) connecting vertices that are defined within different moving body frames. These stretchable elements support collisions and contact forces, which are then distributed to all the interconnected bodies. Flexes also generate passive and constraint forces as needed to simulate deformable entities with the desired material properties. The modeling of flexes is automated and simplified by the flexcomp element. In most cases, the user will specify a flexcomp which will then automatically construct the corresponding low-level flex. See deformable objects for additional information."""

    tag = "flex"

    attributes = (
        "name",
        "group",
        "dim",
        "radius",
        "material",
        "rgba",
        "flatskin",
        "body",
        "vertex",
        "element",
        "texcoord",
        "elemtexcoord",
        "node",
    )
    children = ("contact", "edge", "elasticity")

    name: FlexName | None = None
    """Name of the flex."""

    dim: int = 2
    """Dimensionality of the flex. Allowed values are 1, 2 and 3. In 1D the elements are capsules, in 2D the elements are triangles with radius, in 3D the elements are tetrahedra with (optional) radius."""

    radius: float = 0.005
    """Radius of all flex elements. It can be zero in 3D, but must be positive in 1D and 2D. The radius affects both collision detection and rendering. In 1D and 2D it is needed to make the elements volumetric."""

    body: str
    """An array of MuJoCo body names (separated by white space) to which each vertex belongs. The number of body names should either equal the number of vertices (nvert), or be a single body. If a single body is specified, all vertices are defined within that body - in which case the flex becomes a rigid body. The latter functionality effectively creates a general non-convex mesh (unlike mesh geoms which are convexified for collision detection purposes)."""

    vertex: VecN | None = None
    """The local coordinates of the vertices within the corresponding body frames. If this attribute is omitted, all coordinates are (0,0,0) or in other words, the vertices coincide with the centers of the body frames."""

    texcoord: VecN | None = None
    """Texture coordinates. If omitted, texture mapping for this flex is disabled, even if a texture is specified in the material."""

    elemtexcoord: VecN | None = None
    """Texture indices for each face. If omitted, texture are assumed to be vertex-based."""

    element: VecN | None = None
    """For each element of the flex, this lists the zero-based indices of the vertices forming that flex element. We need two vertices to specify a capsule, three vertices to specify a triangle, and four vertices to specify a tetrahedron - which is why the number of indices equals (dim+1) times the number of elements. In 2D, the vertices should be listed in counter-clockwise order. In 1D and 3D the order is irrelevant; in 3D the model compiler will rearrange the vertices as needed. Repeated vertex indices within a flex element are not allowed. The topology of the flex is not enforced; it could correspond to a continuous soft body, or a collection of disconnected stretchable elements, or anything in-between."""

    flatskin: bool = False
    """This attribute determines whether 2D and 3D flexes that are rendered in flexskin mode will use smooth or flat shading. The default smooth shading is suitable in most cases, however if the object is intended to have visible sharp edges (such as a cube) then flat shading is more natural."""

    material: MaterialName | None = None
    """If specified, this attribute applies a material to the flex. Note that textures specified in the material will be applied only if the flex has explicit texture coordinates."""

    rgba: Vec4 = np.array((0.5, 0.5, 0.5, 1))
    """Instead of creating material assets and referencing them, this attribute can be used to set color and transparency only. This is not as flexible as the material mechanism, but is more convenient and is often sufficient. If the value of this attribute is different from the internal default, it takes precedence over the material."""

    group: int = 0
    """Integer group to which the flex belongs. This attribute can be used for custom tags. It is also used by the visualizer to enable and disable the rendering of entire groups of flexes."""

    node: str | None = None
    """The degrees-of-freedom of the flex. An array of MuJoCo body names (separated by white space) to which each node belongs. The number of body names should equal the number of nodes (nnode). See the flexcomp dof attribute for more details."""

    edge: FlexEdge | None = None
    """Edge constraint properties of Flex."""

    elasticity: FlexElasticity | None = None
    """Elasticity model properties of Flex."""

    contact: FlexContact | None = None
    """Contact properties of Flex."""
