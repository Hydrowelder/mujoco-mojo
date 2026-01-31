from __future__ import annotations

from typing import Optional, Set

import numpy as np

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.defaults import FRICTION_DEFAULT, SOLIMP_DEFAULT, SOLREF_DEFAULT
from mujoco_mojo.mjcf.mujoco_attr.option_attr.flag import Flag
from mujoco_mojo.typing import (
    ActuatorGroup,
    Cone,
    Integrator,
    Jacobian,
    Solver,
    Vec2,
    Vec3,
    Vec5,
)

__all__ = ["Option"]


class Option(XMLModel):
    """This element is in one-to-one correspondence with the low level structure mjOption contained in the field mjModel.opt of mjModel. These are simulation options and do not affect the compilation process in any way; they are simply copied into the low level model. Even though mjOption can be modified by the user at runtime, it is nevertheless a good idea to adjust it properly through the XML."""

    tag = "option"

    attributes = (
        "timestep",
        "impratio",
        "tolerance",
        "ls_tolerance",
        "noslip_tolerance",
        "ccd_tolerance",
        "sleep_tolerance",
        "gravity",
        "wind",
        "magnetic",
        "density",
        "viscosity",
        "o_margin",
        "o_solref",
        "o_solimp",
        "o_friction",
        "integrator",
        "cone",
        "jacobian",
        "solver",
        "iterations",
        "ls_iterations",
        "noslip_iterations",
        "ccd_iterations",
        "sdf_iterations",
        "sdf_initpoints",
        "actuatorgroupdisable",
    )
    children = ("flag",)

    timestep: float = 0.002
    """Simulation time step in seconds. This is the single most important parameter affecting the speed-accuracy trade-off which is inherent in every physics simulation. Smaller values result in better accuracy and stability. To achieve real-time performance, the time step must be larger than the CPU time per step (or 4 times larger when using the RK4 integrator). The CPU time is measured with internal timers. It should be monitored when adjusting the time step. MuJoCo can simulate most robotic systems a lot faster than real-time, however models with many floating objects (resulting in many contacts) are more demanding computationally. Keep in mind that stability is determined not only by the time step but also by the Solver parameters; in particular softer constraints can be simulated with larger time steps. When fine-tuning a challenging model, it is recommended to experiment with both settings jointly. In optimization-related applications, real-time is no longer good enough and instead it is desirable to run the simulation as fast as possible. In that case the time step should be made as large as possible."""

    impratio: float = 1
    """This attribute determines the ratio of frictional-to-normal constraint impedance for elliptic friction cones. The setting of solimp determines a single impedance value for all contact dimensions, which is then modulated by this attribute. Settings larger than 1 cause friction forces to be "harder" than normal forces, having the general effect of preventing slip, without increasing the actual friction coefficient. For pyramidal friction cones the situation is more complex because the pyramidal approximation mixes normal and frictional dimensions within each basis vector; it is not recommended to use high impratio values with pyramidal cones."""

    gravity: Vec3 = np.array((0, 0, -9.81))
    """Gravitational acceleration vector. In the default world orientation the Z-axis points up. The MuJoCo GUI is organized around this convention (both the camera and perturbation commands are based on it) so we do not recommend deviating from it."""

    wind: Vec3 = np.array((0, 0, 0))
    """Velocity vector of the medium (i.e., wind). This vector is subtracted from the 3D translational velocity of each body, and the result is used to compute viscous, lift and drag forces acting on the body; recall Passive forces in the Computation chapter. The magnitude of these forces scales with the values of the next two attributes."""

    magnetic: Vec3 = np.array((0, -0.5, 0))
    """Global magnetic flux. This vector is used by magnetometer sensors, which are defined as sites and return the magnetic flux at the site position expressed in the site frame."""

    density: float = 0
    """Density of the medium, not to be confused with the geom density used to infer masses and inertias. This parameter is used to simulate lift and drag forces, which scale quadratically with velocity. In SI units the density of air is around 1.2 while the density of water is around 1000 depending on temperature. Setting density to 0 disables lift and drag forces."""

    viscosity: float = 0
    """Viscosity of the medium. This parameter is used to simulate viscous forces, which scale linearly with velocity. In SI units the viscosity of air is around 0.00002 while the viscosity of water is around 0.0009 depending on temperature. Setting viscosity to 0 disables viscous forces. Note that the default Euler integrator handles damping in the joints implicitly - which improves stability and accuracy. It does not presently do this with body viscosity. Therefore, if the goal is merely to create a damped simulation (as opposed to modeling the specific effects of viscosity), we recommend using joint damping rather than body viscosity, or switching to the implicit or implicitfast integrators."""

    o_margin: float = 0
    """This attribute replaces the margin parameter of all active contact pairs when Contact override is enabled. Otherwise MuJoCo uses the element-specific margin attribute of geom or pair depending on how the contact pair was generated. See also Collision detection in the Computation chapter. The related gap parameter does not have a global override."""

    o_solref: Vec2 = SOLREF_DEFAULT
    """These attributes replace the solref parameters of all active contact pairs when contact override is enabled. See Solver parameters for details."""

    o_solimp: Vec5 = SOLIMP_DEFAULT
    """These attributes replace the solimp parameters of all active contact pairs when contact override is enabled. See Solver parameters for details."""

    o_friction: Vec3 = FRICTION_DEFAULT
    """These attributes replace the friction parameters of all active contact pairs when contact override is enabled. See Solver parameters for details."""

    integrator: Integrator = Integrator.EULER
    """This attribute selects the numerical integrator to be used. Currently the available integrators are the semi-implicit Euler method, the fixed-step 4-th order Runge Kutta method, the Implicit-in-velocity Euler method, and implicitfast, which drops the Coriolis and centrifugal terms. See Numerical Integration for more details."""

    cone: Cone = Cone.PYRAMIDAL
    """The type of contact friction cone. Elliptic cones are a better model of the physical reality, but pyramidal cones sometimes make the solver faster and more robust."""

    jacobian: Jacobian = Jacobian.AUTO
    """The type of constraint Jacobian and matrices computed from it. Auto resolves to dense when the number of degrees of freedom is up to 60, and sparse over 60."""

    solver: Solver = Solver.NEWTON
    """This attribute selects one of the constraint solver algorithms described in the Computation chapter. Guidelines for solver selection and parameter tuning are available in the Algorithms section above."""

    iterations: int = 100
    """Maximum number of iterations of the constraint solver. When the warmstart attribute of flag is enabled (which is the default), accurate results are obtained with fewer iterations. Larger and more complex systems with many interacting constraints require more iterations. Note that mjData.solver contains statistics about solver convergence, also shown in the profiler."""

    tolerance: float = 1e-8
    """Tolerance threshold used for early termination of the iterative solver. For PGS, the threshold is applied to the cost improvement between two iterations. For CG and Newton, it is applied to the smaller of the cost improvement and the gradient norm. Set the tolerance to 0 to disable early termination."""

    ls_iterations: int = 50
    """Maximum number of linesearch iterations performed by CG/Newton constraint solvers. Ensures that at most iterations times ls_iterations linesearch iterations are performed during each constraint solve."""

    ls_tolerance: float = 0.01
    """Tolerance threshold used for early termination of the linesearch algorithm."""

    noslip_iterations: int = 0
    """Maximum number of iterations of the Noslip solver. This is a post-processing step executed after the main solver. It uses a modified PGS method to suppress slip/drift in friction dimensions resulting from the soft-constraint model. The default setting 0 disables this post-processing step."""

    noslip_tolerance: float = 1e-6
    """Tolerance threshold used for early termination of the Noslip solver."""

    ccd_iterations: int = 50
    """Maximum number of iterations of the algorithm used for convex collisions. This rarely needs to be adjusted, except in situations where some geoms have very large aspect ratios."""

    ccd_tolerance: float = 1e-6
    """Tolerance threshold used for early termination of the convex collision algorithm."""

    sleep_tolerance: float = 1e-4
    """Velocity tolerance below which sleeping is allowed."""

    sdf_iterations: int = 10
    """Number of iterations used for Signed Distance Field collisions (per initial point)."""

    sdf_initpoints: int = 40
    """Number of starting points used for finding contacts with Signed Distance Field collisions."""

    actuatorgroupdisable: Optional[Set[ActuatorGroup]] = None
    """List of actuator groups to disable. Actuators whose group is in this list will produce no force. If they are stateful, their activation states will not be integrated. Internally this list is implemented as an integer bitfield, so values must be in the range 0 <= group <= 30. If not set, all actuator groups are enabled. See example model and associated screen-capture on the right."""

    flag: Flag = Flag()
