from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorFramequat"]


class SensorFramequat(SensorBase):
    """"""

    tag = "framequat"

    attributes = SensorBase.attributes + ()
