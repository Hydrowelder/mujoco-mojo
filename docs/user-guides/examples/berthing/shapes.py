"""Helpers shared by the parts."""

from __future__ import annotations

from typing import Literal

import numpy as np

import mujoco_mojo as mojo


# --8<-- [start:shapes]
class CylinderInput(mojo.UserData):
    """Radius, length and mass of a cylinder."""

    RADIUS: float
    """Radius of the cylinder."""

    LENGTH: float
    """Length of the cylinder, along its axis."""

    MASS: float
    """Mass of the cylinder."""


def cylinder_mesh(
    name: str, radius: float, length: float, cells: int = 8
) -> mojo.MeshCylinder:
    """A builtin cylinder mesh along Z, centered on the origin."""
    # a builtin mesh spans (count - 1) * spacing along each axis, so count is one more than the cells
    return mojo.MeshCylinder(
        name=mojo.MeshName(name),
        count=(cells + 1, cells + 1, cells + 1),
        spacing=np.array((2 * radius / cells, 2 * radius / cells, length / cells)),
    )


def lying_along(
    axis: Literal["x", "y"], center: mojo.Vec3 | None = None
) -> mojo.PoseEuler:
    """A pose at `center` that turns a mesh built along Z to lie along `axis`."""
    euler = {"x": (0, 90, 0), "y": (-90, 0, 0)}[axis]
    return mojo.PoseEuler(
        euler=np.array(euler),
        angle=mojo.Angle.DEGREE,
        pos=np.zeros(3) if center is None else center,
    )


# --8<-- [end:shapes]
