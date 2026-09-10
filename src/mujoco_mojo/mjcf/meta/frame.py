from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import mujoco
from pydantic import Field

from mujoco_mojo.mjcf.plugin import Plugin
from mujoco_mojo.mjcf.pose import AnyPose, PoseQuat
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import FrameName
from mujoco_mojo.utils.utils import is_empty_list

if TYPE_CHECKING:
    # these are only needed for field type annotations. Importing any of them for
    # real (outside TYPE_CHECKING) would be circular: they live under `mujoco_attr`,
    # whose package __init__ imports body.py, which imports this module. Deferred
    # here, `Frame.model_rebuild()` in body.py resolves them once they all exist.
    from mujoco_mojo.mjcf.mujoco_attr.body import Body
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.attach import Attach
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.camera import Camera
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.composite import Composite
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.flexcomp import FlexComp
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.free_joint import FreeJoint
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import AnyGeom
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.inertial import Inertial
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.joint import Joint
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.light import Light
    from mujoco_mojo.mjcf.mujoco_attr.body_attr.site import AnySite

__all__ = ["Frame"]

_frame_children = (
    "inertial",
    "joints",
    "freejoints",
    "geoms",
    "sites",
    "cameras",
    "lights",
    "composites",
    "flexcomps",
    "plugins",
    "attaches",
    "frames",
    "bodies",
)


class Frame(XMLModel):
    """
    Frames specify a coordinate transformation which is applied to all child elements. They disappear during compilation and the transformation they encode is accumulated in their direct children. See frame for examples.

    The frame meta-element is a pure coordinate transformation that can wrap any group of elements in the kinematic tree (under worldbody). After compilation, frame elements disappear and their transformation is accumulated in their direct children.

    A frame accepts the same child elements a `Body` would at the position it's nested in: `geoms`, `sites`, `cameras`, `lights`, `bodies`, `composites`, `flexcomps`, `plugins`, `attaches`, and nested `frames` are always valid; `joints`, `freejoints`, and `inertial` are only valid when the frame itself sits inside a real `Body` (a joint/inertial always belongs to that enclosing body, since a frame has no dynamical identity of its own) - MuJoCo's compiler rejects them when the frame is a direct child of `worldbody`, the same as it would a bare joint there.

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
    children = _frame_children

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_FRAME

    name: FrameName | None = None
    """Name of the frame."""

    childclass: str | None = None
    """If this attribute is present, all descendant elements that admit a defaults class will use the class specified here, unless they specify their own class or another frame or body with a childclass attribute is encountered along the chain of nested bodies and frames. Recall Default settings."""

    pose: AnyPose = PoseQuat()
    """The 3D position and orientation of the frame, in the parent coordinate system."""

    inertial: Inertial | None = None
    """Inertial assigned to this frame. Only valid when the frame is nested inside a body; the inertial properties end up belonging to that enclosing body, since a frame has no body identity of its own."""

    joints: list[Joint] = Field(default_factory=list, exclude_if=is_empty_list)
    """Joints wrapped by this frame. Only valid when the frame is nested inside a body; the joints end up belonging to that enclosing body."""

    freejoints: list[FreeJoint] = Field(default_factory=list, exclude_if=is_empty_list)
    """Free joints wrapped by this frame. Subject to the same body-only restriction as `joints`."""

    geoms: list[AnyGeom] = Field(default_factory=list, exclude_if=is_empty_list)
    """Geometries wrapped by this frame."""

    sites: list[AnySite] = Field(default_factory=list, exclude_if=is_empty_list)
    """Sites wrapped by this frame."""

    cameras: list[Camera] = Field(default_factory=list, exclude_if=is_empty_list)
    """Cameras wrapped by this frame."""

    lights: list[Light] = Field(default_factory=list, exclude_if=is_empty_list)
    """Lights wrapped by this frame."""

    composites: list[Composite] = Field(default_factory=list, exclude_if=is_empty_list)
    """Composites wrapped by this frame."""

    flexcomps: list[FlexComp] = Field(default_factory=list, exclude_if=is_empty_list)
    """Flexible composites wrapped by this frame."""

    plugins: list[Plugin] = Field(default_factory=list, exclude_if=is_empty_list)
    """Plugins wrapped by this frame."""

    attaches: list[Attach] = Field(default_factory=list, exclude_if=is_empty_list)
    """Attach elements wrapped by this frame."""

    frames: list[Frame] = Field(default_factory=list, exclude_if=is_empty_list)
    """Frames nested inside this frame."""

    bodies: list[Body] = Field(default_factory=list, exclude_if=is_empty_list)
    """Bodies wrapped by this frame, positioned by the frame's pose transform without needing a dummy parent body."""

    def walk_bodies(self) -> list[Body]:
        """Recursively collects every body wrapped by this frame, including through nested frames."""
        bodies: list[Body] = []
        for body in self.bodies:
            bodies.extend(body.walk_bodies(include_self=True))
        for frm in self.frames:
            bodies.extend(frm.walk_bodies())
        return bodies
