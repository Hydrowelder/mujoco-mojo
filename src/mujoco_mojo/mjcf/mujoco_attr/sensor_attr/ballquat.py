from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorBallquat"]


class SensorBallquat(SensorBase):
    """"""

    tag = "ballquat"

    attributes = SensorBase.attributes + ()
