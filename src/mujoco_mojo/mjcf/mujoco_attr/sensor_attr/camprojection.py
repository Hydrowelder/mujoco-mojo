from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorCamprojection"]


class SensorCamprojection(SensorBase):
    """"""

    tag = "camprojection"

    attributes = SensorBase.attributes + ()
