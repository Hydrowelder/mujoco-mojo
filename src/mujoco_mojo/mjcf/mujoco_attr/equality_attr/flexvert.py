from __future__ import annotations

from mujoco_mojo.mjcf.mujoco_attr.equality_attr.equality_base import EqualityBase
from mujoco_mojo.typing import FlexName

__all__ = ["EqualityFlexVert"]


class EqualityFlexVert(EqualityBase):
    """
    This element constrains the trace and the derminant of the strain tensor to that of the identity matrix as in Chen, Kry, and Vouga, "Locking-free Simulation of Isometric Thin Plates", 2019. The strain tensor is computed per triangle and averaged over all triangles adjacent to a vertex. This reduces the number of constraints from 2T to 2V, freeing V degrees of freedom to avoid locking. It is only supported for dimension 2, i.e., cloth-like flexes. See this model for an example.
    """

    tag = "flexvert"

    attributes = (
        *EqualityBase.attributes,
        "flex",
    )

    flex: FlexName
    """Name of the flex whose vertices are being constrained."""
