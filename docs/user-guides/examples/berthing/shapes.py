"""Shapes shared by the components."""

from __future__ import annotations

from typing import Literal

import numpy as np

import mujoco_mojo as mojo


# --8<-- [start:shapes]
def cylinder_mesh(
    name: str, radius: float, length: float, cells: int = 8
) -> mojo.MeshCylinder:
    """A builtin cylinder that MuJoCo generates at compile time, along Z and centered on the origin. Its extent along each axis is `(count - 1) * spacing`, so a count of `cells + 1` and a spacing of the size over `cells` gives the size asked for."""
    return mojo.MeshCylinder(
        name=mojo.MeshName(name),
        count=(cells + 1, cells + 1, cells + 1),
        spacing=np.array((2 * radius / cells, 2 * radius / cells, length / cells)),
    )


def lying_along(
    axis: Literal["x", "y"], center: mojo.Vec3 | None = None
) -> mojo.PoseEuler:
    """A pose at `center` that lays a mesh built along Z down along `axis` instead."""
    euler = {"x": (0, 90, 0), "y": (-90, 0, 0)}[axis]
    return mojo.PoseEuler(
        euler=np.array(euler),
        angle=mojo.Angle.DEGREE,
        pos=np.zeros(3) if center is None else center,
    )


# --8<-- [end:shapes]
