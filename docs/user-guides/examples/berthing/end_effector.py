"""A cylinder with a site at its tip that latches onto a grapple fixture. The arm has the same one at each end."""

from __future__ import annotations

from typing import Self

import numpy as np
from shapes import CylinderInput, cylinder_mesh, lying_along

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()


# --8<-- [start:inputs]
class EndEffectorInput(CylinderInput):
    """Dimensions and mass of an end effector, and the size of its tip site."""

    RADIUS: float = 0.14 * US.m
    """Radius of the end effector."""

    LENGTH: float = 0.9 * US.m
    """Length of the end effector, from its root to its tip."""

    MASS: float = 40 * US.kg
    """Mass of the end effector."""

    TIP_SITE_SIZE: float = 0.04 * US.m
    """Radius of the sphere that marks the tip site."""


END_EFFECTOR = EndEffectorInput()
# --8<-- [end:inputs]


# --8<-- [start:end_effector]
class EndEffector(mojo.UserData):
    """A cylinder that runs along +X from its root to a site at its tip."""

    frame: mojo.Frame
    """The frame at the root, with its X axis along the end effector. Add it to the body it belongs to."""

    geom: mojo.GeomMesh
    """The end effector's volume."""

    tip: mojo.SiteSphere
    """The site at the tip, which meets a grapple fixture's site."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel, name: str, mount: mojo.AnyPose) -> Self:
        """Makes an end effector with its root at `mount`, a pose whose X axis is the direction it points. `name` prefixes the names of everything it makes."""
        mojo_model.mjcf.assets.append(
            mojo.Asset(
                meshes=[
                    mesh := cylinder_mesh(
                        f"{name}_effector_mesh",
                        END_EFFECTOR.RADIUS,
                        END_EFFECTOR.LENGTH,
                    )
                ]
            )
        )
        assert mesh.name

        geom = mojo.GeomMesh(
            name=mojo.GeomName(f"{name}_effector_geom"),
            mesh=mesh.name,
            pose=lying_along("x", center=np.array((END_EFFECTOR.LENGTH / 2, 0, 0))),
            mass=END_EFFECTOR.MASS,
            rgba=mojo.utils.Color.SLATE_300.rgba,
        )

        # no rotation of its own, so the site's X axis points along the end effector, the same way a fixture's site points into its structure
        tip = mojo.SiteSphere(
            name=mojo.SiteName(f"{name}_tip_site"),
            size=END_EFFECTOR.TIP_SITE_SIZE,
            pose=mojo.PoseQuat(pos=np.array((END_EFFECTOR.LENGTH, 0, 0))),
            rgba=mojo.utils.Color.AMBER_500.rgba,
        )

        frame = mojo.Frame(
            name=mojo.FrameName(f"{name}_effector"),
            pose=mount,
            geoms=[geom],
            sites=[tip],
        )
        return cls(frame=frame, geom=geom, tip=tip)


# --8<-- [end:end_effector]
