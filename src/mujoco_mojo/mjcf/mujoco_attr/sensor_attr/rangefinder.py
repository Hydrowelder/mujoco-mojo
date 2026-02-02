from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorRangefinder"]


class SensorRangefinder(SensorBase):
    """"""

    tag = "rangefinder"

    attributes = SensorBase.attributes + ()
