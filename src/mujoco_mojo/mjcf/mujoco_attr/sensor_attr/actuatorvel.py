from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorActuatorvel"]


class SensorActuatorvel(SensorBase):
    """"""

    tag = "actuatorvel"

    attributes = SensorBase.attributes + ()
