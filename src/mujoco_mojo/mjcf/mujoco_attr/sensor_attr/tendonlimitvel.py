from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorTendonlimitvel"]


class SensorTendonlimitvel(SensorBase):
    """"""

    tag = "tendonlimitvel"

    attributes = SensorBase.attributes + ()
