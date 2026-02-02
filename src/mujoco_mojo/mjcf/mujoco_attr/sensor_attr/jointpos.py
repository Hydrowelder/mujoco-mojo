from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorJointpos"]


class SensorJointpos(SensorBase):
    """"""

    tag = "jointpos"

    attributes = SensorBase.attributes + ()
