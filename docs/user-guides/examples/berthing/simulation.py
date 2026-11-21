"""The whole model: the components put together, and the `generate` entry point that builds it."""

from __future__ import annotations

import numpy as np
from arm import Arm
from environment import Environment
from station import Station
from visitor import Visitor

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()  # define a unit system used throughout the model


# --8<-- [start:generate]
def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Generates the MJCF model."""
    mojo_model.us = US
    mojo_model.mjcf.model = mojo.ModelName("Berthing")
    mojo_model.mjcf.worldbody = mojo.WorldBody()

    station = Station.new(mojo_model)
    Arm.new(mojo_model, station.fixture)
    Environment.new(mojo_model)
    Visitor.new(mojo_model)

    mojo_model.mjcf.options.append(
        mojo.Option(
            timestep=0.002 * US.s,
            gravity=np.array((0, 0, 0)) * US["m/s**2"],
        )
    )

    # a viewer sizes its frames, joint axes and other markers in units of the model's mean body size, which MuJoCo works out on its own (and the big station makes it large), so it is fixed at one meter and the scales below are lengths in meters
    mojo_model.mjcf.statistics.append(mojo.Statistic(meansize=1.0 * US.m))
    mojo_model.mjcf.visuals.append(
        mojo.Visual(scale=mojo.VisualScale(framelength=0.5, framewidth=0.03))
    )
    return mojo_model


# --8<-- [end:generate]
