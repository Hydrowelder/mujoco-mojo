from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorPlugin"]


class SensorPlugin(SensorBase):
    """"""

    tag = "plugin"

    attributes = SensorBase.attributes + ()
