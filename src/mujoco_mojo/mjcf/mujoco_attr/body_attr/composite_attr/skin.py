from typing import Optional

import numpy as np

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import MaterialName, Vec4


class Skin(XMLModel):
    """If this element is included, the model compiler will generate a skinned mesh asset and attach it to the element bodies of the composite object. Skin can be attached to 2D grid, cloth, box, cylinder and ellipsoid. For other composite types it has no effect. Note that the skin created here is equivalent to a skin specified directly in the XML, as opposed to a skin loaded from file. So if the model is saved as XML, it will contain a large section describing the automatically-generated skin."""

    texcoord: bool = False
    """If this is true, explicit texture coordinates will be generated, mapping the skin to the unit square in texture space. This is needed when the material specifies a texture. If texcoord is false and the skin has texture, the texture will appear fixed to the world instead of the skin. The reason for having this attribute in the first place is because skins with texture coordinates upload these coordinates to the GPU even if no texture is applied later. So this attribute should be set to false in cases where no texture will be applied via the material attribute."""

    material: Optional[MaterialName] = None
    """If specified, this attribute applies a material to the geom. Otherwise, if unspecified and the type of the geom is a mesh the compiler will apply the mesh asset material if present.

    The material determines the visual properties of the geom. The only exception is color: if the rgba attribute below is different from its internal default, it takes precedence while the remaining material properties are still applied. Note that if the same material is referenced from multiple geoms (as well as sites and tendons) and the user changes some of its properties at runtime, these changes will take effect immediately for all model elements referencing the material. This is because the compiler saves the material and its properties as a separate element in mjModel, and the elements using this material only keep a reference to it."""

    rgba: Vec4 = np.array((0.5, 0.5, 0.5, 1))
    """Instead of creating material assets and referencing them, this attribute can be used to set color and transparency only. This is not as flexible as the material mechanism, but is more convenient and is often sufficient. If the value of this attribute is different from the internal default, it takes precedence over the material."""

    group: int = 0
    """This attribute specifies an integer group to which the geom belongs. The only effect on the physics is at compile time, when body masses and inertias are inferred from geoms selected based on their group; see inertiagrouprange attribute of compiler. At runtime this attribute is used by the visualizer to enable and disable the rendering of entire geom groups. By default, groups 0, 1 and 2 are visible, while all other groups are invisible. The group attribute can also be used as a tag for custom computations."""

    inflate: float = 0
    """The default value of 0 means that the automatically-generated skin passes through the centers of the body elements comprising the composite object. Positive values offset each skin vertex by the specified amount, in the direction normal to the (non-inflated) skin at that vertex. This has two uses. First, in 2D objects, a small positive inflate factor is needed to avoid aliasing artifacts. Second, collisions are done with geoms that create some thickness, even for 2D objects. Inflating the skin with a value equal to the geom size will render the skin as a "mattress" that better represents the actual collision geometry. The value of this attribute is copied into the corresponding attribute of the skin asset being created."""

    subgrid: int = 0
    """This is only applicable to cloth and 2D grid types, and has no effect for any other composite type. The default value of 0 means that the skin has as many vertices as the number of element bodies. A positive value causes subdivision, with the specified number of (additional) grid lines. In this case the model compiler generates a denser skin using bi-cubic interpolation. This increases the quality of the rendering (especially in the absence of textures) but also slows down the renderer, so use it with caution. Values above 3 are unlikely to be needed."""
