from __future__ import annotations

from typing import ClassVar

import mujoco
from pydantic import Field

from mujoco_mojo.mjcf.pose import Pose, PoseQuat
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import FrameName
from mujoco_mojo.utils.utils import is_empty_list

__all__ = ["Frame"]


class Frame(XMLModel):
    """
    Frames specify a coordinate transformation which is applied to all child elements. They disappear during compilation and the transformation they encode is accumulated in their direct children. See frame for examples.

    The frame meta-element is a pure coordinate transformation that can wrap any group of elements in the kinematic tree (under worldbody). After compilation, frame elements disappear and their transformation is accumulated in their direct children.

    ???+ example "Example Usage of Frame"

        Compiling this model:
        ```xml hl_lines="3 5 7 12"
        <mujoco>
            <worldbody>
                <frame quat="0 0 1 0">
                    <geom name="Alice" quat="0 1 0 0" size="1"/>
                </frame>

                <frame pos="0 1 0">
                    <geom name="Bob" pos="0 1 0" size="1"/>
                    <body name="Carl" pos="1 0 0">
                        ...
                    </body>
                </frame>
            </worldbody>
        </mujoco>
        ```

        Results in this model:
        ```xml
        <mujoco>
            <worldbody>
                <geom name="Alice" quat="0 0 0 1" size="1"/>
                <geom name="Bob" pos="0 2 0" size="1"/>
                <body name="Carl" pos="1 1 0">
                    ...
                </body>
            </worldbody>
        </mujoco>
        ```

        Note that in the compiled model, the frame elements have disappeared but their transformation was accumulated with those of their child elements in the resulting model.
    """

    tag = "frame"

    attributes = ("name", "childclass", "pose")
    children = ("frames",)

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_FRAME

    name: FrameName | None = None
    """Name of the frame."""

    childclass: str | None = None
    """If this attribute is present, all descendant elements that admit a defaults class will use the class specified here, unless they specify their own class or another frame or body with a childclass attribute is encountered along the chain of nested bodies and frames. Recall Default settings."""

    pose: Pose = PoseQuat()
    """The 3D position and orientation of the frame, in the parent coordinate system."""

    frames: list[Frame] = Field(default_factory=list, exclude_if=is_empty_list)
    """Frames assigned to Frame."""
