from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorFramelinvel"]


class SensorFramelinvel(SensorBase):
    """"""

    tag = "framelinvel"

    attributes = SensorBase.attributes + ()
