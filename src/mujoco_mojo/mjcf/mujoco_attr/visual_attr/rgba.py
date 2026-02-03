import numpy as np

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import Vec4

__all__ = ["VisualRGBA"]


class VisualRGBA(XMLModel):
    """
    The settings in this element control the color and transparency (rgba) of various decorative objects. We will call this combined attribute "color" to simplify terminology below. All values should be in the range [0 1]. An alpha value of 0 disables the rendering of the corresponding object.
    """

    tag = "rgba"

    attributes = (
        "fog",
        "haze",
        "force",
        "inertia",
        "joint",
        "actuator",
        "actuatornegative",
        "actuatorpositive",
        "com",
        "camera",
        "light",
        "selectpoint",
        "connect",
        "contactpoint",
        "contactforce",
        "contactfriction",
        "contacttorque",
        "contactgap",
        "rangefinder",
        "constraint",
        "slidercrank",
        "crankbroken",
        "frustum",
        "bv",
        "bvactive",
    )

    fog: Vec4 = np.array((0, 0, 0, 1))
    """When fog is enabled, the color of all pixels fades towards the color specified here. The spatial extent of the fading is controlled by the fogstart and fogend attributes of the map element above."""

    haze: Vec4 = np.array((1, 1, 1, 1))
    """Haze color at the horizon, used to transition between an infinite plane and a skybox smoothly. The default creates white haze. To create a seamless transition, make sure the skybox colors near the horizon are similar to the plane color/texture, and set the haze color somewhere in that color gamut."""

    force: Vec4 = np.array((1, 0.5, 0.5, 1))
    """Color of the arrows used to render perturbation forces."""

    inertia: Vec4 = np.array((0.8, 0.2, 0.2, 0.6))
    """Color of the boxes used to render equivalent body inertias. This is the only rgba setting that has transparency by default, because it is usually desirable to see the geoms inside the inertia box."""

    joint: Vec4 = np.array((0.2, 0.6, 0.8, 1))
    """Color of the arrows used to render joint axes. If a joint is limited and the joint value exceeds the limit, the value of the constraint impedance dd is used to mix this color and rgba/constraint."""

    actuator: Vec4 = np.array((0.2, 0.25, 0.2, 1))
    """Actuator color for neutral value of the control."""

    actuatornegative: Vec4 = np.array((0.2, 0.6, 0.9, 1))
    """Actuator color for most negative value of the control."""

    actuatorpositive: Vec4 = np.array((0.9, 0.4, 0.2, 1))
    """Actuator color for most positive value of the control."""

    com: Vec4 = np.array((0.9, 0.9, 0.9, 1))
    """Color of the spheres used to render sub-tree centers of mass."""

    camera: Vec4 = np.array((0.6, 0.9, 0.6, 1))
    """Color of the decorative object used to represent model cameras in the rendering."""

    light: Vec4 = np.array((0.6, 0.6, 0.9, 1))
    """Color of the decorative object used to represent model lights in the rendering."""

    selectpoint: Vec4 = np.array((0.9, 0.9, 0.1, 1))
    """Color of the sphere used to render the selection point."""

    connect: Vec4 = np.array((0.2, 0.2, 0.8, 1))
    """Color of the capsules used to connect bodies and joints, resulting in an automatically generated skeleton."""

    contactpoint: Vec4 = np.array((0.9, 0.6, 0.2, 1))
    """Color of the cylinders used to render contact points."""

    contactforce: Vec4 = np.array((0.7, 0.9, 0.9, 1))
    """Color of the arrows used to render contact forces. When splitting of contact forces into normal and tangential components is enabled, this color is used to render the normal components."""

    contactfriction: Vec4 = np.array((0.9, 0.8, 0.4, 1))
    """Color of the arrows used to render contact tangential forces, only when splitting is enabled."""

    contacttorque: Vec4 = np.array((0.9, 0.7, 0.9, 1))
    """Color of the arrows used to render contact torques (currently disabled)."""

    contactgap: Vec4 = np.array((0.5, 0.8, 0.9, 1))
    """Color of contacts that fall in the contact gap (and are thereby excluded from contact force computations)."""

    rangefinder: Vec4 = np.array((1, 1, 0.1, 1))
    """Color of line geoms used to render rangefinder sensors."""

    constraint: Vec4 = np.array((0.9, 0, 0, 1))
    """Color corresponding to spatial constraint violations - equality constraints, joint limits, and tendon limits."""

    slidercrank: Vec4 = np.array((0.5, 0.3, 0.8, 1))
    """Color of slider-crank mechanisms."""

    crankbroken: Vec4 = np.array((0.9, 0, 0, 1))
    """Color used to render the crank of slide-crank mechanisms, in model configurations where the specified rod length cannot be maintained, i.e., it is "broken"."""

    frustum: Vec4 = np.array((1, 1, 0, 0.2))
    """Color used to render the camera frustum."""

    bv: Vec4 = np.array((0, 1, 0, 0.5))
    """Color used to render bounding volumes."""

    bvactive: Vec4 = np.array((1, 0, 0, 0.5))
    """Color used to render active bounding volumes, if the bvactive flag is "true"."""
