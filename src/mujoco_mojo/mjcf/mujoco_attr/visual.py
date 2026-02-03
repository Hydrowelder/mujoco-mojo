from __future__ import annotations

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.visual_attr.global_ import VisualGlobal
from mujoco_mojo.mjcf.mujoco_attr.visual_attr.headlight import VisualHeadlight
from mujoco_mojo.mjcf.mujoco_attr.visual_attr.map import VisualMap
from mujoco_mojo.mjcf.mujoco_attr.visual_attr.quality import VisualQuality
from mujoco_mojo.mjcf.mujoco_attr.visual_attr.rgba import VisualRGBA
from mujoco_mojo.mjcf.mujoco_attr.visual_attr.scale import VisualScale

__all__ = ["Visual"]


class Visual(XMLModel):
    """
    This element is in one-to-one correspondence with the low level structure mjVisual contained in the field mjModel.vis of mjModel. The settings here affect the visualizer, or more precisely the abstract phase of visualization which yields a list of geometric entities for subsequent rendering. The settings here are global, in contrast with the element-specific visual settings. The global and element-specific settings refer to non-overlapping properties. Some of the global settings affect properties such as triangulation of geometric primitives that cannot be set per element. Other global settings affect the properties of decorative objects, i.e., objects such as contact points and force arrows which do not correspond to model elements. The visual settings are grouped semantically into several subsections.

    This element is a good candidate for the file include mechanism. One can create an XML file with coordinated visual settings corresponding to a "theme", and then include this file in multiple models.
    """

    tag = "visual"

    children = ("global_", "quality", "headlight", "map", "scale", "rgba")

    global_: VisualGlobal | None = None
    """Visual global grouping."""

    quality: VisualQuality | None = None
    """Visual quality grouping."""

    headlight: VisualHeadlight | None = None
    """Visual headlight grouping."""

    map: VisualMap | None = None
    """Visual map grouping."""

    scale: VisualScale | None = None
    """Visual scale grouping."""

    rgba: VisualRGBA | None = None
    """Visual rgba grouping."""
