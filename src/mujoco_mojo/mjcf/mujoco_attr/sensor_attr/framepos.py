from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorFramepos"]


class SensorFramepos(SensorBase):
    """"""

    tag = "framepos"

    attributes = SensorBase.attributes + ()
