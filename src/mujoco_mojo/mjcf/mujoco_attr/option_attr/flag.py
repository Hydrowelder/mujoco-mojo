from __future__ import annotations

from typing import Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.types import EnableDisable

__all__ = ["Flag"]


class Flag(XMLModel):
    """This element sets the flags that enable and disable different parts of the simulation pipeline. The actual flags used at runtime are represented as the bits of two integers, namely mjModel.opt.disableflags and mjModel.opt.enableflags, used to disable standard features and enable optional features respectively. The reason for this separation is that setting both integers to 0 restores the default. In the XML we do not make this separation explicit, except for the default attribute values - which are "enable" for flags corresponding to standard features, and "disable" for flags corresponding to optional features. In the documentation below, we explain what happens when the setting is different from its default."""

    tag = "flag"

    attributes = (
        "constraint",
        "equality",
        "frictionloss",
        "limit",
        "contact",
        "spring",
        "damping",
        "gravity",
        "clampctrl",
        "warmstart",
        "filterparent",
        "actuation",
        "refsafe",
        "sensor",
        "midphase",
        "eulerdamp",
        "autoreset",
        "nativeccd",
        "island",
        "override",
        "energy",
        "fwdinv",
        "invdiscrete",
        "multiccd",
        "sleep",
    )

    constraint: Optional[EnableDisable] = None
    """This flag disables all standard computations related to the constraint solver. As a result, no constraint forces are applied. Note that the next four flags disable the computations related to a specific type of constraint. Both this flag and the type-specific flag must be set to "enable" for a given computation to be performed."""
    equality: Optional[EnableDisable] = None
    """This flag disables all standard computations related to equality constraints."""
    frictionloss: Optional[EnableDisable] = None
    """This flag disables all standard computations related to friction loss constraints."""
    limit: Optional[EnableDisable] = None
    """This flag disables all standard computations related to joint and tendon limit constraints."""
    contact: Optional[EnableDisable] = None
    """This flag disables collision detection and all standard computations related to contact constraints."""
    spring: Optional[EnableDisable] = None
    """This flag disables passive joint and tendon springs. If passive damper forces are also disabled, all passive forces are disabled, including gravity compensation, fluid forces, forces computed by the mjcb_passive callback, and forces computed by plugins when passed the mjPLUGIN_PASSIVE capability flag."""
    damping: Optional[EnableDisable] = None
    """This flag disables passive joint and tendon dampers. If passive spring forces are also disabled, all passive forces are disabled, including gravity compensation, fluid forces, forces computed by the mjcb_passive callback, and forces computed by plugins when passed the mjPLUGIN_PASSIVE capability flag."""
    gravity: Optional[EnableDisable] = None
    """This flag causes the gravitational acceleration vector in mjOption to be replaced with (0 0 0) at runtime, without changing the value in mjOption. Once the flag is re-enabled, the value in mjOption is used."""
    clampctrl: Optional[EnableDisable] = None
    """This flag disables the clamping of control inputs to all actuators, even if the actuator-specific attributes are set to enable clamping."""
    warmstart: Optional[EnableDisable] = None
    """This flag disables warm-starting of the constraint solver. By default the solver uses the solution (i.e., the constraint force) from the previous time step to initialize the iterative optimization. This feature should be disabled when evaluating the dynamics at a collection of states that do not form a trajectory - in which case warm starts make no sense and are likely to slow down the solver."""
    filterparent: Optional[EnableDisable] = None
    """This flag disables the filtering of contact pairs where the two geoms belong to a parent and child body; recall contact selection in the Computation chapter."""
    actuation: Optional[EnableDisable] = None
    """This flag disables all standard computations related to actuator forces, including the actuator dynamics. As a result, no actuator forces are applied to the simulation."""
    refsafe: Optional[EnableDisable] = None
    """This flag enables a safety mechanism that prevents instabilities due to solref[0] being too small compared to the simulation timestep. Recall that solref[0] is the stiffness of the virtual spring-damper used for constraint stabilization. If this setting is enabled, the solver uses max(solref[0], 2*timestep) in place of solref[0] separately for each active constraint."""
    sensor: Optional[EnableDisable] = None
    """This flag disables all computations related to sensors. When disabled, sensor values will remain constant, either zeros if disabled at the start of simulation, or, if disabled at runtime, whatever value was last computed."""
    midphase: Optional[EnableDisable] = None
    """This flag disables the mid-phase collision filtering using a static AABB bounding volume hierarchy (a BVH binary tree). If disabled, all geoms pairs that are allowed to collide are checked for collisions."""
    nativeccd: Optional[EnableDisable] = None
    """This flag enables the native convex collision detection pipeline instead of using the libccd library, see convex collisions for more details."""
    island: Optional[EnableDisable] = None
    """This flag enables discovery and construction of constraint islands: disjoint sets of constraints and degrees-of-freedom that do not interact and can be solved independently. Islanding is not yet supported by the PGS solver. See Constraint islands for more details. The mjVIS_ISLAND enables island visualization."""
    eulerdamp: Optional[EnableDisable] = None
    """This flag disables implicit integration with respect to joint damping in the Euler integrator. See the Numerical Integration section for more details."""
    autoreset: Optional[EnableDisable] = None
    """This flag disables the automatic resetting of the simulation state when numerical issues are detected."""
    override: Optional[EnableDisable] = None
    """This flag enables the Contact override mechanism."""
    energy: Optional[EnableDisable] = None
    """This flag enables the computation of potential and kinetic energy in mjData.energy[0, 1] respectively, and displayed in the simulate GUI info overlay. Potential energy includes the gravitational component summed over all bodies and energy stored in passive springs in joints, tendons and flexes. Note that potential and kinetic energy in constraints is not accounted for.

    The extra computation (also triggered by potential and kinetic energy sensors) adds some CPU time but it is usually negligible. Monitoring energy for a system that is supposed to be energy-conserving is one of the best ways to assess the accuracy of a complex simulation."""
    fwdinv: Optional[EnableDisable] = None
    """This flag enables the automatic comparison of forward and inverse dynamics. When enabled, the inverse dynamics is invoked after mj_forward (or internally within mj_step) and the difference in applied forces is recorded in mjData.solver_fwdinv[2]. The first value is the relative norm of the discrepancy in joint space, the next is in constraint space."""
    invdiscrete: Optional[EnableDisable] = None
    """This flag enables discrete-time inverse dynamics with mj_inverse for all integrators other than RK4. Recall from the numerical integration section that the one-step integrators (Euler, implicit and implicitfast), modify the mass matrix M -> M-hD. This implies that finite-differenced accelerations (v_(t+h)-v_t)/h will not correspond to the continuous-time acceleration mjData.qacc. When this flag is enabled, mj_inverse will interpret qacc as having been computed from the difference of two sequential velocities, and undo the above modification."""
    multiccd: Optional[EnableDisable] = None
    """This flag enables multiple-contact collision detection for geom pairs that use a general-purpose convex-convex collider e.g., mesh-mesh collisions. This can be useful when the contacting geoms have a flat surface and the single contact point generated by the convex-convex collider cannot accurately capture the surface contact, leading to instabilities that typically manifest as sliding or wobbling. The implementation of this feature depends on the selected convex collision pipeline, see convex collisions for more details."""
    sleep: Optional[EnableDisable] = None
    """This flag enables sleeping. Disabling this flag when some trees are sleeping will wake them."""
