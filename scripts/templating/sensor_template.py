from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["Sensor${name_pascal}"]


class Sensor${name_pascal}(SensorBase):
    """"""

    tag = "${name_lower}"

    attributes = SensorBase.attributes + ()
