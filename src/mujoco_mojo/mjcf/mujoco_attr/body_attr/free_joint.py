from __future__ import annotations

from typing import ClassVar, Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import Align, JointType

__all__ = ["FreeJoint"]


class FreeJoint(XMLModel):
    """This element creates a free joint whose only attributes are name and group. The freejoint element is an XML shortcut for

    ``` xml
    <joint type="free" stiffness="0" damping="0" frictionloss="0" armature="0"/>
    ```

    While this joint can evidently be created with the joint element, default joint settings could affect it. This is usually undesirable as physical free bodies do not have nonzero stiffness, damping, friction or armature. To avoid this complication, the freejoint element was introduced, ensuring joint defaults are not inherited. If the XML model is saved, it will appear as a regular joint of type free."""

    tag = "joint"
    type: ClassVar[JointType] = JointType.FREE

    name: Optional[str] = None
    """Name of the joint."""

    group: Optional[int] = None
    """Integer group to which the joint belongs. This attribute can be used for custom tags. It is also used by the visualizer to enable and disable the rendering of entire groups of joints."""

    align: Optional[Align] = None
    """When set to true, the body frame and free joint will automatically be aligned with inertial frame. When set to false, no alignment will occur. When set to auto, the compiler's alignfree global attribute will be respected.

    Inertial frame alignment is an optimization only applies to bodies with a free joint and no child bodies ("simple free bodies"). The alignment diagonalizes the 6x6 inertia matrix and minimizes bias forces, leading to faster and more stable simulation. While this behaviour is a strict improvement, it modifies the semantics of the free joint, making qpos and qvel values saved in older versions (for example, in keyframes) invalid.

    Note that the align attribute is never saved to XML. Instead, the pose of simple free bodies and their children will be modified such that the body frame and inertial frame are aligned."""
