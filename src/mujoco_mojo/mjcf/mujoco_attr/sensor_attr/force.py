from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorForce"]


class SensorForce(SensorBase):
    """"""

    tag = "force"

    attributes = SensorBase.attributes + ()
