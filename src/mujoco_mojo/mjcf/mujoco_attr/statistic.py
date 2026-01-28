from __future__ import annotations

from typing import Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.types import Vec3

__all__ = ["Statistic"]


class Statistic(XMLModel):
    """This element is used to override model statistics computed by the compiler. These statistics are not only informational but are also used to scale various components of the rendering and perturbation. We provide an override mechanism in the XML because it is sometimes easier to adjust a small number of model statistics than a larger number of visual parameters."""

    tag = "statistic"

    attributes = (
        "meaninertia",
        "meanmass",
        "meansize",
        "extent",
        "center",
    )

    meanmass: Optional[float] = None
    """If this attribute is specified, it replaces the value of mjModel.stat.meanmass computed by the compiler. The computed value is the average body mass, not counting the massless world body. At runtime this value scales the perturbation force."""
    meaninertia: Optional[float] = None
    """If this attribute is specified, it replaces the value of mjModel.stat.meaninertia computed by the compiler. The computed value is the average diagonal element of the joint-space inertia matrix when the model is in qpos0. At runtime this value scales the solver cost and gradient used for early termination."""
    meansize: Optional[float] = None
    """If this attribute is specified, it replaces the value of mjModel.stat.meansize computed by the compiler. At runtime this value multiplies the attributes of the scale element above, and acts as their length unit. If specific lengths are desired, it can be convenient to set meansize to a round number like 1 or 0.01 so that scale values are in recognized length units. This is the only semantic of meansize and setting it has no other side-effect. The automatically computed value is heuristic, representing the average body radius. The heuristic is based on geom sizes when present, the distances between joints when present, and the sizes of the body equivalent inertia boxes."""
    extent: Optional[float] = None
    """If this attribute is specified, it replaces the value of mjModel.stat.extent computed by the compiler. The computed value is half the side of the bounding box of the model in the initial configuration. At runtime this value is multiplied by some of the attributes of the map element above. When the model is first loaded, the free camera’s initial distance from the center (see below) is 1.5 times the extent. Must be strictly positive."""
    center: Optional[Vec3] = None
    """If this attribute is specified, it replaces the value of mjModel.stat.center computed by the compiler. The computed value is the center of the bounding box of the entire model in the initial configuration. This 3D vector is used to center the view of the free camera when the model is first loaded."""


if __name__ == "__main__":
    import numpy as np

    x = Statistic(center=np.array([1.0, 2, 3]))
    breakpoint()
