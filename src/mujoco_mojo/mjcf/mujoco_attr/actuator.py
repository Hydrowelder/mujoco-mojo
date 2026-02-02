from __future__ import annotations

from typing import Sequence

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.cylinder import ActuatorCylinder
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.damper import ActuatorDamper
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.general import ActuatorGeneral
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.intvelocity import (
    ActuatorIntegratedVelocity,
)
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.motor import ActuatorMotor
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.position import ActuatorPosition
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.velocity import ActuatorVelocity
from mujoco_mojo.utils import is_empty_list

__all__ = ["Actuator"]


class Actuator(XMLModel):
    """This is a grouping element for actuator definitions. Recall the discussion of MuJoCo's Actuation model in the Computation chapter, and the Actuator shortcuts discussed earlier in this chapter. The first 13 attributes of all actuator-related elements below are the same, so we document them only once, under the general actuator."""

    tag = "actuator"

    children = (
        "generals",
        "motors",
        "positions",
        "velocities",
        "intvelocities",
        "dampers",
        "cylinders",
        # "muscles",
        # "adhesions",
        # "plugins",
    )

    generals: Sequence[ActuatorGeneral] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Generals actuator elements."""

    motors: Sequence[ActuatorMotor] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Motors actuator elements."""

    positions: Sequence[ActuatorPosition] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Positions actuator elements."""

    velocities: Sequence[ActuatorVelocity] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Velocities actuator elements."""

    intvelocities: Sequence[ActuatorIntegratedVelocity] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Intvelocities actuator elements."""

    dampers: Sequence[ActuatorDamper] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Dampers actuator elements."""

    cylinders: Sequence[ActuatorCylinder] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Cylinders actuator elements."""

    # muscles: Sequence[] = Field(
    #     default_factory=list,
    #     exclude_if=is_empty_list,
    # )
    # """Muscles actuator elements."""

    # adhesions: Sequence[] = Field(
    #     default_factory=list,
    #     exclude_if=is_empty_list,
    # )
    # """Adhesions actuator elements."""

    # plugins: Sequence[] = Field(
    #     default_factory=list,
    #     exclude_if=is_empty_list,
    # )
    # """Plugins actuator elements."""
