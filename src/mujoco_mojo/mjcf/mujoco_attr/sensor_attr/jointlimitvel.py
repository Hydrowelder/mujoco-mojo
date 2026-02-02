from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorJointlimitvel"]


class SensorJointlimitvel(SensorBase):
    """"""

    tag = "jointlimitvel"

    attributes = SensorBase.attributes + ()
