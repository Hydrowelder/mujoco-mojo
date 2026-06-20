from __future__ import annotations

from mujoco_mojo.mjcf.mujoco_attr.actuator_attr.general import ActuatorGeneral
from mujoco_mojo.mjcf.plugin import Plugin

__all__ = ["ActuatorPlugin"]


class ActuatorPlugin(ActuatorGeneral, Plugin):
    """Associate this actuator with an engine plugin. Either `plugin` or `instance` are required."""

    tag = "plugin"
    attributes = ActuatorGeneral.attributes + Plugin.attributes
