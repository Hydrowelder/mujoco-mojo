from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import Field

from mujoco_mojo.mjcf.mujoco_attr.equality_attr.equality_base import EqualityBase
from mujoco_mojo.typing import BodyName, SiteName, Vec3

__all__ = ["EqualityConnectBody", "EqualityConnectSite"]


class EqualityConnectBody(EqualityBase):
    """This element creates an equality constraint that connects two bodies at a point. The constraint effectively defines a ball joint outside the kinematic tree.

    Using body1 and anchor (both required) and optionally body2. When using this specification, the constraint is assumed to be satisfied at the configuration in which the model is defined (mjData.qpos0).
    """

    tag = "connect"
    attributes = EqualityBase.attributes + ("body1", "body2", "anchor")

    type: Literal["body"] = "body"

    body1: BodyName
    """Name of the first body participating in the constraint."""

    body2: Optional[BodyName] = None
    """Name of the second body participating in the constraint. If this attribute is omitted, the second body is the world body."""

    anchor: Optional[Vec3] = None
    """Coordinates of the 3D anchor point where the two bodies are connected, in the local coordinate frame of body1. The constraint is assumed to be satisfied in the configuration at which the model is defined (mjData.qpos0), which lets the compiler compute the associated anchor point for body2."""


class EqualityConnectSite(EqualityBase):
    """This element creates an equality constraint that connects two bodies at a point. The constraint effectively defines a ball joint outside the kinematic tree.

    site1 and site2 (both required). When using this specification, the two sites will be pulled together by the constraint, regardless of their position in the default configuration. An example of this specification is shown in this model.
    """

    attributes = EqualityBase.attributes + ("site1", "site2")

    type: Literal["site"] = "site"

    site1: SiteName
    """Name of a site belonging to the first body participating in the constraint. When specified, site2 must also be specified. The (site1, site2) specification is a more flexible alternative to the body-based specification, and is different in two ways. First, the sites are not required to overlap at the default configuration; if they do not overlap then the sites will "snap together" at the beginning of the simulation. Second, changing the site positions in mjModel.site_pos at runtime will correctly change the position of the constraint (i.e. the content of mjModel.eq_data has no effect when this semantic is used)."""

    site2: SiteName
    """Name of a site belonging to the second body participating in the constraint. When specified, site1 must also be specified. See the site1 description for more details."""


EqualityConnect = Annotated[
    EqualityConnectBody | EqualityConnectSite, Field(discriminator="type")
]
"""Discriminated union for type hinting the various types of Connect."""
