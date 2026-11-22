"""The weld that joins the arm's free end effector to the visitor's grapple fixture."""

from __future__ import annotations

from typing import Self

from arm import Arm
from visitor import Visitor

import mujoco_mojo as mojo


# --8<-- [start:capture]
class Capture(mojo.UserData):
    """A weld between the end effector's tip and the visitor's grapple site, switched off until the capture."""

    weld: mojo.EqualityWeldSite
    """The weld, inactive at the start."""

    def engage(self, state: mojo.MjState) -> None:
        """Switches the weld on, so the visitor goes wherever the arm goes."""
        self.weld.enable(state)

    def release(self, state: mojo.MjState) -> None:
        """Switches the weld off, which lets the visitor go."""
        self.weld.disable(state)

    def is_engaged(self, state: mojo.MjState) -> bool:
        """Whether the weld is on."""
        return self.weld.is_active(state)

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel, arm: Arm, visitor: Visitor) -> Self:
        """Makes the weld and adds it to the model."""
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
