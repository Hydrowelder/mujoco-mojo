from __future__ import annotations

from typing import Sequence

from pydantic import Field

from mujoco_mojo.mjcf.mujoco_attr.tendon_attr.fixed_attr.joint import TendonJoint
from mujoco_mojo.mjcf.mujoco_attr.tendon_attr.tendon_base import TendonBase
from mujoco_mojo.utils import is_empty_list

__all__ = ["Fixed"]


class Fixed(TendonBase):
    """This element creates an abstract tendon whose length is defined as a linear combination of joint positions. Recall that the tendon length and its gradient are the only quantities needed for simulation. Thus we could define any scalar function of joint positions, call it "tendon", and plug it in MuJoCo. Presently the only such function is a fixed linear combination. The attributes of fixed tendons are a subset of the attributes of spatial tendons and have the same meaning as above."""

    tag = "fixed"

    children = ("joints",)

    joints: Sequence[TendonJoint] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Joint elements assigned to Fixed."""
