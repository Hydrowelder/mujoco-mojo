from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorTorque"]


class SensorTorque(SensorBase):
    """"""

    tag = "torque"

    attributes = SensorBase.attributes + ()
