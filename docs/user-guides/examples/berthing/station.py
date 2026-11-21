"""The station: a cylinder with a pedestal on top that the arm will stand on."""

from __future__ import annotations

from typing import Self

import numpy as np

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

    PEDESTAL_RADIUS: float = 0.3 * US.m
    """Radius of the pedestal the arm stands on."""

    SHOULDER_HEIGHT: float = 1.2 * US.m
    """Height of the top of the pedestal above the station's center line, which is where the arm's shoulder will sit."""


STATION = StationInput()
# --8<-- [end:inputs]


# --8<-- [start:station]
class Station(mojo.UserData):
    """The station's main cylinder and the pedestal that rises out of it, in one body."""

    body: mojo.Body
    """The station's body. It has no joint, so it is fixed in the world. A free joint here would let it float."""

    cylinder: mojo.GeomCylinder
    """The station's main cylinder."""

    pedestal: mojo.GeomCylinder
    """The pedestal, which starts at the station's center line so it never leaves a gap against the curved surface."""

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

        # make the pedestal which the arm will be attached to
        pedestal = mojo.GeomCylinder(
            name=mojo.GeomName("pedestal_geom"),
            size=STATION.PEDESTAL_RADIUS,
            fromto=np.array((0, 0, 0, 0, 0, STATION.SHOULDER_HEIGHT)),
            rgba=mojo.utils.Color.SLATE_600.with_alpha(OPACITY),
        )

        # attach these geometries to a body which can be made freely moving later on
        body = mojo.Body(
            name=mojo.BodyName("station"),
            geoms=[cylinder, pedestal],
        )
        mojo_model.mjcf.worldbody.bodies.append(body)

        return cls(body=body, cylinder=cylinder, pedestal=pedestal)


# --8<-- [end:station]
