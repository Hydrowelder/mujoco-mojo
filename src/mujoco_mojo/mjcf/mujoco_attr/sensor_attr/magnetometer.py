from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorMagnetometer"]


class SensorMagnetometer(SensorBase):
    """"""

    tag = "magnetometer"

    attributes = SensorBase.attributes + ()
