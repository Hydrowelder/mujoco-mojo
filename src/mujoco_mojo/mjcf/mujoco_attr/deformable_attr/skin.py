from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.skin_attr.bone import Bone
from mujoco_mojo.typing import DeformableSkinName, MaterialName, Vec4, VecN
from mujoco_mojo.utils import is_empty_list

__all__ = ["DeformableSkin"]


class DeformableSkin(XMLModel):
    """
    These are deformable meshes whose vertex positions and normals are computed each time the model is rendered. MuJoCo skins are only used for visualization and do not affect the physics in any way. In particular, collisions involve the geoms of the bodies to which the skin is attached, and not the skin itself. Unlike regular meshes which are referenced from geoms and participate in collisions, the skin is not referenced from anywhere else in the model. It is a stand-alone element that is used by renderer and not by the simulator.

    The skin has vertex positions and normals updated at runtime, and triangle faces and optional texture coordinates which are predefined. It also has "bones" used for updating. Bones are regular MuJoCo bodies referenced with the bone subelement. Each bone has a list of vertex indices and corresponding real-valued weights which specify how much the bone position and orientation influence the corresponding vertex. The vertex has local coordinates with respect to every bone that influences it. The local coordinates are computed by the model compiler, given global vertex coordinates and global bind poses for each body. The bind poses do not have to correspond to the model reference configuration qpos0. Note that the vertex positions and bone bind poses provided in the skin definition are always global, even if the model itself is defined in local coordinates.

    At runtime the local coordinates of each vertex with respect to each bone that influences it are converted to global coordinates, and averaged in proportion to the corresponding weights to obtain a single set of 3D coordinates for each vertex. Normals then are computed automatically given the resulting global vertex positions and face information. Finally, the skin can be inflated by applying an offset to each vertex position along its (computed) normal. Skins are one-sided for rendering purposes; this is because back-face culling is needed to avoid shading and aliasing artifacts. When the skin is a closed 3D shape this does not matter because the back sides cannot be seen. But if the skin is a 2D object, we have to specify both sides and offset them slightly to avoid artifacts. Note that the composite objects generate skins automatically. So one can save an XML model with a composite object, and obtain an elaborate example of how a skin is specified in the XML.

    Similar to meshes, skins can be specified directly in the XML via attributes documented later, or loaded from a binary SKN file which is in a custom format. The specification of skins is more complex than meshes because of the bone subelements. The file format starts with a header of 4 integers: nvertex, ntexcoord, nface, nbone. The first three are the same as in meshes, and specify the total number of vertices, texture coordinate pairs, and triangle faces in the skin. ntexcoord can be zero or equal to nvertex. nbone specifies the number of MuJoCo bodies that will be used as bones in the skin. The header is followed by the vertex, texcoord and face data, followed by a specification for each bone. The bone specification contains the name of the corresponding model body, 3D bind position, 4D bind quaternion, number of vertices influenced by the bone, and the vertex index array and weight array. Body names are represented as fixed-length character arrays and are expected to be 0-terminated. Characters after the first 0 are ignored. The contents of the SKN file are:

    ```
    (int32)   nvertex
    (int32)   ntexcoord
    (int32)   nface
    (int32)   nbone
    (float)   vertex_positions[3*nvertex]
    (float)   vertex_texcoords[2*ntexcoord]
    (int32)   face_vertex_indices[3*nface]
    for each bone:
        (char)    body_name[40]
        (float)   bind_position[3]
        (float)   bind_quaternion[4]
        (int32)   vertex_count
        (int32)   vertex_index[vertex_count]
        (float)   vertex_weight[vertex_count]
    ```

    Similar to the other custom binary formats used in MuJoCo, the file size in bytes is strictly enforced by the model compiler. The skin file format has subelements so the overall file size formula is difficult to write down, but should be clear from the above specification.
    """

    tag = "skin"

    attributes = (
        "name",
        "file",
        "material",
        "rgba",
        "inflate",
        "vertex",
        "texcoord",
        "face",
        "group",
    )

    children = ("bones",)

    name: DeformableSkinName | None = None
    """Name of the skin."""

    file: Path | None = None
    """The SKN file from which the skin will be loaded. The path is determined as described in the meshdir attribute of compiler. If the file is omitted, the skin specification must be provided in the XML using the attributes below."""

    vertex: VecN | None = None
    """Vertex 3D positions, in the global bind pose where the skin is defined."""

    texcoord: VecN | None = None
    """Vertex 2D texture coordinates, between 0 and 1. Note that skin and geom texturing are somewhat different. Geoms can use automated texture coordinate generation while skins cannot. This is because skin data are computed directly in global coordinates. So if the material references a texture, one should specify explicit texture coordinates for the skin using this attribute. Otherwise the texture will appear to be stationary in the world while the skin moves around (creating an interesting effect but probably not as intended)."""

    face: VecN | None = None
    """Trinagular skin faces. Each face is a triple of vertex indices, which are integers between zero and nvert-1."""

    inflate: float = 0
    """If this number is not zero, the position of vertex during updating will be offset along the vertex normal, but the distance specified in this attribute. This is particularly useful for skins representing flexible 2D shapes."""

    material: MaterialName | None = None
    """If specified, this attribute applies a material to the skin."""

    rgba: Vec4 = np.array((0.5, 0.5, 0.5, 1))
    """Instead of creating material assets and referencing them, this attribute can be used to set color and transparency only. This is not as flexible as the material mechanism, but is more convenient and is often sufficient. If the value of this attribute is different from the internal default, it takes precedence over the material."""

    group: int = 0
    """Integer group to which the skin belongs. This attribute can be used for custom tags. It is also used by the visualizer to enable and disable the rendering of entire groups of skins."""

    bones: Sequence[Bone] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Bones defined in the skin."""
