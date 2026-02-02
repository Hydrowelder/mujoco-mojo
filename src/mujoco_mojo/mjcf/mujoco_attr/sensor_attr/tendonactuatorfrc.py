from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorTendonactuatorfrc"]


class SensorTendonactuatorfrc(SensorBase):
    """"""

    tag = "tendonactuatorfrc"

    attributes = SensorBase.attributes + ()
