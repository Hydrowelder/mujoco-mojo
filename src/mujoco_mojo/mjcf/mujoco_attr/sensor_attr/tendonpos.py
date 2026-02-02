from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import TendonName

__all__ = ["SensorTendonpos"]


class SensorTendonpos(SensorBase):
    """This element creates a tendon length sensor. It can be attached to both spatial and fixed tendons. Its output is scalar."""

    tag = "tendonpos"

    attributes = (
        *SensorBase.attributes,
        "tendon",
    )

    tendon: TendonName
    """The tendon whose length will be sensed. The sensor output is copied from mjData.ten_length."""
