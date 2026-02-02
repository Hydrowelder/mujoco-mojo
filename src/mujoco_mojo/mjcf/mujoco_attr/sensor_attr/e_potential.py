from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorEPotential"]


class SensorEPotential(SensorBase):
    """This element creates sensor that returns the potential energy."""

    tag = "e_potential"

    attributes = (*SensorBase.attributes,)
