"""The visiting vehicle: a cylindrical hull that is free to move."""

from __future__ import annotations

from typing import Self

import numpy as np
from shapes import cylinder_mesh, lying_along

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()  # define a unit system used throughout the model

OPACITY = 0.6  # how opaque the hull is, from 0 (invisible) to 1 (solid)


# --8<-- [start:inputs]
class VisitorInput(mojo.UserData):
    """Dimensions, mass and starting place of the visiting vehicle."""

    HULL_LENGTH: float = 3.0 * US.m
    """Length of the hull, which is a cylinder lying along Y."""

    HULL_RADIUS: float = 0.9 * US.m
    """Radius of the hull."""

    HULL_MASS: float = 1500 * US.kg
    """Mass of the hull."""

    RANGE: float = 6.0 * US.m
    """Horizontal distance from the shoulder's axis to the center of the hull."""

    AZIMUTH_DEG: float = 20
    """Direction of the hull from the shoulder's axis, in degrees from the station's X axis. The visitor's X axis points this way, away from the station."""

    HEIGHT: float = 1.5 * US.m
    """Height of the hull's center above the station's center line."""

    FIXTURE_LENGTH: float = 0.4 * US.m
    """How far the grapple fixture sticks out of the side of the hull that faces the station."""

    FIXTURE_RADIUS: float = 0.15 * US.m
    """Radius of the grapple fixture."""

    FIXTURE_MASS: float = 20 * US.kg
    """Mass of the grapple fixture."""


VISITOR = VisitorInput()
# --8<-- [end:inputs]


# --8<-- [start:visitor]
class Visitor(mojo.UserData):
    """The visiting vehicle: a cylindrical hull with a grapple fixture, free to drift, in a body whose X axis points away from the station."""

    body: mojo.Body
    """The visitor's body, which has a free joint."""

    hull: mojo.GeomMesh
    """The hull's volume."""

    fixture: mojo.GeomMesh
    """The grapple fixture's volume, a short cylinder on the side of the hull that faces the station."""

    grapple_site: mojo.SiteSphere
    """The site at the fixture's tip that the arm's end effector will meet. Its X axis points into the hull, along the visitor's own X axis."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        assert mojo_model.mjcf.worldbody  # for type hinting

        # the hull and the fixture are builtin cylinders, which MuJoCo makes when it compiles the model
        mojo_model.mjcf.assets.append(
            mojo.Asset(
                meshes=[
                    hull_mesh := cylinder_mesh(
                        "hull_mesh", VISITOR.HULL_RADIUS, VISITOR.HULL_LENGTH
                    ),
                    fixture_mesh := cylinder_mesh(
                        "fixture_mesh", VISITOR.FIXTURE_RADIUS, VISITOR.FIXTURE_LENGTH
                    ),
                ]
            )
        )
        assert hull_mesh.name
        assert fixture_mesh.name

        hull = mojo.GeomMesh(
            name=mojo.GeomName("hull_geom"),
            mesh=hull_mesh.name,
            pose=lying_along("y"),
            mass=VISITOR.HULL_MASS,
            rgba=mojo.utils.Color.CYAN_500.with_alpha(OPACITY),
        )

        # the body's X axis points away from the station, so the side that faces the station is -X: the fixture starts at the hull's surface there and sticks out along -X
        fixture = mojo.GeomMesh(
            name=mojo.GeomName("fixture_geom"),
            mesh=fixture_mesh.name,
            pose=lying_along(
                "x",
                center=np.array(
                    (-(VISITOR.HULL_RADIUS + VISITOR.FIXTURE_LENGTH / 2), 0, 0)
                ),
            ),
            mass=VISITOR.FIXTURE_MASS,
            rgba=mojo.utils.Color.ORANGE_500.rgba,
        )

        # the site is at the fixture's tip, and with no rotation of its own its X axis is the body's, which points from the tip into the hull
        grapple_site = mojo.SiteSphere(
            name=mojo.SiteName("grapple_site"),
            size=0.05 * US.m,
            pose=mojo.PoseQuat(
                pos=np.array((-(VISITOR.HULL_RADIUS + VISITOR.FIXTURE_LENGTH), 0, 0))
            ),
            rgba=mojo.utils.Color.ORANGE_500.rgba,
        )

        # the body sits on the line from the shoulder's axis out through the azimuth, turned to face along it
        azimuth = np.deg2rad(VISITOR.AZIMUTH_DEG)
        center = np.array(
            (
                VISITOR.RANGE * np.cos(azimuth),
                VISITOR.RANGE * np.sin(azimuth),
                VISITOR.HEIGHT,
            )
        )
        body = mojo.Body(
            name=mojo.BodyName("visitor"),
            pose=mojo.PoseEuler(
                euler=np.array((0, 0, VISITOR.AZIMUTH_DEG)),
                angle=mojo.Angle.DEGREE,
                pos=center,
            ),
            geoms=[hull, fixture],
            sites=[grapple_site],
            freejoints=[mojo.FreeJoint()],
        )
        mojo_model.mjcf.worldbody.bodies.append(body)

        return cls(body=body, hull=hull, fixture=fixture, grapple_site=grapple_site)


# --8<-- [end:visitor]
