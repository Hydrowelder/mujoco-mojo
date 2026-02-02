from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorFrameangvel"]


class SensorFrameangvel(SensorBase):
    """"""

    tag = "frameangvel"

    attributes = SensorBase.attributes + ()
