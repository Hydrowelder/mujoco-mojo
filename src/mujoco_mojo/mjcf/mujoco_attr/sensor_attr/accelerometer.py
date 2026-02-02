from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorAccelerometer"]


class SensorAccelerometer(SensorBase):
    """"""

    tag = "accelerometer"

    attributes = SensorBase.attributes + ()
