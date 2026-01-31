from __future__ import annotations

from typing import Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.typing import LightType, TrackingMode, Vec3

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

    name: Optional[str] = None
    """Name of the light."""

    class_: Optional[str] = None
    """Defaults class for setting unspecified attributes."""

    mode: Optional[TrackingMode] = None
    """This is identical to the mode attribute of camera. It specifies the how the light position and orientation in world coordinates are computed in forward kinematics (which in turn determine what the light illuminates)."""

    target: Optional[str] = None
    """This is identical to the target attribute of camera above. It specifies which body should be targeted in "targetbody" and "targetbodycom" modes."""

    type: Optional[LightType] = None
    """Determines the type of light. Note that some light types may not be supported by some renderers (e.g. only spot and directional lights are supported by the default native renderer)."""

    directional: Optional[bool] = None
    """This is a deprecated legacy attribute. Please use light type instead. If set to "true", and no type is specified, this will change the light type to be directional."""

    castshadow: Optional[bool] = None
    """If this attribute is "true" the light will cast shadows. More precisely, the geoms illuminated by the light will cast shadows, however this is a property of lights rather than geoms. Since each shadow-casting light causes one extra rendering pass through all geoms, this attribute should be used with caution. Higher quality of the shadows is achieved by increasing the value of the shadowsize attribute of quality, as well as positioning spotlights closer to the surface on which shadows appear, and limiting the volume in which shadows are cast. For spotlights this volume is a cone, whose angle is the cutoff attribute below multiplied by the shadowscale attribute of map. For directional lights this volume is a box, whose half-sizes in the directions orthogonal to the light are the model extent multiplied by the shadowclip attribute of map. The model extent is computed by the compiler but can also be overridden by specifying the extent attribute of statistic. Internally the shadow-mapping mechanism renders the scene from the light viewpoint (as if it were a camera) into a depth texture, and then renders again from the camera viewpoint, using the depth texture to create shadows. The internal rendering pass uses the same near and far clipping planes as regular rendering, i.e., these clipping planes bound the cone or box shadow volume in the light direction. As a result, some shadows (especially those very close to the light) may be clipped."""

    active: Optional[bool] = None
    """The light is active if this attribute is "true". This can be used at runtime to turn lights on and off."""

    pos: Optional[Pos] = None
    """Position of the light. This attribute only affects the rendering for spotlights, but it should also be defined for directional lights because we render the cameras as decorative elements."""

    dir: Optional[Vec3] = None
    """Direction of the light."""

    diffuse: Optional[Vec3] = None
    """The color of the light. For the Phong (default) lighting model, this defines the diffuse color of the light."""

    texture: Optional[str] = None
    """The texture to use for image-based lighting. This is unused by the default Phong lighting model."""

    intensity: Optional[float] = None
    """The intensity of the light source, measured in candela, used for physically-based lighting models. This is unused by the default Phong lighting model."""

    ambient: Optional[Vec3] = None
    """The ambient color of the light, used by the default Phong lighting model."""

    specular: Optional[Vec3] = None
    """The specular color of the light, used by the default Phong lighting model."""

    range: Optional[float] = None
    """The effective range of the light. Objects further than this distance from the light position will not be illuminated by this light. This only applies to spotlights."""

    bulbradius: Optional[float] = None
    """The radius of the light source which can affect shadow softness depending on the renderer. This only applies to spotlights."""

    attenuation: Optional[Vec3] = None
    """These are the constant, linear and quadratic attenuation coefficients for Phong lighting. The default corresponds to no attenuation."""

    cutoff: Optional[float] = None
    """Cutoff angle for spotlights, always in degrees regardless of the global angle setting."""

    exponent: Optional[float] = None
    """Exponent for spotlights. This setting controls the softness of the spotlight cutoff."""
