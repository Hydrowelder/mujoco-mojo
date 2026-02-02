from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorUser"]


class SensorUser(SensorBase):
    """"""

    tag = "user"

    attributes = SensorBase.attributes + ()
