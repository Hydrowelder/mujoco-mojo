from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorFramelinacc"]


class SensorFramelinacc(SensorBase):
    """"""

    tag = "framelinacc"

    attributes = SensorBase.attributes + ()
