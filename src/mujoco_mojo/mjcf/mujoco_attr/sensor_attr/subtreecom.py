from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorSubtreecom"]


class SensorSubtreecom(SensorBase):
    """"""

    tag = "subtreecom"

    attributes = SensorBase.attributes + ()
