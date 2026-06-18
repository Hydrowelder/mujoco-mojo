from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.mjcf.plugin import Plugin
from mujoco_mojo.typing import Name

__all__ = ["SensorPlugin"]


class SensorPlugin(SensorBase, Plugin):
    """Ascociate this sensor with an engine plugin. Either plugin or instance are required."""

    tag = "plugin"

    attributes = (
        *tuple([a for a in SensorBase.attributes if a not in ("noise",)]),
        *Plugin.attributes,
        "objtype",
        "objname",
        "reftype",
        "refname",
    )

    non_xml_fields = ("noise",)  # plugin sensors define their own noise model

    objtype: str | None = None
    """Type of MuJoCo object attached to this sensor."""

    objname: Name | None = None
    """Name of MuJoCo object attached to this sensor."""

    reftype: str | None = None
    """Type of the reference object."""

    refname: str | None = None
    """Name of the reference object."""
