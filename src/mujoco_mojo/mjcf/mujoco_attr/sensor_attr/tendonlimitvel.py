from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import TendonName

__all__ = ["SensorTendonlimitvel"]


class SensorTendonlimitvel(SensorBase):
    """This element creates a tendon limit sensor for velocity."""

    tag = "tendonlimitvel"

    attributes = (
        *SensorBase.attributes,
        "tendon",
    )

    tendon: TendonName
    """The tendon whose limit is sensed. The sensor output is copied from mjData.efc_vel. If the tendon limit is not violated, the result is 0."""
