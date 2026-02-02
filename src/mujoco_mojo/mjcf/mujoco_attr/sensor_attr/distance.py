from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorDistance"]


class SensorDistance(SensorBase):
    """"""

    tag = "distance"

    attributes = SensorBase.attributes + ()
