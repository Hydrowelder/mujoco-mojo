from __future__ import annotations

from copy import deepcopy
from typing import Literal

from pydantic import Field

from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import GeomBase
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import SelfCollide, Vec2, Vec3, Vec5

__all__ = ["FlexContact"]


class FlexContact(XMLModel):
    """This element adjusts the contact properties of the flex. It is mostly identical to geom contact properties, with some extensions specific to flexes."""

    tag = "contact"

    attributes = (
        "contype",
        "conaffinity",
        "condim",
        "priority",
        "friction",
        "solmix",
        "solref",
        "solimp",
        "margin",
        "gap",
        "selfcollide",
        "activelayers",
        "passive",
    )

    selfcollide: SelfCollide = SelfCollide.AUTO
    """This determines the strategy for midphase collision pruning of element pairs belonging to the same flex. none means flex elements cannot collide with each other. narrow means narrow phase only (i.e. all pairs are checked). This is a diagnostic tool and is never a good idea in practice. bvh and sap refer to bounding volume hierarchies and sweep-and-prune (which are two different strategies for midphase collision pruning). auto selects sap in 1D and 2D, and bvh in 3D. Which strategy performs better depends on the specifics of the model. The automatic setting is just a simple rule which we have found to perform well in general."""

    activelayers: int = 1
    """This only has an effect for 3D flexes. Each tetrahedron is labeled by the model compiler with an integer corresponding to (graph) distance to the outside surface of the flex. Thus outside-facing elements are in layer 0, their neighbors are in layer 1, etc. This attribute specifies how many layers will be allowed to participate in collisions. The default setting 1 means that only one layer (i.e. layer 0) can collide, with itself and with the rest of the world. This is usually sufficient, however if the outer layer is composed of small tetrahedra, another body can "pierce" it and get stuck. In that case the value should be increased."""

    contype: int = Field(
        default_factory=lambda: deepcopy(GeomBase.model_fields["contype"].default),
    )
    """Same meaning as regular geom attributes."""

    conaffinity: int = Field(
        default_factory=lambda: deepcopy(GeomBase.model_fields["conaffinity"].default),
    )
    """Same meaning as regular geom attributes."""

    condim: Literal[1, 3, 4, 6] = Field(
        default_factory=lambda: deepcopy(GeomBase.model_fields["condim"].default),
    )
    """Same meaning as regular geom attributes."""

    priority: int = Field(
        default_factory=lambda: deepcopy(GeomBase.model_fields["priority"].default),
    )
    """Same meaning as regular geom attributes."""

    friction: Vec3 = Field(
        default_factory=lambda: deepcopy(GeomBase.model_fields["friction"].default),
    )
    """Same meaning as regular geom attributes."""

    solmix: float = Field(
        default_factory=lambda: deepcopy(GeomBase.model_fields["solmix"].default),
    )
    """Same meaning as regular geom attributes."""

    solref: Vec2 = Field(
        default_factory=lambda: deepcopy(GeomBase.model_fields["solref"].default),
    )
    """Same meaning as regular geom attributes."""

    solimp: Vec5 = Field(
        default_factory=lambda: deepcopy(GeomBase.model_fields["solimp"].default),
    )
    """Same meaning as regular geom attributes."""

    margin: float = Field(
        default_factory=lambda: deepcopy(GeomBase.model_fields["margin"].default),
    )
    """Same meaning as regular geom attributes."""

    gap: float = Field(
        default_factory=lambda: deepcopy(GeomBase.model_fields["gap"].default),
    )
    """Same meaning as regular geom attributes."""

    passive: bool = False
    """When enabled, contact of this flex with another flex, with itself, or with static geometry is not added to the contact solver and is instead applied as a passive normal force. Contact with a body that can move is left on the constraint solver.

    Friction is not modeled on this path: every passive contact is frictionless (condim 1) regardless of the specified condim, and the force is purely normal. A flex therefore slides freely over static geometry, so a cloth will not stay draped over a fixed shape and will not come to rest on a slope. Where friction matters more than non-penetration, leave this option off.

    The force is a penalty on penetration depth whose stiffness is chosen as a natural frequency scaled by the participating vertex mass (or for interpolated flexes, the effective cage node mass at the contact point scaled by the node-to-vertex ratio), so a single value is appropriate across model scales and mesh resolutions; it is not user-specified. That stiffness is integrated implicitly, its curvature being carried by the effective metric, and is therefore far stiffer than an explicit force at the same timestep could be. It follows that the feature requires the `discrete` integrator, with the `CG` or `Newton` solver, no noslip iterations and the sleep flag disabled. A model requesting passive flex collisions otherwise is rejected with an error.

    Being a penalty force, it does not guarantee non-penetration: a thin flex moving fast enough to cross another within one step will pass through it. This is an experimental feature."""
