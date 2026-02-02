from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorActuatorpos"]


class SensorActuatorpos(SensorBase):
    """"""

    tag = "actuatorpos"

    attributes = SensorBase.attributes + ()
