from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorTendonlimitfrc"]


class SensorTendonlimitfrc(SensorBase):
    """"""

    tag = "tendonlimitfrc"

    attributes = SensorBase.attributes + ()
