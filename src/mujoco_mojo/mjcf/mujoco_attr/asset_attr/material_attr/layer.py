from __future__ import annotations

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import LayerRole, TextureName

__all__ = ["Layer"]


class Layer(XMLModel):
    """If multiple textures are needed to specify the appearance of a material, the texture attribute cannot be used, and layer child elements must be used instead. Specifying both the texture attribute and layer child elements is an error."""

    tag = "layer"

    attributes = (
        "texture",
        "role",
    )

    texture: TextureName
    """Name of the texture, like the texture attribute."""

    role: LayerRole
    """Role of the texture. The valid values, expected number of channels, and the role semantics are:

    | value     | channels | description                                                  |
    |:----------|:---------|:-------------------------------------------------------------|
    | rgb       | 3        | base color / albedo [red, green, blue]                       |
    | normal    | 3        | bump map (surface normals)                                   |
    | occlusion | 1        | ambient occlusion                                            |
    | roughness | 1        | roughness                                                    |
    | metallic  | 1        | metallicity                                                  |
    | opacity   | 1        | opacity (alpha channel)                                      |
    | emissive  | 4        | RGB light emmision intensity, exposure weight in 4th channel |
    | orm       | 3        | packed 3 channel [occlusion, roughness, metallic]            |
    | rgba      | 4        | packed 4 channel [red, green, blue, alpha]                   |
    """
