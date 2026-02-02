from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorJointactuatorfrc"]


class SensorJointactuatorfrc(SensorBase):
    """"""

    tag = "jointactuatorfrc"

    attributes = SensorBase.attributes + ()
