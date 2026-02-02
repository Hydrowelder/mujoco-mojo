from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorSubtreelinvel"]


class SensorSubtreelinvel(SensorBase):
    """"""

    tag = "subtreelinvel"

    attributes = SensorBase.attributes + ()
