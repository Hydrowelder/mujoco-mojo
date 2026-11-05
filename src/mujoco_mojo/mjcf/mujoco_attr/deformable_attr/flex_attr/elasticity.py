from __future__ import annotations

import numpy as np

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import FlexElastic2D, FlexSection, Vec2

__all__ = ["FlexElasticity"]


class FlexElasticity(XMLModel):
    """
    The elasticity model is a Saint Venant-Kirchhoff model discretized with piecewise linear finite elements, intended to simulate the compression or elongation of hyperelastic materials subjected to large displacements (finite rotations) and small strains, since it uses a nonlinear strain-displacement but a linear stress-strain relationship.. See also deformable objects.

    For 1D flexes, elasticity is a twist-free, isotropic discrete elastic rod bending model with the cross-section given by section. Every vertex shared by exactly two edges stores the energy `k * |κ * b|^2`, where κb is the discrete curvature binormal and `k=EI/(l_0+l_1)`, with II the second moment of area of the cross-section and `l_0,1` the reference lengths of the two edges. The reference configuration `qpos0` must be straight: a compiler error is raised if any such vertex is bent by more than `10^-4` rad, since without material frames an isotropic rod with a curved reference would only resist the magnitude of its curvature, not its direction. A curved initial pose, e.g. coiled or draped, can be set with qpos or a keyframe; the rod then starts with stored bending energy and is pushed toward straightening. Rods with a curved rest shape, such as coil springs, can use the cable composite instead. Twist is assumed to relax instantly, which is exact unless the orientation of both ends of the rod is constrained. Stretching is not included; use edge constraints or stiffness instead. Rod bending is integrated implicitly by the discrete integrator, using a positive semi-definite approximation of its Hessian, and explicitly by all other integrators. It is not supported by dof trilinear and quadratic.
    """

    tag = "elasticity"

    attributes = (
        "young",
        "poisson",
        "shear",
        "damping",
        "thickness",
        "yield_",
        "elastic2d",
        "section",
        "sectionsize",
    )

    young: float = 0
    """Young's elastic modulus, a measure of tensile and compressive stiffness for continuum elastic materials. Units of pressure=force/areapressure=force/area."""

    poisson: float = 0
    """Poisson's ratio, the ratio of transverse deformation to applied longitudinal strain. This unitless quantity is in the range [0,0.5)[0,0.5). Small or large values imply compressibility or incompressiblity, respectively."""

    shear: float = 0
    """Shear modulus G used for the torsional stiffness of 1D flexes, units of pressure=force/area. Must be non-negative. If zero, the isotropic value `G = E / (2 (1 + nu))` is computed from young and poisson; if positive, it overrides that value. Ignored for 2D and 3D flexes."""

    damping: float = 0
    """Rayleigh's damping coefficient, units of time. This quantity scales the stiffness defined by Young's modulus to produce the damping matrix."""

    thickness: float = -1
    """Shell thickness, units of length; only for used 2D flexes. Used to scale the stretching stiffness. This thickness can be set equal to 2 times the radius in order to match the geometry, but is exposed separately since the radius might be constrained by considerations related to collision detection."""

    yield_: float | Vec2 = np.array((0, 0))
    """Dimensionless plastic yield strain thresholds for stretching and bending of 2D and 3D flexes, as `(stretching, bending)`. A mode (stretching or bending) is plastic if its threshold is positive at compile time; its plastic state is then allocated in `mjData.plastic` and the bit of the mode is set in `mjModel.flex_plasticmode[f]` (1: bending, 2: stretching). A mode whose threshold is zero has no plastic state and remains purely elastic, e.g., `(0.01, 0)` makes only stretching plastic. As for joints and tendons, setting the threshold of a plastic mode to zero at runtime in `mjModel.flex_yield` (which has two columns) corresponds to zero yield strain (full plastic flow). If the stretching threshold is positive, each element's (or interpolated cell's/face's) elastic stretching strain tensor is bounded by the von Mises (J2) yield criterion (3D isochoric in 3D, plane-stress with out-of-plane thinning in tension in 2D) via radial return mapping. If the bending threshold is positive, which requires a non-interpolated 2D flex (a compiler error otherwise), for shells with bending enabled (elastic2d `bend` or `both`), each interior hinge's outer-fiber bending strain `t/2 |dkappa_e| <= yield` is bounded via return mapping in dihedral angle space (assuming an initially flat rest configuration). For example, `(0, 0.001)` makes a shell yield in bending while its stretching remains elastic. 1D flexes do not support plasticity (both values must be zero). In `mjData.plastic` at `flex_plasticadr[f]`, a non-interpolated flex stores its stretching plastic metric offsets first (`3 * elemnum` entries in 2D or `6 * elemnum` entries in 3D when stretching is plastic), followed by `edgenum` bending plastic entries in 2D when bending is plastic. An interpolated flex with cellcount (cx, cy, cz) stores one dimensionless plastic stretching strain per grid cell (`6 * cx * cy * cz` entries in 3D) or per outer grid face in 2D shell mode (`3 * 2 * (cy*cz + cx*cz + cx*cy)` entries); the elastic strain is measured in the corotated frame of the polar decomposition of the physical deformation gradient. Bending plasticity is not supported for interpolated flexes: with elastic2d `bend`, yield is ignored and the flex remains purely elastic."""

    elastic2d: FlexElastic2D = FlexElastic2D.NONE
    """Elastic contribution to passive forces of 2D flexes. "none": none, "bend": bending only, "stretch": stretching only, "both": bending and stretching.

    Non-interpolated flex elasticity supports vertices attached to articulated bodies, including jointless welded children. A vertex pinned to a moving body follows that body's motion and applies its reaction force and torque to the body. With the `discrete` integrator, use solver `CG` for general attachments. Newton supports fixed attachments and independent slide bodies with local positive X, Y and Z joints in that order and fixed ancestors. Mocap attachments are not supported for non-rigid flexes with elasticity because mocap poses do not provide velocities for elastic damping."""

    section: FlexSection = FlexSection.CIRCLE
    """Cross-section of 1D flexes, used to compute the second moment of area I of the bending stiffness. "circle": `I = pi r^4 / 4`, where r is the flex radius. "box": rectangle with half-sizes given by `sectionsize`. Since the bending model is isotropic, a box uses the second moment of area of its weak axis, `I = min(w h^3, h w^3) / 12`, where w, h are the full sizes. Collisions and rendering always use the flex radius."""

    sectionsize: Vec2 = np.array((0, 0))
    """Half-sizes of the "box" cross-section of 1D flexes, units of length. Both values must be positive when `section` is "box"; ignored otherwise."""
