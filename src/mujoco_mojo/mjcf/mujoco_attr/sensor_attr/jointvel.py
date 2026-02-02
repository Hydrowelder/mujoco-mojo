from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorJointvel"]


class SensorJointvel(SensorBase):
    """"""

    tag = "jointvel"

    attributes = SensorBase.attributes + ()
