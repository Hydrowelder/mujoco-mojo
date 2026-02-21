from __future__ import annotations

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import BodyName, Vec3, Vec4, VecN

__all__ = ["Bone"]


class Bone(XMLModel):
    """This element defines a bone of the skin. The bone is a regular MuJoCo body which is referenced by name here."""

    tag = "bone"

    attributes = (
        "body",
        "bindpos",
        "bindquat",
        "vertid",
        "vertweight",
    )

    body: BodyName
    """Name of the body corresponding to this bone."""

    bindpos: Vec3
    """Global body position corresponding to the bind pose."""

    bindquat: Vec4
    """Global body orientation corresponding to the bind pose."""

    vertid: VecN
    """Integer indices of the vertices influenced by this bone. The vertex index corresponds to the order of the vertex in the skin mesh. The number of vertex indices specified here (nvert) must equal the number of vertex weights specified with the next attribute. The same vertex may be influenced by multiple bones, and each vertex must be influenced by at least one bone."""

    vertweight: VecN
    """Weights for the vertices influenced by this bone, in the same order as the vertex indices. Negative weights are allowed (which is needed for cubic interpolation for example) however the sum of all bone weights for a given vertex must be positive."""
