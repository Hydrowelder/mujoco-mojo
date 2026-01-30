from __future__ import annotations

from typing import Optional, Sequence

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.asset_attr.material_attr.layer import Layer
from mujoco_mojo.types import Vec2, Vec4

__all__ = ["Material"]


class Material(XMLModel):
    """This element creates a material asset. It can be referenced from skins, geoms, sites and tendons to set their appearance. Note that all these elements also have a local rgba attribute, which is more convenient when only colors need to be adjusted, because it does not require creating materials and referencing them. Materials are useful for adjusting appearance properties beyond color. However once a material is created, it is more natural the specify the color using the material, so that all appearance properties are grouped together."""

    tag = "material"

    attributes = (
        "name",
        "class_",
        "texture",
        "texrepeat",
        "texuniform",
        "emission",
        "specular",
        "shininess",
        "reflectance",
        "metallic",
        "roughness",
        "rgba",
    )

    children = ("layers",)

    name: str
    """Name of the material, used for referencing."""

    class_: Optional[str] = None
    """Defaults class for setting unspecified attributes."""

    texture: Optional[str] = None
    """If this attribute is specified, the material has a texture associated with it. Referencing the material from a model element will cause the texture to be applied to that element. Note that the value of this attribute is the name of a texture asset, not a texture file name. Textures cannot be loaded in the material definition; instead they must be loaded explicitly via the texture element and then referenced here. The texture referenced here is used for specifying the RGB values. For advanced rendering (e.g., Physics-Based Rendering), more texture types need to be specified (e.g., roughness, metallic). In this case, this texture attribute should be omitted, and the texture types should be specified using layer child elements. Note however that the built-in renderer does not support PBR properties, so these advanced rendering features are only available when using an external renderer."""

    texrepeat: Optional[Vec2] = None
    """This attribute applies to textures of type "2d". It specifies how many times the texture image is repeated, relative to either the object size or the spatial unit, as determined by the next attribute."""

    texuniform: Optional[bool] = None
    """For cube textures, this attribute controls how cube mapping is applied. The default value "false" means apply cube mapping directly, using the actual size of the object. The value "true" maps the texture to a unit object before scaling it to its actual size (geometric primitives are created by the renderer as unit objects and then scaled). In some cases this leads to more uniform texture appearance, but in general, which settings produces better results depends on the texture and the object. For 2d textures, this attribute interacts with texrepeat above. Let texrepeat be N. The default value "false" means that the 2d texture is repeated N times over the (z-facing side of the) object. The value "true" means that the 2d texture is repeated N times over one spatial unit, regardless of object size."""

    emission: Optional[float] = None
    """Emission in OpenGL has the RGBA format, however we only provide a scalar setting. The RGB components of the OpenGL emission vector are the RGB components of the material color multiplied by the value specified here. The alpha component is 1."""

    specular: Optional[float] = None
    """Specularity in OpenGL has the RGBA format, however we only provide a scalar setting. The RGB components of the OpenGL specularity vector are all equal to the value specified here. The alpha component is 1. This value should be in the range [0 1]."""

    shininess: Optional[float] = None
    """Shininess in OpenGL is a number between 0 and 128. The value given here is multiplied by 128 before passing it to OpenGL, so it should be in the range [0 1]. Larger values correspond to tighter specular highlight (thus reducing the overall amount of highlight but making it more salient visually). This interacts with the specularity setting; see OpenGL documentation for details."""

    reflectance: Optional[float] = None
    """This attribute should be in the range [0 1]. If the value is greater than 0, and the material is applied to a plane or a box geom, the renderer will simulate reflectance. The larger the value, the stronger the reflectance. For boxes, only the face in the direction of the local +Z axis is reflective. Simulating reflectance properly requires ray-tracing which cannot (yet) be done in real-time. We are using the stencil buffer and suitable projections instead. Only the first reflective geom in the model is rendered as such. This adds one extra rendering pass through all geoms, in addition to the extra rendering pass added by each shadow-casting light."""

    metallic: Optional[float] = None
    """This attribute corresponds to uniform metallicity coefficient applied to the entire material. This attribute has no effect in MuJoCo's native renderer, but it can be useful when rendering scenes with a physically-based renderer. In this case, if a non-negative value is specified, this metallic value should be multiplied by the metallic texture sampled value to obtain the final metallicity of the material."""

    roughness: Optional[float] = None
    """This attribute corresponds to uniform roughness coefficient applied to the entire material. This attribute has no effect in MuJoCo's native renderer, but it can be useful when rendering scenes with a physically-based renderer. In this case, if a non-negative value is specified, this roughness value should be multiplied by the roughness texture sampled value to obtain the final roughness of the material."""

    rgba: Optional[Vec4] = None
    """Color and transparency of the material. All components should be in the range [0 1]. Note that the texture color (if assigned) and the color specified here are multiplied component-wise. Thus the default value of "1 1 1 1" has the effect of leaving the texture unchanged. When the material is applied to a model element which defines its own local rgba attribute, the local definition has precedence. Note that this "local" definition could in fact come from a defaults class. The remaining material properties always apply."""

    layers: Sequence[Layer] = Field(default_factory=list)
