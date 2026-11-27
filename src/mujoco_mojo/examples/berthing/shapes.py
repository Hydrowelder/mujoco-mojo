"""Helpers shared by the parts."""

from __future__ import annotations

from typing import Literal

import numpy as np

import mujoco_mojo as mojo


# --8<-- [start:shapes]
# contact filtering: MuJoCo lets two geoms collide only if the `contype` of one shares a bit with the `conaffinity` of the other
# the arm's parts offer bit 1 and accept none, so no part of the arm touches another, even where their volumes overlap at a joint
ARM_CONTYPE = 1
ARM_CONAFFINITY = 0
# the hull, the station and the grapple fixtures accept bit 1 and offer none, so the arm touches them and they do not touch each other
OBSTACLE_CONTYPE = 0
OBSTACLE_CONAFFINITY = 1


class CylinderInput(mojo.UserData):
    """Radius, length and mass of a cylinder."""

    RADIUS: float
    """Radius of the cylinder."""

    LENGTH: float
    """Length of the cylinder, along its axis."""

    MASS: float
    """Mass of the cylinder."""

    CELLS: int = 8
    """Cells along each axis of the mesh's grid. More cells make a finer mesh."""

    def mesh(self, name: str) -> mojo.MeshCylinder:
        """A builtin cylinder mesh along Z, centered on the origin."""
        # a builtin mesh spans (count - 1) * spacing along each axis, so count is one more than the cells
        cells = self.CELLS
        return mojo.MeshCylinder(
            name=mojo.MeshName(name),
            count=(cells + 1, cells + 1, cells + 1),
            spacing=np.array(
                (2 * self.RADIUS / cells, 2 * self.RADIUS / cells, self.LENGTH / cells)
            ),
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
