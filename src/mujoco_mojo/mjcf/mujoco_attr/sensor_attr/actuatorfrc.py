from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorActuatorfrc"]


class SensorActuatorfrc(SensorBase):
    """"""

    tag = "actuatorfrc"

    attributes = SensorBase.attributes + ()
