from __future__ import annotations

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import FlexElastic2D

__all__ = ["FlexElasticity"]


class FlexElasticity(XMLModel):
    """The elasticity model is a Saint Venant-Kirchhoff model discretized with piecewise linear finite elements, intended to simulate the compression or elongation of hyperelastic materials subjected to large displacements (finite rotations) and small strains, since it uses a nonlinear strain-displacement but a linear stress-strain relationship.. See also deformable objects."""

    tag = "elasticity"

    attributes = (
        "young",
        "poisson",
        "damping",
        "thickness",
        "elastic2d",
    )

    young: float = 0
    """Young's elastic modulus, a measure of tensile and compressive stiffness for continuum elastic materials. Units of pressure=force/areapressure=force/area."""

    poisson: float = 0
    """Poisson's ratio, the ratio of transverse deformation to applied longitudinal strain. This unitless quantity is in the range [0,0.5)[0,0.5). Small or large values imply compressibility or incompressiblity, respectively."""

    damping: float = 0
    """Rayleigh's damping coefficient, units of time. This quantity scales the stiffness defined by Young's modulus to produce the damping matrix."""

    thickness: float = -1
    """Shell thickness, units of length; only for used 2D flexes. Used to scale the stretching stiffness. This thickness can be set equal to 2 times the radius in order to match the geometry, but is exposed separately since the radius might be constrained by considerations related to collision detection."""

    elastic2d: FlexElastic2D = FlexElastic2D.NONE
    """Elastic contribution to passive forces of 2D flexes. "none": none, "bend": bending only, "stretch": stretching only, "both": bending and stretching."""
