from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorEKinetic"]


class SensorEKinetic(SensorBase):
    """"""

    tag = "e_kinetic"

    attributes = SensorBase.attributes + ()
