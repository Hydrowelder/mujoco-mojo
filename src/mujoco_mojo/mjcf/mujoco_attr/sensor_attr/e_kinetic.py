from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorEKinetic"]


class SensorEKinetic(SensorBase):
    """This element creates sensor that returns the kinetic energy."""

    tag = "e_kinetic"

    attributes = (*SensorBase.attributes,)
