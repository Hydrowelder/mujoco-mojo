from mujoco_mojo.mjcf.xml_model import XMLModel

__all__ = ["VisualScale"]


class VisualScale(XMLModel):
    """
    The settings in this element control the spatial extent of various decorative objects. In all cases, the rendered size equals the mean body size (see statistic element) multiplied by the value of an attribute documented below.
    """

    tag = "scale"

    attributes = (
        "forcewidth",
        "contactwidth",
        "contactheight",
        "connect",
        "com",
        "camera",
        "light",
        "selectpoint",
        "jointlength",
        "jointwidth",
        "actuatorlength",
        "actuatorwidth",
        "framelength",
        "framewidth",
        "constraint",
        "slidercrank",
        "frustum",
    )

    forcewidth: float = 0.1
    """The radius of the arrows used to render contact forces and perturbation forces."""

    contactwidth: float = 0.3
    """The radius of the cylinders used to render contact points. The normal direction of the cylinder is aligned with the contact normal. Making the cylinder short and wide results in a "pancake" representation of the tangent plane."""

    contactheight: float = 0.1
    """The height of the cylinders used to render contact points."""

    connect: float = 0.2
    """The radius of the capsules used to connect bodies and joints, resulting in an automatically generated skeleton."""

    com: float = 0.4
    """The radius of the spheres used to render the centers of mass of kinematic sub-trees."""

    camera: float = 0.3
    """The size of the decorative object used to represent model cameras in the rendering."""

    light: float = 0.3
    """The size of the decorative object used to represent model lights in the rendering."""

    selectpoint: float = 0.2
    """The radius of the sphere used to render the selection point (i.e., the point where the user left-double-clicked to select a body). Note that the local and global coordinates of this point can be printed in the 3D view by activating the corresponding rendering flags. In this way, the coordinates of points of interest can be found."""

    jointlength: float = 1.0
    """The length of the arrows used to render joint axes."""

    jointwidth: float = 0.1
    """The radius of the arrows used to render joint axes."""

    actuatorlength: float = 0.7
    """The length of the arrows used to render actuators acting on scalar joints only."""

    actuatorwidth: float = 0.2
    """The radius of the arrows used to render actuators acting on scalar joints only."""

    framelength: float = 1.0
    """The length of the cylinders used to render coordinate frames. The world frame is automatically scaled relative to this setting."""

    framewidth: float = 0.1
    """The radius of the cylinders used to render coordinate frames."""

    constraint: float = 0.1
    """The radius of the capsules used to render violations in spatial constraints."""

    slidercrank: float = 0.2
    """The radius of the capsules used to render slider-crank mechanisms. The second part of the mechanism is automatically scaled relative to this setting."""

    frustum: float = 10
    """The distance of the zfar plane from the camera pinhole for rendering the frustum."""
