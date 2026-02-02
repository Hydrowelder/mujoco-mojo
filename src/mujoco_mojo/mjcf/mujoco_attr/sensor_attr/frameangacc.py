from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorFrameangacc"]


class SensorFrameangacc(SensorBase):
    """"""

    tag = "frameangacc"

    attributes = SensorBase.attributes + ()
