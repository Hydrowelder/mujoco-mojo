from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorTendonpos"]


class SensorTendonpos(SensorBase):
    """"""

    tag = "tendonpos"

    attributes = SensorBase.attributes + ()
