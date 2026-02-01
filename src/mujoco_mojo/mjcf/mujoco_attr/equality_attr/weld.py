from __future__ import annotations

from typing import Annotated, Literal, Optional

import numpy as np
from pydantic import Field

from mujoco_mojo.mjcf.mujoco_attr.equality_attr.equality_base import EqualityBase
from mujoco_mojo.typing import BodyName, SiteName, Vec3, Vec7

__all__ = ["EqualityWeldBody", "EqualityWeldSite"]


class EqualityWeldBody(EqualityBase):
    """This element creates a weld equality constraint. It attaches two bodies to each other, removing all relative degrees of freedom between them (softly of course, like all other constraints in MuJoCo). The two bodies are not required to be close to each other. The relative body position and orientation being enforced by the constraint solver is the one in which the model was defined. Note that two bodies can also be welded together rigidly, by defining one body as a child of the other body, without any joint elements in the child body.

    Using body1 (and optionally anchor, relpose, body2). When using this specification, the constraint is assumed to be satisfied at the configuration in which the model is defined.
    """

    tag = "weld"
    attributes = EqualityBase.attributes + (
        "body1",
        "body2",
        "anchor",
        "relpose",
        "toquescale",
    )

    type: Literal["body"] = "body"

    body1: BodyName
    """Name of the first body participating in the constraint."""

    body2: Optional[BodyName] = None
    """Name of the second body. If this attribute is omitted, the second body is the world body. Welding a body to the world and changing the corresponding component of mjData.eq_active at runtime can be used to fix the body temporarily."""

    relpose: Vec7 = np.array((0, 1, 0, 0, 0, 0, 0))
    """This attribute specifies the relative pose (3D position followed by 4D quaternion orientation) of body2 relative to body1. If the quaternion part (i.e., last 4 components of the vector) are all zeros, as in the default setting, this attribute is ignored and the relative pose is the one corresponding to the model reference pose in qpos0. The unusual default is because all equality constraint types share the same default for their numeric parameters."""

    anchor: Optional[Vec3] = np.array((0, 0, 0))
    """Coordinates of the weld point relative to body2. If relpose is not specified, the meaning of this parameter is the same as for connect constraints, except that is relative to body2. If relpose is specified, body1 will use the pose to compute its anchor point."""

    toquescale: float = 1
    """A constant that scales the angular residual (angular constraint violation). Notionally in units of torque/force=lengthtorque/force=length. Intuitively this coefficient defines how much the weld "cares" about rotational displacements vs. translational displacements. Setting this value to 0 makes the weld behave like a connect constraint. Note that this value has units of length and can therefore be understood as follows. Imagining that the weld is implemented by a flat patch of glue sticking the two bodies together, torquescale can be interpreted as the diameter of this glue patch."""


class EqualityWeldSite(EqualityBase):
    """This element creates a weld equality constraint. It attaches two bodies to each other, removing all relative degrees of freedom between them (softly of course, like all other constraints in MuJoCo). The two bodies are not required to be close to each other. The relative body position and orientation being enforced by the constraint solver is the one in which the model was defined. Note that two bodies can also be welded together rigidly, by defining one body as a child of the other body, without any joint elements in the child body.

    site1 and site2 (both required). When using this specification, the frames of the two sites will be aligned by the constraint, regardless of their position in the default configuration. An example of this specification is shown in this model.
    """

    tag = "weld"
    attributes = EqualityBase.attributes + ("site1", "site2", "toquescale")

    type: Literal["site"] = "site"

    site1: SiteName
    """Name of a site belonging to the first body participating in the constraint. When specified, site2 must also be specified. The (site1, site2) specification is a more flexible alternative to the body-based specification, and is different in two ways. First, the sites are not required to overlap at the default configuration; if they do not overlap then the sites will "snap together" at the beginning of the simulation. Second, changing the site position and orientation in mjModel.site_pos and mjModel.site_quat at runtime will correctly change the position and orientation of the constraint (i.e. the content of mjModel.eq_data has no effect when this semantic is used, with the exception of torquescale)."""

    site2: SiteName
    """Name of a site belonging to the second body participating in the constraint. When specified, site1 must also be specified. See the site1 description for more details."""

    toquescale: float = 1
    """A constant that scales the angular residual (angular constraint violation). Notionally in units of torque/force=lengthtorque/force=length. Intuitively this coefficient defines how much the weld "cares" about rotational displacements vs. translational displacements. Setting this value to 0 makes the weld behave like a connect constraint. Note that this value has units of length and can therefore be understood as follows. Imagining that the weld is implemented by a flat patch of glue sticking the two bodies together, torquescale can be interpreted as the diameter of this glue patch."""


EqualityWeld = Annotated[
    EqualityWeldBody | EqualityWeldSite, Field(discriminator="type")
]
"""Discriminated union for type hinting the various types of Weld."""
