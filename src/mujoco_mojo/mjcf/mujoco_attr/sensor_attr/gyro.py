from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase

__all__ = ["SensorGyro"]


class SensorGyro(SensorBase):
    """"""

    tag = "gyro"

    attributes = SensorBase.attributes + ()
