from __future__ import annotations

import numpy as np

from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import FlexElastic2D, FlexSection, Vec2

__all__ = ["FlexElasticity"]


class FlexElasticity(XMLModel):
    """
    **2D and 3D flexes** use a Saint Venant-Kirchhoff model discretized with piecewise linear finite elements, intended to simulate the compression or elongation of hyperelastic materials subjected to large displacements (finite rotations) and small strains, since it uses a nonlinear strain-displacement but a linear stress-strain relationship. See also deformable objects.

    For 3D flexes, the stretching energy density is `mu tr(eps^2) + lambda/2 tr(eps)^2`, where `eps` is the Green strain and `mu = E / (2 (1 + nu))`, `lambda = E nu / ((1 + nu) (1 - 2 nu))` are the Lamé parameters given by young `E` and poisson `nu`. For 2D flexes (shells of thickness `t`), the stretching (membrane) energy per unit area is `t` times the same density with the plane-stress parameter `lambda* = E nu / (1 - nu^2)` instead of `lambda`. The bending energy of 2D flexes is a discrete hinge model for flat references, normalized so that bending a flat sheet into a cylinder of curvature `kappa` stores the Kirchhoff plate energy `D kappa^2 / 2` per unit area, with bending rigidity `D = E t^3 / (12 (1 - nu^2))`. Poisson's ratio enters the bending energy only through `D`.

    **1D flexes** are discrete elastic rods with bending and torsion and cross-section given by section (see Rods for details):

    - **Bending:** Every interior vertex shared by two edges of reference lengths `l_0, l_1` stores bending energy `k |kappa_b - kappa_b0|^2` with stiffness `k = E I / (l_0 + l_1)`, where `kappa_b` is the discrete curvature binormal and `I` is the second moment of area of the cross-section. Vertices bent by more than `10^-4` rad in `qpos0` keep their reference curvature `kappa_b0` (so curved rods such as rings or arcs are at rest in `qpos0`); for an isolated curved vertex on a twistless circular rod, only the curvature magnitude `|kappa_b0|` is held and its bending plane is free. Less-bent vertices are treated as straight (`kappa_b0 = 0`); to start a straight rod in a bent or coiled pose with stored energy, set `qpos` or use a keyframe.
    - **Torsion:** Each vertex of a single-hinge chain has torsional stiffness `k_t = G J / (l_0 + l_1)`, while pairs of adjacent curved vertices on closed circular loops (or raw `<flex dim="1">` chains without twist joints) penalize the dihedral twist of their osculating planes across the shared edge of length `l_1` with stiffness `k_d = G J / (2 l_1)`. Here `G` is the shear modulus from shear or `G = E / (2 (1 + nu))` when shear is zero, and `J` is the Saint-Venant torsional constant of the cross-section.
    - **Per-edge twist joints and clamped vs. free ends:** For open-chain 1D elastic rods with `n >= 2` edges (both circle and box sections), flexcomp creates per-edge twist bodies and hinge joints `<name>_twist_0`, ..., `<name>_twist_{n-2}`, `<name>_twist` parented to the world body, with per-edge polar mass moment of inertia (`m_e r^2 / 2` for circle and `m_e (a^2 + b^2) / 3` for box half-sizes `a, b`) and frame-indifferent relative Rayleigh torsional damping. An edge whose two points are pinned is clamped: the first edge with `<pin id="0 1"/>`, or the last edge when the last two points of a rod with `n >= 3` edges are pinned. A clamped edge has no twist joint (`<name>_twist_0` or `<name>_twist` is omitted), and the body holding it fixes that end's material frame and receives the reaction torque of the rod. With `<pin id="0"/>` or no pin, `<name>_twist_0` remains free, and an unclamped `<name>_twist` can be actuated to twist the far end. A raw flex binds the hinge joints with these names: each unclamped edge needs one and, when the first edge is free, `<name>_twist_0` must immediately precede the joint of the second edge. Contact Jacobians couple frictional contact forces via their cross-sectional lever arm into each element's two vertices and edge twist DOF, including the velocity of the surface point due to the rotation of the element, enabling circular cables to roll on surfaces and twist in grippers. Because the per-edge twist DOFs have small polar inertia and stiff torsional coupling, the `discrete` integrator with the `CG` or `Newton` solver is recommended: it solves the tridiagonal torsional system, including the bending stiffness of each twist angle, implicitly (`PGS` is not supported with flex). Otherwise use a smaller timestep with `Euler` or `RK4`.
    - **Box sections:** For section box (requires a single open chain with at least two elements and per-edge twist joints, which flexcomp creates; a raw flex without them fails to compile), the principal bending stiffnesses `k_1,2 = E I_1,2 / (l_0 + l_1)` are anisotropic, all interior vertices carry directional reference curvature in the material frame, and bending damping uses the geometric mean `sqrt(k_1 k_2)` on the weak axis so that the damping ratio `zeta_i` proportional to `sqrt(k_i)` is equalized across both principal axes. Rendering and collisions with planes, spheres, capsules, boxes, and other 1D rods use an oriented box of half-sizes sectionsize in the DER material frame. Against other geom types (meshes, cylinders, ellipsoids, height fields) and 2D or 3D flexes, the elements collide as capsules whose radius is the minor half-size, which the compiler assigns to radius; an explicit radius that differs from it is a compile error.
    - **State:** In `mjData.plastic` at `flex_plasticadr[f]`, an open rod with per-edge twist joints (every box-section rod has them) stores `6 n + (n - 1)` numbers: the time-parallel reference frames `(t_old, u_old)` of its `n` edges, followed by the reference twist of each interior vertex, unwrapped across steps so that the twist energy stays continuous when the rod writhes or tumbles. This is not plasticity, but state snapshots must include `mjSTATE_PLASTIC` to save and restore it. Without it (after `mj_resetData` or a keyframe without plastic state), the reference frames restart from the reference frame of the first edge (following its body when clamped, or transported from `qpos0` to the current tangent when free), propagated twist-free along the rod.
    - **Limitations:** Stretching is not included; use edge equality constraints (or edge stiffness under integrators other than `discrete`) instead. Rod elasticity is integrated implicitly by `discrete` (using a positive semi-definite Hessian approximation) and explicitly by `Euler` and `RK4`; `implicit` and `implicitfast` are not supported, nor are dof trilinear and quadratic.

    Flex elasticity (both standard and interpolated) supports vertices or nodes attached to articulated bodies, including jointless welded children, under both **Newton** and **CG** with the `discrete` integrator. A vertex or node pinned to a moving body follows that body's motion and applies its reaction force and torque to the body. **Newton** is fastest when every vertex and node is fixed or sits on a body with three slide joints along the world axes: their stiffness is then assembled as 3x3 vertex blocks. Once any flex in the model has another kind of attachment, the stiffness of all its flexes is pulled back through the attachment Jacobians, which costs more per step. MuJoCo Warp does not yet support articulated attachments with **Newton**; use **CG** there. Mocap attachments are not supported for non-rigid flexes with elasticity because mocap poses do not provide velocities for elastic damping, except for 1D flexes with zero damping.
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
    """Shell thickness, units of length; only used for 2D flexes. The stretching stiffness of 2D flexes is proportional to the thickness `t` and their bending stiffness to `t^3`, see elasticity. This thickness can be set equal to 2 times the radius in order to match the geometry, but is exposed separately since the radius might be constrained by considerations related to collision detection."""

    yield_: float | Vec2 = np.array((0, 0))
    """Dimensionless plastic yield strain thresholds for stretching and bending of 2D and 3D flexes, as `(stretching, bending)`. A mode (stretching or bending) is plastic if its threshold is positive at compile time; its plastic state is then allocated in `mjData.plastic` and the bit of the mode is set in `mjModel.flex_plasticmode[f]` (1: bending, 2: stretching). A mode whose threshold is zero has no plastic state and remains purely elastic, e.g., `(0.01, 0)` makes only stretching plastic. As for joints and tendons, setting the threshold of a plastic mode to zero at runtime in `mjModel.flex_yield` (which has two columns) corresponds to zero yield strain (full plastic flow). If the stretching threshold is positive, each element's (or interpolated cell's/face's) elastic stretching strain tensor is bounded by the von Mises (J2) yield criterion (3D isochoric in 3D, plane-stress with out-of-plane thinning in tension in 2D) via radial return mapping. If the bending threshold is positive, which requires a non-interpolated 2D flex (a compiler error otherwise), for shells with bending enabled (elastic2d `bend` or `both`), each interior hinge's outer-fiber bending strain `t/2 |dkappa_e| <= yield` is bounded via return mapping in dihedral angle space (assuming an initially flat rest configuration). For example, `(0, 0.001)` makes a shell yield in bending while its stretching remains elastic. 1D flexes do not support plasticity (both values must be zero). In `mjData.plastic` at `flex_plasticadr[f]`, a non-interpolated flex stores its stretching plastic metric offsets first (`3 * elemnum` entries in 2D or `6 * elemnum` entries in 3D when stretching is plastic), followed by `edgenum` bending plastic entries in 2D when bending is plastic. An interpolated flex with cellcount (cx, cy, cz) stores one dimensionless plastic stretching strain per grid cell (`6 * cx * cy * cz` entries in 3D) or per outer grid face in 2D shell mode (`3 * 2 * (cy*cz + cx*cz + cx*cy)` entries); the elastic strain is measured in the corotated frame of the polar decomposition of the physical deformation gradient. Bending plasticity is not supported for interpolated flexes: with elastic2d `bend`, yield is ignored and the flex remains purely elastic."""

    elastic2d: FlexElastic2D = FlexElastic2D.NONE
    """Elastic contribution to passive forces of 2D flexes. "none": none, "bend": bending only, "stretch": stretching only, "both": bending and stretching. Bending is not yet supported by dof trilinear and quadratic."""

    section: FlexSection = FlexSection.CIRCLE
    """Cross-section of 1D flexes, used to compute the second moments of area `I_1, I_2` and torsional constant `J` of the bending and torsional stiffnesses. "circle": `I_1 = I_2 = pi r^4 / 4` and `J = pi r^4 / 2`, where `r` is the flex radius. "box": rectangle with half-sizes given by `sectionsize` and full sizes `w, h`, with principal second moments `I_1 = h w^3 / 12`, `I_2 = w h^3 / 12`, and Saint-Venant torsional constant `J` (requires an open chain). Both rendering and collision detection use an oriented box of half-sizes `sectionsize` in the DER material frame when `section` is "box" and a capsule of the flex radius otherwise."""

    sectionsize: Vec2 = np.array((0, 0))
    """Half-sizes of the "box" cross-section of 1D flexes, units of length. Both values must be positive when `section` is "box"; ignored otherwise. With a "box" section the flex radius is set to the minor half-size, so radius must be omitted or equal to it."""
