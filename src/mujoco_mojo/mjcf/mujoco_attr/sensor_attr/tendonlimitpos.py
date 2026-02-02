from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorTendonlimitpos"]


class SensorTendonlimitpos(SensorBase):
    """"""

    tag = "tendonlimitpos"

    attributes = SensorBase.attributes + ()
