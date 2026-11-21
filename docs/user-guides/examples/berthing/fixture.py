"""The grapple fixture: a short post with a site at its tip, which the arm grabs. The visiting vehicle carries one, and so does the station, which is where the arm's base attaches."""

from __future__ import annotations

from typing import Self

import numpy as np
from shapes import cylinder_mesh, lying_along

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()  # define a unit system used throughout the model

# how far the post is sunk into the structure, so a curved surface never leaves a gap under its edge
SEAT = 0.05 * US.m


# --8<-- [start:inputs]
class FixtureInput(mojo.UserData):
    """Dimensions and mass of a grapple fixture."""

    LENGTH: float = 0.4 * US.m
    """How far the fixture sticks out of the structure's surface, which is the distance from the surface to its site."""

    RADIUS: float = 0.15 * US.m
    """Radius of the fixture's post."""

    MASS: float = 20 * US.kg
    """Mass of the fixture's post."""

    SITE_SIZE: float = 0.05 * US.m
    """Radius of the sphere that marks the site at the fixture's tip."""


FIXTURE = FixtureInput()
# --8<-- [end:inputs]


# --8<-- [start:fixture]
class GrappleFixture(mojo.UserData):
    """A post that sticks out of a structure, with a site at its tip. The site's X axis points from the tip into the structure, which is the way an end effector comes in to grab it."""

    frame: mojo.Frame
    """The frame at the mount, where the fixture meets the structure, with its X axis pointing into the structure. Add it to the body the fixture belongs to."""

    geom: mojo.GeomMesh
    """The post's volume."""

    site: mojo.SiteSphere
    """The site at the post's tip, which an end effector will meet. It has the frame's orientation, so its X axis points into the structure."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel, name: str, mount: mojo.AnyPose) -> Self:
        """Makes a fixture at `mount`, a pose in the body's frame whose X axis points into the structure. The `name` is put in front of the names of the mesh, the geom, the site and the frame, so each fixture in the model has its own."""
        # the post is a builtin cylinder, which MuJoCo makes when it compiles the model
        mojo_model.mjcf.assets.append(
            mojo.Asset(
                meshes=[
                    mesh := cylinder_mesh(
                        f"{name}_fixture_mesh", FIXTURE.RADIUS, FIXTURE.LENGTH + SEAT
                    )
                ]
            )
        )
        assert mesh.name

        # everything below is in the mount's frame, where the structure is on the +X side and the post sticks out along -X, from the seat inside the structure to the tip
        geom = mojo.GeomMesh(
            name=mojo.GeomName(f"{name}_fixture_geom"),
            mesh=mesh.name,
            pose=lying_along("x", center=np.array(((SEAT - FIXTURE.LENGTH) / 2, 0, 0))),
            mass=FIXTURE.MASS,
            rgba=mojo.utils.Color.ORANGE_500.rgba,
        )

        # with no rotation of its own, the site's X axis is the mount's, which points from the tip into the structure
        site = mojo.SiteSphere(
            name=mojo.SiteName(f"{name}_grapple_site"),
            size=FIXTURE.SITE_SIZE,
            pose=mojo.PoseQuat(pos=np.array((-FIXTURE.LENGTH, 0, 0))),
            rgba=mojo.utils.Color.ORANGE_500.rgba,
        )

        frame = mojo.Frame(
            name=mojo.FrameName(f"{name}_fixture"),
            pose=mount,
            geoms=[geom],
            sites=[site],
        )
        return cls(frame=frame, geom=geom, site=site)


# --8<-- [end:fixture]
