from __future__ import annotations

from typing import Optional

import numpy as np

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.typing import (
    BodyName,
    LightName,
    LightType,
    TextureName,
    TrackingMode,
    Vec3,
)

__all__ = ["Light"]


class Light(XMLModel):
    """This element creates a light, which moves with the body where it is defined. To create a fixed light, define it in the world body. The lights created here are in addition to the headlight which is always defined and is configured via the visual element. Lights shine along the direction specified by the dir attribute. They do not have a full spatial frame with three orthogonal axes.

    By default, MuJoCo uses the standard OpenGL (fixed functional) Phong lighting model for its rendering, with augmented with shadow mapping. (See the OpenGL documentation for more information, including details about various attributes.)

    MJCF also supports alternative lighting models (e.g. physically-based rendering) by providing additional attributes. Attributes may be applied or ignored depending on the lighting model being used."""

    tag = "light"

    attributes = (
        "name",
        "class_",
        "directional",
        "type",
        "castshadow",
        "active",
        "pos",
        "dir",
        "bulbradius",
        "intensity",
        "range",
        "attenuation",
        "cutoff",
        "exponent",
        "ambient",
        "diffuse",
        "specular",
        "mode",
        "target",
        "texture",
    )

    name: Optional[LightName] = None
    """Name of the light."""

    class_: Optional[str] = None
    """Defaults class for setting unspecified attributes."""

    mode: TrackingMode = TrackingMode.FIXED
    """This is identical to the mode attribute of camera. It specifies the how the light position and orientation in world coordinates are computed in forward kinematics (which in turn determine what the light illuminates)."""

    target: Optional[BodyName] = None
    """This is identical to the target attribute of camera above. It specifies which body should be targeted in "targetbody" and "targetbodycom" modes."""

    type: LightType = LightType.SPOT
    """Determines the type of light. Note that some light types may not be supported by some renderers (e.g. only spot and directional lights are supported by the default native renderer)."""

    directional: bool = False
    """This is a deprecated legacy attribute. Please use light type instead. If set to "true", and no type is specified, this will change the light type to be directional."""

    castshadow: bool = True
    """If this attribute is "true" the light will cast shadows. More precisely, the geoms illuminated by the light will cast shadows, however this is a property of lights rather than geoms. Since each shadow-casting light causes one extra rendering pass through all geoms, this attribute should be used with caution. Higher quality of the shadows is achieved by increasing the value of the shadowsize attribute of quality, as well as positioning spotlights closer to the surface on which shadows appear, and limiting the volume in which shadows are cast. For spotlights this volume is a cone, whose angle is the cutoff attribute below multiplied by the shadowscale attribute of map. For directional lights this volume is a box, whose half-sizes in the directions orthogonal to the light are the model extent multiplied by the shadowclip attribute of map. The model extent is computed by the compiler but can also be overridden by specifying the extent attribute of statistic. Internally the shadow-mapping mechanism renders the scene from the light viewpoint (as if it were a camera) into a depth texture, and then renders again from the camera viewpoint, using the depth texture to create shadows. The internal rendering pass uses the same near and far clipping planes as regular rendering, i.e., these clipping planes bound the cone or box shadow volume in the light direction. As a result, some shadows (especially those very close to the light) may be clipped."""

    active: bool = True
    """The light is active if this attribute is "true". This can be used at runtime to turn lights on and off."""

    pos: Pos = Pos(pos=np.array((0, 0, 0)))
    """Position of the light. This attribute only affects the rendering for spotlights, but it should also be defined for directional lights because we render the cameras as decorative elements."""

    dir: Vec3 = np.array((0, 0, -1))
    """Direction of the light."""

    diffuse: Vec3 = np.array((0.7, 0.7, 0.7))
    """The color of the light. For the Phong (default) lighting model, this defines the diffuse color of the light."""

    texture: Optional[TextureName] = None
    """The texture to use for image-based lighting. This is unused by the default Phong lighting model."""

    intensity: float = 0
    """The intensity of the light source, measured in candela, used for physically-based lighting models. This is unused by the default Phong lighting model."""

    ambient: Vec3 = np.array((0, 0, 0))
    """The ambient color of the light, used by the default Phong lighting model."""

    specular: Vec3 = np.array((0.3, 0.3, 0.3))
    """The specular color of the light, used by the default Phong lighting model."""

    range: float = 10
    """The effective range of the light. Objects further than this distance from the light position will not be illuminated by this light. This only applies to spotlights."""

    bulbradius: float = 0.02
    """The radius of the light source which can affect shadow softness depending on the renderer. This only applies to spotlights."""

    attenuation: Vec3 = np.array((1, 0, 0))
    """These are the constant, linear and quadratic attenuation coefficients for Phong lighting. The default corresponds to no attenuation."""

    cutoff: float = 45
    """Cutoff angle for spotlights, always in degrees regardless of the global angle setting."""

    exponent: float = 10
    """Exponent for spotlights. This setting controls the softness of the spotlight cutoff."""
