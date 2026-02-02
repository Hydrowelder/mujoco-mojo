from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorFramexaxis"]


class SensorFramexaxis(SensorBase):
    """"""

    tag = "framexaxis"

    attributes = SensorBase.attributes + ()
