"""The station: a cylinder with a grapple fixture on top for the arm's base, and a berthing point."""

from __future__ import annotations

from typing import Self

import numpy as np
from fixture import GrappleFixture
from shapes import CylinderInput, lying_along

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()

OPACITY = 0.3  # 0 is invisible, 1 is solid


# --8<-- [start:inputs]
class StationInput(CylinderInput):
    """Dimensions of the station."""

    RADIUS: float = 0.8 * US.m
    """Radius of the station's cylinder."""

    LENGTH: float = 6.0 * US.m
    """Length of the station's cylinder, which lies along Y and is centered on the origin."""

    MASS: float = 400_000 * US.kg
    """Mass of the station's cylinder. It has no effect, since the station is fixed in the world."""

    BERTH_POSITION: tuple[float, float, float] = (3.0 * US.m, 0.0 * US.m, 1.5 * US.m)
    """Where the visitor's grapple site is brought to, as X, Y and Z in the world. It must be far enough out for the end effector, which lies behind the site, to clear the station."""


STATION = StationInput()
# --8<-- [end:inputs]


# --8<-- [start:station]
class Station(mojo.UserData):
    """The station's cylinder, the grapple fixture for the arm's base and the berthing point, in one fixed body."""

    body: mojo.Body
    """The station's body, fixed in the world."""

    cylinder: mojo.GeomMesh
    """The station's cylinder."""

    fixture: GrappleFixture
    """The grapple fixture the arm's base attaches to. Its site's X axis points down into the station."""

    berth: mojo.SiteSphere
    """The berthing point, a marker for where the visitor goes. Its X axis points away from the station."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        assert mojo_model.mjcf.worldbody  # for type hinting

        mojo_model.mjcf.assets.append(
            mojo.Asset(meshes=[mesh := STATION.mesh("station_mesh")])
        )
        assert mesh.name

        cylinder = mojo.GeomMesh(
            name=mojo.GeomName("station_geom"),
            mesh=mesh.name,
            pose=lying_along("y"),
            mass=STATION.MASS,
            rgba=mojo.utils.Color.SLATE_500.with_alpha(OPACITY),
        )

        # turned so the fixture's X axis points down into the station
        fixture = GrappleFixture.new(
            mojo_model,
            "station",
            mojo.PoseEuler(
                euler=np.array((0, 90, 0)),
                angle=mojo.Angle.DEGREE,
                pos=np.array((0, 0, STATION.RADIUS)),
            ),
        )

        # no rotation of its own, so its X axis points away from the station, and so does the visitor's once it is berthed
        berth = mojo.SiteSphere(
            name=mojo.SiteName("berth_site"),
            size=0.1 * US.m,
            pose=mojo.PoseQuat(pos=np.array(STATION.BERTH_POSITION)),
            rgba=mojo.utils.Color.LIME_400.rgba,
        )

        body = mojo.Body(
            name=mojo.BodyName("station"),
            geoms=[cylinder],
            sites=[berth],
            frames=[fixture.frame],
        )
        mojo_model.mjcf.worldbody.bodies.append(body)

        return cls(body=body, cylinder=cylinder, fixture=fixture, berth=berth)


# --8<-- [end:station]
