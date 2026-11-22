"""A short post with a site at its tip, which the arm grabs. The visitor carries one, and so does the station."""

from __future__ import annotations

from typing import Self

import numpy as np
from shapes import cylinder_mesh, lying_along

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()

# the post is sunk this far into the structure so a curved surface leaves no gap under its edge
SEAT = 0.05 * US.m


# --8<-- [start:inputs]
class FixtureInput(mojo.UserData):
    """Dimensions and mass of a grapple fixture."""

    LENGTH: float = 0.4 * US.m
    """How far the post sticks out of the structure, which is the distance from the surface to the site."""

    RADIUS: float = 0.15 * US.m
    """Radius of the post."""

    MASS: float = 20 * US.kg
    """Mass of the post."""

    SITE_SIZE: float = 0.05 * US.m
    """Radius of the sphere that marks the site."""


FIXTURE = FixtureInput()
# --8<-- [end:inputs]


# --8<-- [start:fixture]
class GrappleFixture(mojo.UserData):
    """A post sticking out of a structure, with a site at its tip."""

    frame: mojo.Frame
    """The frame where the post meets the structure, with its X axis pointing into the structure. Add it to the structure's body."""

    geom: mojo.GeomMesh
    """The post's volume."""

    site: mojo.SiteSphere
    """The site at the post's tip. Its X axis points into the structure, which is the way an end effector comes in."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel, name: str, mount: mojo.AnyPose) -> Self:
        """Makes a fixture at `mount`, a pose whose X axis points into the structure. `name` prefixes the names of everything it makes."""
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

        # in the mount's frame the structure is on the +X side, so the post runs along -X from the seat to the tip
        geom = mojo.GeomMesh(
            name=mojo.GeomName(f"{name}_fixture_geom"),
            mesh=mesh.name,
            pose=lying_along("x", center=np.array(((SEAT - FIXTURE.LENGTH) / 2, 0, 0))),
            mass=FIXTURE.MASS,
            rgba=mojo.utils.Color.ORANGE_500.rgba,
        )

        # no rotation of its own, so the site's X axis is the mount's
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
