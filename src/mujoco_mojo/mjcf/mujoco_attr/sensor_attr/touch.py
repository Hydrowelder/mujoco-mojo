from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorTouch"]


class SensorTouch(SensorBase):
    """"""

    tag = "touch"

    attributes = SensorBase.attributes + ()
