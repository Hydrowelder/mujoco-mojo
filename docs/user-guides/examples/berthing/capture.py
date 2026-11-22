"""The capture weld: the constraint that joins the arm's free end effector to the visitor's grapple fixture, switched off until the arm has grabbed it."""

from __future__ import annotations

from typing import Self

from arm import Arm
from visitor import Visitor

import mujoco_mojo as mojo


# --8<-- [start:capture]
class Capture(mojo.UserData):
    """The weld between the free end effector's tip and the visitor's grapple site. It pulls the two site frames together, position and orientation, wherever the bodies happen to be, so it can be switched on mid-run: until then the arm and the visitor do not know about each other, and once it is on the visitor is carried wherever the arm goes."""

    weld: mojo.EqualityWeldSite
    """The weld. It starts inactive. Its `name` is what the runtime needs to switch it on and off."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel, arm: Arm, visitor: Visitor) -> Self:
        """Makes the weld between the tip of the arm's free end effector and the site at the tip of the visitor's grapple fixture, and adds it to the model."""
        tip = arm.free_effector.tip.name
        grapple = visitor.fixture.site.name
        assert tip
        assert grapple

        weld = mojo.EqualityWeldSite(
            name=mojo.EqualityName("capture"),
            site1=tip,
            site2=grapple,
            active=False,
        )
        mojo_model.mjcf.equalities.append(mojo.Equality(welds=[weld]))

        return cls(weld=weld)


# --8<-- [end:capture]
