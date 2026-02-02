from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorVelocimeter"]


class SensorVelocimeter(SensorBase):
    """"""

    tag = "velocimeter"

    attributes = SensorBase.attributes + ()
