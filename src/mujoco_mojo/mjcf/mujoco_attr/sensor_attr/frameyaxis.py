from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorFrameyaxis"]


class SensorFrameyaxis(SensorBase):
    """"""

    tag = "frameyaxis"

    attributes = SensorBase.attributes + ()
