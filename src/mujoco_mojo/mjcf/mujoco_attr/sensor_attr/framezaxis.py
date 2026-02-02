from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorFramezaxis"]


class SensorFramezaxis(SensorBase):
    """"""

    tag = "framezaxis"

    attributes = SensorBase.attributes + ()
