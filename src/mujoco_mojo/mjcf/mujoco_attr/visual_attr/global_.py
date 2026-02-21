from pydantic import PositiveFloat

from mujoco_mojo.mjcf.xml_model import XMLModel

__all__ = ["VisualGlobal"]


class VisualGlobal(XMLModel):
    """
    While all settings in mjVisual are global, the settings here could not be fit into any of the other subsections. So this is effectively a miscellaneous subsection.
    """

    tag = "global"

    attributes = (
        "cameraid",
        "orthographic",
        "fovy",
        "ipd",
        "azimuth",
        "elevation",
        "linewidth",
        "glow",
        "realtime",
        "offwidth",
        "offheight",
        "ellipsoidinertia",
        "bvactive",
    )

    cameraid: int = -1
    """The id of the camera used when initially loading the model in the visualizer. The default value of -1 means the free camera. In order to specify a modeled camera, use the camera's id as given by mj_name2id."""

    orthographic: bool = False
    """Whether the free camera uses a perspective projection (the default) or an orthographic projection. Setting this attribute changes the semantic of the global/fovy attribute, see below."""

    fovy: float = 45.0
    """This attribute specifies the vertical field of view of the free camera, i.e., the camera that is always available in the visualizer even if no cameras are explicitly defined in the model. If the camera uses a perspective projection, the field-of-view is expressed in degrees, regardless of the global compiler/angle setting. If the camera uses an orthographic projection, the field-of-view is expressed in units of length; note that in this case the default of 45 is too large for most scenes and should likely be reduced. In either case, the horizontal field of view is computed automatically given the window size and the vertical field of view. The same convention applies to the camera/fovy attribute."""

    ipd: float = 0.068
    """This attribute specifies the inter-pupilary distance of the free camera. It only affects the rendering in stereoscopic mode. The left and right viewpoints are offset by half of this value in the corresponding direction."""

    azimuth: float = 90.0
    """This attribute specifies the initial azimuth of the free camera around the vertical z-axis, in degrees. A value of 0 corresponds to looking in the positive x direction, while the default value of 90 corresponds to looking in the positive y direction. The look-at point itself is specified by the statistic/center attribute, while the distance from the look-at point is controlled by the statistic/extent attribute."""

    elevation: float = -45.0
    """This attribute specifies the initial elevation of the free camera with respect to the lookat point. Note that since this is a rotation around a vector parallel to the camera's X-axis (right in pixel space), negative numbers correspond to moving the camera up from the horizontal plane, and vice-versa. The look-at point itself is specified by the statistic/center attribute, while the distance from the look-at point is controlled by the statistic/extent attribute."""

    linewidth: float = 1.0
    """This attribute specifies the line-width in the sense of OpenGL. It affects the rendering in wire-frame mode."""

    glow: float = 0.3
    """The value of this attribute is added to the emission coefficient of all geoms attached to the selected body. As a result, the selected body appears to glow."""

    realtime: PositiveFloat = 1.0
    """This value sets the initial real-time factor of the model, when loaded in simulate. 1: real time. Less than 1: slower than real time. Must be greater than 0."""

    offwidth: int = 640
    """This and the next attribute specify the size in pixels of the off-screen OpenGL rendering buffer. This attribute specifies the width of the buffer. The size of this buffer can also be adjusted at runtime, but it is usually more convenient to set it in the XML."""

    offheight: int = 480
    """This attribute specifies the height in pixels of the OpenGL off-screen rendering buffer."""

    ellipsoidinertia: bool = False
    """This attribute specifies how the equivalent inertia is visualized. "false": use box, "true": use ellipsoid."""

    bvactive: bool = True
    """This attribute specifies whether collision and raycasting code should mark elements of Bounding Volume Hierarchies as intersecting, for the purpose of visualization. Setting this attribute to "false" can speed up simulation for models with high-resolution meshes."""
