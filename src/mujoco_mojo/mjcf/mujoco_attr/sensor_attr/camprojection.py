from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import CameraName, SiteName

__all__ = ["SensorCamprojection"]


class SensorCamprojection(SensorBase):
    """This element creates a camera projection sensor: the location of a target site, projected onto a camera image in pixel coordinates. The pixel origin (0, 0) is located at the top-left corner. Values are not clipped, so targets which fall outside the camera image will take values above or below the pixel range limits. Moreover, points behind the camera are also projected onto the image, so it is up to the user to filter out such points, if desired. This can be done using a framepos sensor with the camera as a reference frame: a negative/positive value in the z-coordinate indicates a location in front of/behind the camera plane, respectively."""

    tag = "camprojection"

    attributes = (*SensorBase.attributes, "site", "camera")

    site: SiteName
    """The site where the sensor is attached."""

    camera: CameraName
    """The camera used for the projection, its resolution attribute must be positive."""
