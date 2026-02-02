from copy import deepcopy

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.flex_attr.elasticity import (
    FlexElasticity,
)
from mujoco_mojo.typing import FlexElastic2D


class FlexCompElasticity(XMLModel):
    tag = "elasticity"

    attributes = (
        "young",
        "poisson",
        "damping",
        "thickness",
        "elastic2d",
    )

    young: float = Field(
        default_factory=lambda: deepcopy(FlexElasticity.model_fields["young"].default),
    )
    """Same as in flex/elasticity. All attributes are passed through to the automatically-generated flex."""

    poisson: float = Field(
        default_factory=lambda: deepcopy(
            FlexElasticity.model_fields["poisson"].default,
        ),
    )
    """Same as in flex/elasticity. All attributes are passed through to the automatically-generated flex."""

    damping: float = Field(
        default_factory=lambda: deepcopy(
            FlexElasticity.model_fields["damping"].default,
        ),
    )
    """Same as in flex/elasticity. All attributes are passed through to the automatically-generated flex."""

    thickness: float = Field(
        default_factory=lambda: deepcopy(
            FlexElasticity.model_fields["thickness"].default,
        ),
    )
    """Same as in flex/elasticity. All attributes are passed through to the automatically-generated flex."""

    elastic2d: FlexElastic2D = Field(
        default_factory=lambda: deepcopy(
            FlexElasticity.model_fields["elastic2d"].default,
        ),
    )
    """Same as in flex/elasticity. All attributes are passed through to the automatically-generated flex."""
