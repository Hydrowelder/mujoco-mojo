from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

import mujoco
import numpy as np
from pydantic import Field, field_validator, model_validator

from mujoco_mojo.mjcf.plugin import Plugin
from mujoco_mojo.mjcf.pose import AnyPose, PoseQuat
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import FrameName, FrameScaling, Vec3
from mujoco_mojo.utils.log import get_logger
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

logger = get_logger(__name__)

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
    Frames specify a coordinate transformation which is applied to all child elements. During compilation the transformation they encode is accumulated in their direct children; frames are preserved when the model is saved.

    The frame meta-element is a pure coordinate transformation that can wrap any group of elements in the kinematic tree (under worldbody). At compile time the transformation is accumulated into the frame's direct children; frames have no counterpart in mjModel. Unlike the other meta-elements, frames are preserved when the model is saved: the frame is written with its pose and its contents in frame-relative coordinates, so a saved model reloads with the same frames. The attributes of the frame meta-element are documented below.
    """

    tag = "frame"

    attributes = (
        "name",
        "childclass",
        "pose",
        "scale",
        "scaling",
        "massscale",
    )
    children = _frame_children

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_FRAME

    name: FrameName | None = None
    """Name of the frame."""

    childclass: str | None = None
    """If this attribute is present, all descendant elements that admit a defaults class will use the class specified here, unless they specify their own class or another frame or body with a childclass attribute is encountered along the chain of nested bodies and frames. Recall Default settings."""

    pose: AnyPose = PoseQuat()
    """The 3D position and orientation of the frame, in the parent coordinate system."""

    scale: Vec3 | float = np.array((1, 1, 1))
    """Resizes everything inside the frame. Bodies, geoms, sites, joints and all other contents are scaled about the frame's origin, while the frame's own pos and orientation, which are in its parent's coordinates, are not. Scaling happens at compile time: the spec keeps the authored values, so changing the scale and recompiling starts again from them, and a model saved as written keeps the attribute.

    Three attributes work together. scale sets the factor `s` of lengths, massscale the factor `m` of masses, by default `s^3` (the same material), and scaling decides whether forces, stiffnesses and actuator gains follow (similar, the default) or keep their authored values (geometry). Typical uses:

    | intent                                                                          | attributes                                   |
    |:--------------------------------------------------------------------------------|:---------------------------------------------|
    | a copy which moves like the original, in proportionally scaled gravity          | `scale="s"`                                  |
    | a larger or smaller body of the same material, with the same motors and springs | `scale="s" scaling="geometry"`               |
    | a larger or smaller body of the same mass                                       | `scale="s" scaling="geometry" massscale="1"` |
    | a heavier or lighter body of the same size, e.g. a payload                      | `massscale="k" scaling="geometry"`           |
    | a change of the units of length and mass                                        | `scale="s" massscale="k"`                    |
    | a body stretched along the frame's axes, see below                              | `scale="sx sy sz" scaling="geometry"`        |

    Scales of nested frames compose by multiplication. A single value applies to all three axes. Values must be finite and positive.

    Three different values stretch the contents along the frame's axes, which requires scaling "geometry". Positions are mapped exactly and orientations are kept, so each shape inside is stretched in its own coordinates, which only some shapes can represent:

    - meshes always, with an instance of the mesh for each distinct stretch;
    - boxes, ellipsoids, planes and height fields aligned with the frame's axes;
    - capsules and cylinders aligned with the frame's axes and stretched equally across their own axis. The caps of a capsule stay hemispherical: with aa the factor across its axis and cc the factor along it, its radius rr becomes arar and its half-length hh becomes chch, so that its total length is `2(ch+ar)` rather than `2c(h+r)`;
    - spheres only when scaled uniformly; use an ellipsoid otherwise.

    Hinge and slide joints must also be aligned with the frame's axes. Anything else is a compile error; alignment is checked to within about 2 degrees. Sites are never an error: a site box, ellipsoid, capsule or cylinder is stretched by the factor along each of its own axes, with the radius of a capsule or cylinder taking the geometric mean of the two factors across it, which is approximate when the site is not aligned. Explicit inertias transform exactly. Sphere sites, and lengths without a direction like margins, contact widths and tendon widths, take the geometric mean of the three factors.

    A mesh or height field used at several scales compiles to an instance per scale; the first keeps its name and the others are named `name@1`, `name@2`, ... A model saved compiled writes a mesh instance which is not stretched along its own axes as vertices and faces; its texture coordinates are kept only if they are given per vertex, and its normals are recomputed. The bones of a skin must have the same scale, and elements with plugins and tactile sensors cannot be scaled.

    Pose resolution (`Mujoco.local_pose`) does not support elements inside a frame whose scale is not 1 and raises a `ValueError`."""

    scaling: FrameScaling = FrameScaling.SIMILAR
    """What changes along with size and mass. With ss the scale and mm the massscale:

    similar

        A change of the units of length and mass: every quantity of dimension `L^a * M^b * T^c` is multiplied by `s^a * m^b`. Positions and sizes are multiplied by `s`, masses by `m`, rotational inertias and torques by `m * s^2`, forces by `m * s`, the stiffness of a slide joint by `m`; times and angles are unchanged. The scaled model moves exactly like the original would in gravity `g/s`. Gravity itself is not scaled, so relative to the model's own forces it is weaker by `1/s`.

    geometry

        Only geometry and inertia change: lengths are multiplied by `s`, masses by `m` and rotational inertias by `m * s^2`, while stiffness, damping, armature, friction loss, force limits and actuator gains keep their authored values. Quantities specified in the time domain, like springdamper or a servo's dampratio, keep that specification, so the stiffness and damping computed from them follow the inertia.

    The policy applies to this frame's scale and massscale only, and is not inherited by nested frames.
    """

    massscale: float = 0
    """Factor `m` of the masses of the frame's contents: masses are multiplied by `m`, rotational inertias by `m * s^2` and densities by `m / s^3`. The default 0 means `m = s_x * s_y * s_z`, the ratio of volumes, which keeps densities constant. Under `similar` scaling `m` is also the factor of the unit of mass, which forces follow. Values must be finite and non-negative. Factors of nested frames compose by multiplication, so massscale "1" in an inner frame is relative to the enclosing frames."""

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

    @field_validator("scale")
    @classmethod
    def validate_scale(cls, value: Vec3 | float) -> Vec3:
        """Spreads a single number over the three axes, and requires finite, positive factors."""
        factors = np.asarray(value, dtype=float)
        if factors.ndim == 0:
            factors = np.full(3, float(factors))
        if not np.all(np.isfinite(factors)) or np.any(factors <= 0):
            msg = "scale must be finite and positive"
            logger.error(msg)
            raise ValueError(msg)
        return factors

    @field_validator("massscale")
    @classmethod
    def validate_massscale(cls, value: float) -> float:
        if not np.isfinite(value) or value < 0:
            msg = "massscale must be finite and non-negative"
            logger.error(msg)
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_anisotropic_scale(self) -> Self:
        if (
            not np.allclose(np.asarray(self.scale), np.asarray(self.scale)[0])
            and self.scaling != FrameScaling.GEOMETRY
        ):
            msg = "Stretching a frame with three different scale values requires scaling=geometry"
            logger.error(msg)
            raise ValueError(msg)
        return self

    @property
    def is_scaled(self) -> bool:
        """Whether this frame's `scale` is anything other than 1 along every axis."""
        return not np.allclose(np.asarray(self.scale, dtype=float), 1.0)

    def walk_bodies(self) -> list[Body]:
        """Recursively collects every body wrapped by this frame, including through nested frames."""
        bodies: list[Body] = []
        for body in self.bodies:
            bodies.extend(body.walk_bodies(include_self=True))
        for frm in self.frames:
            bodies.extend(frm.walk_bodies())
        return bodies
