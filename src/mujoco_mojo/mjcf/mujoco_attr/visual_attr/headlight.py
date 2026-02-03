import numpy as np

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import Vec3

__all__ = ["VisualHeadlight"]


class VisualHeadlight(XMLModel):
    """
    This element is used to adjust the properties of the headlight. There is always a built-in headlight, in addition to any lights explicitly defined in the model. The headlight is a directional light centered at the current camera and pointed in the direction in which the camera is looking. It does not cast shadows (which would be invisible anyway). Note that lights are additive, so if explicit lights are defined in the model, the intensity of the headlight would normally need to be reduced.
    """

    tag = "headlight"

    attributes = ("ambient", "diffuse", "specular", "active")

    ambient: Vec3 = np.array((0.1, 0.1, 0.1))
    """The ambient component of the headlight, in the sense of OpenGL. The alpha component here and in the next two attributes is set to 1 and cannot be adjusted."""

    diffuse: Vec3 = np.array((0.4, 0.4, 0.4))
    """The diffuse component of the headlight, in the sense of OpenGL."""

    specular: Vec3 = np.array((0.5, 0.5, 0.5))
    """The specular component of the headlight, in the sense of OpenGL."""

    active: int = 1
    """This attribute enables and disables the headlight. A value of 0 means disabled, any other value means enabled."""
