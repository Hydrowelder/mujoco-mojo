"""The whole model: the components put together, and the `generate` entry point that builds it."""

from __future__ import annotations

from typing import Self

import numpy as np
from arm import Arm
from capture import Capture
from environment import Environment
from overview import Overview
from station import Station
from visitor import Visitor

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()  # define a unit system used throughout the model


# --8<-- [start:model]
class Berthing(mojo.UserData):
    """Root user data for the whole model, which collects the parts the runtime will need. `generate` stores it on `mojo_model.user_data`, and the runtime reads it back with `mojo_model.get_user_data(Berthing)`."""

    station: Station
    """The station, with the grapple fixture the arm is latched onto."""

    arm: Arm
    """The arm, with its joints and servos, its two end effectors and its camera."""

    visitor: Visitor
    """The visiting vehicle, with the grapple fixture the arm grabs."""

    overview: Overview
    """The fixed camera that follows the visitor."""

    capture: Capture
    """The weld that joins the arm to the visitor, which starts switched off."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        """Builds every component and puts it in the model."""
        mojo_model.mjcf.model = mojo.ModelName("Berthing")
        mojo_model.mjcf.worldbody = mojo.WorldBody()

        station = Station.new(mojo_model)
        arm = Arm.new(mojo_model, station.fixture)
        Environment.new(mojo_model)
        visitor = Visitor.new(mojo_model)
        overview = Overview.new(mojo_model, visitor.body)
        capture = Capture.new(mojo_model, arm, visitor)

        return cls(
            station=station,
            arm=arm,
            visitor=visitor,
            overview=overview,
            capture=capture,
        )


# --8<-- [end:model]


# --8<-- [start:generate]
def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Generates the MJCF model."""
    mojo_model.us = US
    mojo_model.user_data = Berthing.new(mojo_model)

    mojo_model.mjcf.options.append(
        mojo.Option(
            timestep=0.002 * US.s,
            gravity=np.array((0, 0, 0)) * US["m/s**2"],
            # the arm's servos are stiff and heavily damped, so the integrator treats that damping implicitly
            integrator=mojo.Integrator.IMPLICITFAST,
            # nothing in this model is meant to touch, so contacts are off (the parts overlap in places, which would push them apart) and the distances that matter are measured by Proximity; the capture weld is a constraint, not a contact, so it still works
            flag=mojo.Flag(contact=mojo.typing.EnableDisable.DISABLE),
        )
    )

    # a viewer sizes its frames, joint axes and other markers in units of the model's mean body size, which MuJoCo works out on its own (and the big station makes it large), so it is fixed at one meter and the scales below are lengths in meters
    mojo_model.mjcf.statistics.append(mojo.Statistic(meansize=1.0 * US.m))
    mojo_model.mjcf.visuals.append(
        mojo.Visual(scale=mojo.VisualScale(framelength=0.5, framewidth=0.03))
    )
    return mojo_model


# --8<-- [end:generate]
