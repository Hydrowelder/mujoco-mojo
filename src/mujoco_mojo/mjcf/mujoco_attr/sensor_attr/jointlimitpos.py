from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorJointlimitpos"]


class SensorJointlimitpos(SensorBase):
    """"""

    tag = "jointlimitpos"

    attributes = SensorBase.attributes + ()
