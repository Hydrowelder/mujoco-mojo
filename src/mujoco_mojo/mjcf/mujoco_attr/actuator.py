from __future__ import annotations

from pydantic import Field

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.adhesion import ActuatorAdhesion
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.cylinder import ActuatorCylinder
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.damper import ActuatorDamper
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.general import ActuatorGeneral
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.intvelocity import (
    ActuatorIntegratedVelocity,
)
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.motor import ActuatorMotor
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.muscle import ActuatorMuscle
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.plugin import ActuatorPlugin
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.position import ActuatorPosition
from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.velocity import ActuatorVelocity
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.utils.utils import is_empty_list

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
        "muscles",
        "adhesions",
        "plugins",
    )

    generals: list[ActuatorGeneral] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Generals actuator elements."""

    motors: list[ActuatorMotor] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Motors actuator elements."""

    positions: list[ActuatorPosition] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Positions actuator elements."""

    velocities: list[ActuatorVelocity] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Velocities actuator elements."""

    intvelocities: list[ActuatorIntegratedVelocity] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Intvelocities actuator elements."""

    dampers: list[ActuatorDamper] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Dampers actuator elements."""

    cylinders: list[ActuatorCylinder] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Cylinders actuator elements."""

    muscles: list[ActuatorMuscle] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Muscles actuator elements."""

    adhesions: list[ActuatorAdhesion] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Adhesions actuator elements."""

    plugins: list[ActuatorPlugin] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Plugins actuator elements."""
