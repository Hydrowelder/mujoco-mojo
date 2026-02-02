from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import TendonName

__all__ = ["SensorTendonvel"]


class SensorTendonvel(SensorBase):
    """This element creates a tendon velocity sensor. It can be attached to both spatial and fixed tendons. Its output is scalar."""

    tag = "tendonvel"

    attributes = (
        *SensorBase.attributes,
        "tendon",
    )

    tendon: TendonName
    """The tendon whose velocity will be sensed. The sensor output is copied from mjData.ten_velocity."""
