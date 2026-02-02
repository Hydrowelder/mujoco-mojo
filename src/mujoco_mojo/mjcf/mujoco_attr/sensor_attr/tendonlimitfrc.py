from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import TendonName

__all__ = ["SensorTendonlimitfrc"]


class SensorTendonlimitfrc(SensorBase):
    """This element creates a tendon limit sensor for constraint force."""

    tag = "tendonlimitfrc"

    attributes = (
        *SensorBase.attributes,
        "tendon",
    )

    tendon: TendonName
    """The tendon whose limit is sensed. The sensor output is copied from mjData.efc_force. If the tendon limit is not violated, the result is 0."""
