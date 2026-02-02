from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import TendonName

__all__ = ["SensorTendonlimitpos"]


class SensorTendonlimitpos(SensorBase):
    """This element creates a tendon limit sensor for position."""

    tag = "tendonlimitpos"

    attributes = (*SensorBase.attributes, "tendon")

    tendon: TendonName
    """The tendon whose limit is sensed. The sensor output equals mjData.efc_pos - mjData.efc_margin for the corresponding limit constraint. If the tendon limit is not violated, the result is 0."""
