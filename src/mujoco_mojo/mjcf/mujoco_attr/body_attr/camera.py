from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.orientation import Orientation, Quat
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.typing import BodyName, CameraName, TrackingMode, Vec2, VecN

__all__ = ["Camera"]


class Camera(XMLModel):
    """This element creates a camera, which moves with the body where it is defined. To create a fixed camera, define it in the world body. The cameras created here are in addition to the default free camera which is always defined and is adjusted via the visual element. Internally MuJoCo uses a flexible camera model, where the viewpoint and projection surface are adjusted independently so as to obtain oblique projections needed for virtual environments. This functionality however is not accessible through MJCF. Instead, the cameras created with this element (as well as the free camera) have a viewpoint that is always centered in front of the projection surface. The viewpoint coincides with the center of the camera frame. The camera is looking along the -Z axis of its frame. The +X axis points to the right, and the +Y axis points up. Thus the frame position and orientation are the key adjustments that need to be made here."""

    tag = "camera"

    attributes = (
        "name",
        "class_",
        "orthographic",
        "fovy",
        "ipd",
        "resolution",
        "pos",
        "orientation",
        "mode",
        "target",
        "focal",
        "focalpixel",
        "principal",
        "principalpixel",
        "sensorsize",
        "user",
    )

    name: Optional[CameraName] = None
    """Name of the camera."""

    class_: Optional[str] = None
    """Defaults class for setting unspecified attributes."""

    mode: TrackingMode = TrackingMode.FIXED
    """This attribute specifies how the camera position and orientation in world coordinates are computed in forward kinematics (which in turn determine what the camera sees).

    * `fixed` means that the position and orientation specified below are fixed relative to the body where the camera is defined.
    * `track` means that the camera position is at a constant offset from the body in world coordinates, while the camera orientation is constant in world coordinates. These constants are determined by applying forward kinematics in qpos0 and treating the camera as fixed. Tracking can be used for example to position a camera above a body, point it down so it sees the body, and have it always remain above the body no matter how the body translates and rotates.
    * `trackcom` is similar to "track" but the constant spatial offset is defined relative to the center of mass of the kinematic subtree starting at the body in which the camera is defined. This can be used to keep an entire mechanism in view. Note that the subtree center of mass for the world body is the center of mass of the entire model. So if a camera is defined in the world body in mode "trackcom", it will track the entire model.
    * `targetbody` means that the camera position is fixed in the body frame, while the camera orientation is adjusted so that it always points towards the targeted body (which is specified with the target attribute below). This can be used for example to model an eye that fixates a moving object; the object will be the target, and the camera/eye will be defined in the body corresponding to the head.
    * `targetbodycom` is the same as "targetbody" but the camera is oriented towards the center of mass of the subtree starting at the target body."""

    target: Optional[BodyName] = None
    """When the camera mode is "targetbody" or "targetbodycom", this attribute becomes required. It specifies which body should be targeted by the camera. In all other modes this attribute is ignored."""

    orthographic: bool = False
    """Whether the camera uses a perspective projection (the default) or an orthographic projection. Setting this attribute changes the semantic of the fovy attribute, see below."""

    fovy: float = 45
    """Vertical field-of-view of the camera. If the camera uses a perspective projection, the field-of-view is expressed in degrees, regardless of the global compiler/angle setting. If the camera uses an orthographic projection, the field-of-view is expressed in units of length; note that in this case the default of 45 is too large for most scenes and should likely be reduced. In either case, the horizontal field of view is computed automatically given the window size and the vertical field of view."""

    resolution: Tuple[int, int] = (1, 1)
    """Resolution of the camera in pixels [width height]. Note that these values are not used for rendering since those dimensions are determined by the size of the rendering context. This attribute serves as a convenient location to save the required resolution when creating a context."""

    focal: Vec2 = np.array((0, 0))
    """Focal length of the camera in length units. It is mutually exclusive with fovy. See Cameras for details."""

    focalpixel: Tuple[int, int] = (1, 1)
    """Focal length of the camera in pixel units. If both focal and focalpixel are specified, the former is ignored."""

    principal: Vec2 = np.array((0, 0))
    """Offset of the principal point of the camera with respect to the camera center in length units. It is mutually exclusive with fovy."""

    principalpixel: Vec2 = np.array((0, 0))
    """Offset of the principal point of the camera with respect to the camera center in pixel units. If both principal and principalpixel are specified, the former is ignored."""

    sensorsize: Vec2 = np.array((0, 0))
    """Size of the camera sensor in length units. It is mutually exclusive with fovy. If specified, resolution and focal are required."""

    ipd: float = 0.068
    """Inter-pupilary distance. This attribute only has an effect during stereoscopic rendering. It specifies the distance between the left and right viewpoints. Each viewpoint is shifted by +/- half of the distance specified here, along the X axis of the camera frame."""

    pos: Pos = Pos(pos=np.array((0, 0, 0)))
    """Position of the camera frame."""

    orientation: Orientation = Quat()
    """Orientation of the camera frame. See Frame orientations. Note that specifically for cameras, the xyaxes attribute is semantically convenient as the X and Y axes correspond to the directions "right" and "up" in pixel space, respectively."""

    user: Optional[VecN] = None
    """See User parameters."""
