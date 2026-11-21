"""The visiting vehicle: a cylindrical hull with a grapple fixture, free to move."""

from __future__ import annotations

from typing import Self

import numpy as np
from fixture import GrappleFixture
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


VISITOR = VisitorInput()
# --8<-- [end:inputs]


# --8<-- [start:visitor]
class Visitor(mojo.UserData):
    """The visiting vehicle: a cylindrical hull with a grapple fixture, free to drift, in a body whose X axis points away from the station."""

    body: mojo.Body
    """The visitor's body, which has a free joint."""

    hull: mojo.GeomMesh
    """The hull's volume."""

    fixture: GrappleFixture
    """The grapple fixture on the side of the hull that faces the station. Its site's X axis points into the hull, along the visitor's own X axis."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        assert mojo_model.mjcf.worldbody  # for type hinting

        # the hull is a builtin cylinder, which MuJoCo makes when it compiles the model, laid down along Y
        mojo_model.mjcf.assets.append(
            mojo.Asset(
                meshes=[
                    hull_mesh := cylinder_mesh(
                        "hull_mesh", VISITOR.HULL_RADIUS, VISITOR.HULL_LENGTH
                    )
                ]
            )
        )
        assert hull_mesh.name

        hull = mojo.GeomMesh(
            name=mojo.GeomName("hull_geom"),
            mesh=hull_mesh.name,
            pose=lying_along("y"),
            mass=VISITOR.HULL_MASS,
            rgba=mojo.utils.Color.CYAN_500.with_alpha(OPACITY),
        )

        # the body's X axis points away from the station, so the side that faces the station is -X: the fixture is mounted on the hull's surface there, and the body's own orientation already has X pointing into the hull
        fixture = GrappleFixture.new(
            mojo_model,
            "visitor",
            mojo.PoseQuat(pos=np.array((-VISITOR.HULL_RADIUS, 0, 0))),
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
            geoms=[hull],
            frames=[fixture.frame],
            freejoints=[mojo.FreeJoint()],
        )
        mojo_model.mjcf.worldbody.bodies.append(body)

        return cls(body=body, hull=hull, fixture=fixture)


# --8<-- [end:visitor]
