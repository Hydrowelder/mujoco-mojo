from __future__ import annotations

from mujoco_mojo.mjcf.mujoco_attr.equality_attr.equality_base import EqualityBase
from mujoco_mojo.typing import FlexName

__all__ = ["EqualityFlexStrain"]


class EqualityFlexStrain(EqualityBase):
    """
    This element constrains the strain of a trilinear or quadratic flex to its initial values. For trilinear elements, a B-bar formulation is used to prevent volumetric locking: the trace of strain (I₁) and volume ratio (J-1 = det(F)-1) are constrained at the element center, while the three off-diagonal shear components (E₁₂, E₁₃, E₂₃) are constrained at each of the 8 Gauss points, giving 26 constraints per element. For quadratic elements, all 6 strain components (3 invariants + 3 shear) are constrained at each of the 27 Gauss points, giving 162 constraints per element. This constraint type is only supported for dimension 3 flexes with trilinear or quadratic interpolation. See this model for an example.
    """

    tag = "flexstrain"

    attributes = (
        *EqualityBase.attributes,
        "flex",
    )

    flex: FlexName
    """Name of the flex whose strain is being constrained."""
