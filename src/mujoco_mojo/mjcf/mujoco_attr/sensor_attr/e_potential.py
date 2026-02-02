from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorEPotential"]


class SensorEPotential(SensorBase):
    """"""

    tag = "e_potential"

    attributes = SensorBase.attributes + ()
