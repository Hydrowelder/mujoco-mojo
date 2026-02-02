from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorBallangvel"]


class SensorBallangvel(SensorBase):
    """"""

    tag = "ballangvel"

    attributes = SensorBase.attributes + ()
