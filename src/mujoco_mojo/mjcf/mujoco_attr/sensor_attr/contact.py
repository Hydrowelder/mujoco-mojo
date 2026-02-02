from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorContact"]


class SensorContact(SensorBase):
    """"""

    tag = "contact"

    attributes = SensorBase.attributes + ()
