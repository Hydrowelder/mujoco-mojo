from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorInsidesite"]


class SensorInsidesite(SensorBase):
    """"""

    tag = "insidesite"

    attributes = SensorBase.attributes + ()
