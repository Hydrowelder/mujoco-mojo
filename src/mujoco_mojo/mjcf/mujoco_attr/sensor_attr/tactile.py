from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorTactile"]


class SensorTactile(SensorBase):
    """"""

    tag = "tactile"

    attributes = SensorBase.attributes + ()
