from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorJointlimitfrc"]


class SensorJointlimitfrc(SensorBase):
    """"""

    tag = "jointlimitfrc"

    attributes = SensorBase.attributes + ()
