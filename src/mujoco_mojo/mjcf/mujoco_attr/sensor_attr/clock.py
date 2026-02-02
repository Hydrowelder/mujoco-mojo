from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorClock"]


class SensorClock(SensorBase):
    """"""

    tag = "clock"

    attributes = SensorBase.attributes + ()
