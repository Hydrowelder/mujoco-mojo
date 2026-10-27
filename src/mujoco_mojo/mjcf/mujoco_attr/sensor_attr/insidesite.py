from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import SensorAttachableName, SensorObjectType, SiteName
from mujoco_mojo.utils.signal_metadata import ColumnMetadata

__all__ = ["SensorInsidesite"]

_FLAG_LABELS = ColumnMetadata(enumeration_map={"OUTSIDE": 0, "INSIDE": 1})


class SensorInsidesite(SensorBase):
    """This element creates a sensor that returns 1 if the given object is inside a site, 0 otherwise. It is useful for triggering events in surrounding environment logic. See example model."""

    tag = "insidesite"

    attributes = (
        *SensorBase.attributes,
        "objtype",
        "objname",
        "site",
        "enclosed",
    )

    objtype: SensorObjectType
    """The type of the object to be queried. When enclosed is "false", this specifies the coordinate frame whose origin is checked (see framepos). When enclosed is "true", body checks all geoms directly attached to the body, xbody checks all geoms in the kinematic subtree rooted at the body, and camera is not supported."""

    objname: SensorAttachableName
    """The name of the object to be queried. See framepos."""

    site: SiteName
    """The site defining the volume used for the inside check."""

    enclosed: bool = False
    """If true, checks full geometric enclosure instead of only checking whether the frame origin is inside the site. The sensor measures how much the object juts out of the site (the directed Hausdorff distance): positive values indicate how far the furthest point protrudes outside the site boundary, while zero or negative values indicate the object is fully enclosed (with the magnitude representing clearance to the boundary). Both the site and all queried geoms/sites must be compact convex shapes. For `objtype="body"` or `objtype="xbody"`, the sensor returns the maximum value across all geoms on the body or in its kinematic subtree, respectively (at least one geom must be present)."""

    def _resolve_builtin_metadata(self, state: MjState) -> ColumnMetadata | None:
        builtin = super()._resolve_builtin_metadata(state)
        # with `enclosed` the sensor reports how far the object juts out of the site, a distance rather than a flag, so only the flag is labeled
        if self.enclosed or builtin is None:
            return builtin
        return builtin | _FLAG_LABELS
