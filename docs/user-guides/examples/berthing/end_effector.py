"""The end effector: a cylinder with a site at its tip that latches onto a grapple fixture. The arm has one at each end, and they are the same part."""

from __future__ import annotations

from typing import Self

import numpy as np
from shapes import CylinderInput, cylinder_mesh, lying_along

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()  # define a unit system used throughout the model


# --8<-- [start:inputs]
class EndEffectorInput(CylinderInput):
    """Dimensions and mass of an end effector, which is a cylinder, and the size of the site at its tip."""

    RADIUS: float = 0.14 * US.m
    """Radius of the end effector."""

    LENGTH: float = 0.9 * US.m
    """Length of the end effector, from its root to its tip."""

    MASS: float = 40 * US.kg
    """Mass of the end effector."""

    TIP_SITE_SIZE: float = 0.04 * US.m
    """Radius of the sphere that marks the site at the tip."""


END_EFFECTOR = EndEffectorInput()
# --8<-- [end:inputs]


# --8<-- [start:end_effector]
class EndEffector(mojo.UserData):
    """A cylinder with a site at its tip. In its frame it runs along +X from its root, at the origin, to its tip, so the tip site's X axis points out toward whatever it is reaching for, which is the way a grapple fixture's site points into its structure."""

    frame: mojo.Frame
    """The frame at the end effector's root, with its X axis along the end effector. Add it to the body the end effector belongs to."""

    geom: mojo.GeomMesh
    """The end effector's volume."""

    tip: mojo.SiteSphere
    """The site at the tip, which meets a grapple fixture's site."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel, name: str, mount: mojo.AnyPose) -> Self:
        """Makes an end effector whose root is at `mount`, a pose in the body's frame whose X axis is the direction the end effector points. The `name` is put in front of the names of the mesh, the geom, the site and the frame, so each end effector in the model has its own."""
        # the end effector is a builtin cylinder, which MuJoCo makes when it compiles the model
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

        # everything below is in the end effector's own frame: laid down along X and moved out by half its length, with the site at the far end
        geom = mojo.GeomMesh(
            name=mojo.GeomName(f"{name}_effector_geom"),
            mesh=mesh.name,
            pose=lying_along("x", center=np.array((END_EFFECTOR.LENGTH / 2, 0, 0))),
            mass=END_EFFECTOR.MASS,
            rgba=mojo.utils.Color.SLATE_300.rgba,
        )

        # with no rotation of its own, the site's X axis is the frame's, which points along the end effector
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
