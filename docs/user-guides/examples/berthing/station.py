"""The station: a cylinder with a grapple fixture on top that the arm will be attached to."""

from __future__ import annotations

from typing import Self

import numpy as np
from fixture import GrappleFixture

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()  # define a unit system used throughout the model

OPACITY = 0.3  # how opaque the station is, from 0 (invisible) to 1 (solid)


# --8<-- [start:inputs]
class StationInput(mojo.UserData):
    """Dimensions of the station."""

    RADIUS: float = 0.8 * US.m
    """Radius of the station's main cylinder."""

    LENGTH: float = 6.0 * US.m
    """Length of the station's main cylinder, which lies along Y and is centered on the origin."""


STATION = StationInput()
# --8<-- [end:inputs]


# --8<-- [start:station]
class Station(mojo.UserData):
    """The station's main cylinder and the grapple fixture on top of it that the arm's base attaches to, in one body."""

    body: mojo.Body
    """The station's body. It has no joint, so it is fixed in the world. A free joint here would let it float."""

    cylinder: mojo.GeomCylinder
    """The station's main cylinder."""

    fixture: GrappleFixture
    """The grapple fixture on top of the station, the same part the visitor carries. Its site's X axis points down into the station."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        assert mojo_model.mjcf.worldbody  # for type hinting

        # make the main truss structure as a cylinder
        cylinder = mojo.GeomCylinder(
            name=mojo.GeomName("station_geom"),
            size=STATION.RADIUS,
            fromto=np.array((0, -STATION.LENGTH / 2, 0, 0, STATION.LENGTH / 2, 0)),
            rgba=mojo.utils.Color.SLATE_500.with_alpha(OPACITY),
        )

        # mount the same grapple fixture the visitor carries on top of the cylinder, where the arm will be attached, turned so its X axis points down into the station
        fixture = GrappleFixture.new(
            mojo_model,
            "station",
            mojo.PoseEuler(
                euler=np.array((0, 90, 0)),
                angle=mojo.Angle.DEGREE,
                pos=np.array((0, 0, STATION.RADIUS)),
            ),
        )

        # attach these to a body which can be made freely moving later on
        body = mojo.Body(
            name=mojo.BodyName("station"),
            geoms=[cylinder],
            frames=[fixture.frame],
        )
        mojo_model.mjcf.worldbody.bodies.append(body)

        return cls(body=body, cylinder=cylinder, fixture=fixture)


# --8<-- [end:station]
