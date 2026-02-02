from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorNormal"]


class SensorNormal(SensorBase):
    """"""

    tag = "normal"

    attributes = SensorBase.attributes + ()
