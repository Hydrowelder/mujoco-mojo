from __future__ import annotations

from enum import StrEnum, auto
from typing import Annotated, Tuple

from numpydantic import NDArray, Shape
from pydantic import Field

__all__ = ["Vec2", "Vec3", "Vec4", "Vec5", "GeomType", "Integrator"]

MaterialName = str
"""Alias of string. Used to type hint a field is the name of a Material."""

TextureName = str
"""Alias of string. Used to type hint a field is the name of a Texture."""

ActuatorGroup = Annotated[int, Field(ge=0, le=30)]
"""An integer representing an actuator group index. Must be between 0 and 30 inclusive."""

GeomGroup = Annotated[int, Field(ge=0, le=30)]
"""An integer representing a geom group index. Must be between 0 and 30 inclusive."""

InertiaGroupRange = Tuple[GeomGroup, GeomGroup]
"""A tuple specifying the inclusive range of geom groups used for inertia computation."""

Vec2 = Annotated[NDArray[Shape["2"], float | int], ...]
"""A 2-element numeric array."""

Vec3 = Annotated[NDArray[Shape["3"], float | int], ...]
"""A 3-element numeric array, often used for positions or directions."""

Vec4 = Annotated[NDArray[Shape["4"], float | int], ...]
"""A 4-element numeric array, often used for RGBA colors or quaternions."""

Vec5 = Annotated[NDArray[Shape["5"], float | int], ...]
"""A 5-element numeric array."""

Vec6 = Annotated[NDArray[Shape["6"], float | int], ...]
"""A 6-element numeric array."""

VecN = Annotated[NDArray[Shape["*"], float | int], ...]  # type: ignore  # noqa: F722
"""An N-element numeric array of arbitrary length."""


class GeomType(StrEnum):
    """Enumeration of supported geometric types in MuJoCo."""

    PLANE = auto()
    HFIELD = auto()
    SPHERE = auto()
    CAPSULE = auto()
    ELLIPSOID = auto()
    CYLINDER = auto()
    BOX = auto()
    MESH = auto()
    SDF = auto()


class Integrator(StrEnum):
    """Enumeration of simulation integrators."""

    EULER = "Euler"
    """Semi-implicit with implicit joint damping (Euler).

    For this method, DD only includes derivatives of joint damping. Note that in this case DD is diagonal and Mhat is symmetric, so LT L decomposition (a variant of Cholesky) can be used. This factorization is stored mjData.qLD. If the model has no joint damping or the eulerdamp disable-flag is set, implicit damping is disabled and the semi-implicit update (3) is used, rather than (6), avoiding the additional factorization of Mhat (additional because MM is already factorized for the acceleration update (5))."""

    RK4 = "RK4"
    """4th-order Runge-Kutta (RK4).

    One advantage of our continuous-time formulation is that we can use higher order integrators such as Runge-Kutta or multistep methods. The only such integrator currently implemented is the fixed-step 4th-order Runge-Kutta method, though users can easily implement other integrators by calling mj_forward and integrating accelerations themselves. We have observed that for energy-conserving systems (example), RK4 is qualitatively better than the single-step methods, both in terms of stability and accuracy, even when the timestep is decreased by a factor of 4 (so the computational effort is identical). In the presence of large velocity- dependent forces, if the chosen single-step method integrates those forces implicitly, single-step methods can be significantly more stable than RK4.
    """
    IMPLICIT = "implicit"
    """Implicit-in-velocity (implicit).

    For this method, D includes derivatives of all forces except the constraint forces JTf(v). These are currently ignored since even though computing them is possible, it is complicated, and numerical tests show that including them does not confer much benefit. That said, analytical derivatives of constraint forces are planned for a future version. Additionally, we restrict D to have the same sparsity pattern as M, for computational efficiency. This restriction will exclude damping in tendons which connect bodies that are on different branches of the kinematic tree. Since D is not symmetric, we cannot use Cholesky factorization, but because D and M have the same sparsity pattern corresponding to the topology of the kinematic tree, reverse-order LU factorization of Mhat is guaranteed to have no fill-in. This factorization is stored mjData.qLU.
    """

    IMPLICITFAST = "implicitfast"
    """Fast implicit-in-velocity (implicitfast).

    For this method, DD includes derivatives of all forces used in the implicit method, with the exception of the centripetal and Coriolis forces c(v) computed by the RNE algorithm. Additionally, it is symmetrized D←(D+DT)/2. One reason for dropping the RNE derivatives is that they are the most expensive to compute. Second, these forces change rapidly only at high rotational velocities of complex pendula and spinning bodies, scenarios which are not common and already well-handled by the Runge-Kutta integrator (see below). Because the RNE derivatives are also the main source of asymmetry of D, by dropping them and symmetrizing, we can use the faster LTL rather than LU decomposition.
    """


class Cone(StrEnum):
    """Cone types used in collision/contact modeling."""

    PYRAMIDAL = auto()
    """Sometimes make the solver faster and more robust."""

    ELLIPTIC = auto()
    """Better model of the physical reality."""


class Jacobian(StrEnum):
    """Jacobian computation methods."""

    DENSE = auto()
    """Dense jacobian."""

    SPARSE = auto()
    """Sparse jacobian."""

    AUTO = auto()
    """Resolves to dense when the number of degrees of freedom is up to 60, and sparse over 60."""


class Solver(StrEnum):
    """Solver algorithms for constraint resolution."""

    PGS = "PGS"
    """Projected Gauss-Seidel method.

    This is the most common algorithm used in physics simulators, and used to be the default in MuJoCo, until we developed the Newton method which appears to be better in every way. PGS uses the dual formulation. Unlike gradient-based methods which improve the solution along oblique directions, Gauss-Seidel works on one scalar component at a time, and sets it to its optimal value given the current values of all other components. One sweep of PGS has the computational complexity of one matrix-vector multiplication (although the constants are larger). It has first-order convergence but nevertheless makes rapid progress in a few iterations."""

    CG = "CG"
    """Conjugate gradient method.

    This algorithm uses the non-linear conjugate gradient method with the Polak-Ribiere-Plus formula. Line-search is exact, using Newton's method in one dimension, with analytical second derivatives.
    """

    NEWTON = "Newton"
    """Newton's method.

    This algorithm implements the exact Newton method, with analytical second-order derivatives and Cholesky factorization of the Hessian. The line-search is the same as in the CG method. It is the default solver.
    """


class EnableDisable(StrEnum):
    """Enable or disable a feature."""

    ENABLE = auto()
    """Enable the feature."""

    DISABLE = auto()
    """Disable the feature."""


class Coordinate(StrEnum):
    """In previous versions, this attribute could be used to specify whether frame positions and orientations are expressed in local or global coordinates, but the "global" option has since been removed, and will cause an error to be generated. In order to convert older models which used the "global" option, load and save them in MuJoCo 2.3.3 or older."""

    LOCAL = auto()
    GLOBAL = auto()


class Angle(StrEnum):
    """This attribute specifies whether the angles in the MJCF model are expressed in units of degrees or radians. The compiler converts degrees into radians, and mjModel always uses radians. For URDF models the parser sets this attribute to "radian" internally, regardless of the XML setting."""

    RADIAN = auto()
    DEGREE = auto()


class InertiaFromGeom(StrEnum):
    """This attribute controls the automatic inference of body masses and inertias from geoms attached to the body."""

    FALSE = auto()
    """No automatic inference is performed. In that case each body must have explicitly defined mass and inertia with the inertial element, or else a compile error will be generated."""

    TRUE = auto()
    """The mass and inertia of each body will be inferred from the geoms attached to it, overriding any values specified with the inertial element."""

    AUTO = auto()
    """Masses and inertias are inferred automatically only when the inertial element is missing in the body definition."""


class Mode(StrEnum):
    """Determines the type of actuators to which length range computation is applied."""

    NONE = auto()
    """Disables this functionality."""

    MUSCLE = auto()
    """Applies to actuators whose gaintype or biastype is set to `muscle`"""

    MUSCLEUSER = auto()
    """Applies to actuators whose gaintype or biastype is set to either `muscle` or `user`."""

    ALL = auto()
    """Applies to all actuators."""


class Inertia(StrEnum):
    """This attribute controls how the mesh is used when mass and inertia are inferred from geometry. The current default value legacy will be changed to convex in a future release."""

    CONVEX = auto()
    """Use the mesh's convex hull to compute volume and inertia, assuming uniform density."""

    EXACT = auto()
    """Compute volume and inertia exactly, even for non-convex meshes. This algorithm requires a well-oriented, watertight mesh and will error otherwise."""

    LEGACY = auto()
    """Use the legacy algorithm, leads to volume overcounting for non-convex meshes. Though currently the default to avoid breakages, it is not recommended."""

    SHELL = auto()
    """Assume mass is concentrated on the surface of the mesh. Use the mesh's surface to compute the inertia, assuming uniform surface density."""


class Type(StrEnum):
    """This attribute determines how the texture is represented and mapped to objects. It also determines which of the remaining attributes are relevant."""

    D2 = "2d"
    """Maps a 2D image to a 3D object using texture coordinates (a.k.a UV coordinates). However, UV coordinates are only available for meshes."""

    CUBE = "cube"
    """Has the effect of shrink-wrapping a texture cube over an object. Apart from the adjustment provided by the texuniform attribute of material, the process is automatic."""

    SKYBOX = "skybox"
    """Very similar to cube mapping, and in fact the texture data is specified in exactly the same way. The only difference is that the visualizer uses the first such texture defined in the model to render a skybox."""


class ColorSpace(StrEnum):
    """This attribute determines the color space of the texture. The default value auto means that the color space will be determined from the image file itself. If no color space is defined in the file, then linear is assumed."""

    AUTO = auto()
    """Color space will be determined from the image file itself. If no color space is defined in the file, then linear is assumed."""

    LINEAR = auto()
    """Linear color space."""

    SRGB = auto()
    """SRGB color space."""


class TextureBuiltIn(StrEnum):
    """This and the remaining attributes control the generation of procedural textures. If the value of this attribute is different from "none", the texture is treated as procedural and any file names are ignored."""

    NONE = auto()
    """No builtin texture."""

    GRADIENT = auto()
    """Generates a color gradient from rgb1 to rgb2. The interpolation in color space is done through a sigmoid function. For cube and skybox textures the gradient is along the +Y axis, i.e., from top to bottom for skybox rendering."""

    CHECKER = auto()
    """Generates a 2-by-2 checker pattern with alternating colors given by rgb1 and rgb2. This is suitable for rendering ground planes and also for marking objects with rotational symmetries. Note that 2d textures can be scaled so as to repeat the pattern as many times as necessary. For cube and skybox textures, the checker pattern is painted on each side of the cube."""

    FLAT = auto()
    """Fills the entire texture with rgb1, except for the bottom face of cube and skybox textures which is filled with rgb2."""


class Mark(StrEnum):
    """Procedural textures can be marked with the markrgb color, on top of the colors determined by the builtin type. All markings are one-pixel wide, thus the markings appear larger and more diffuse on smaller textures."""

    NONE = auto()
    """No marks."""

    EDGE = auto()
    """Edges of all texture images are marked."""

    CROSS = auto()
    """A cross is marked in the middle of each image."""

    RANDOM = auto()
    """Randomly chosen pixels are marked."""


"""Sleep policy for the tree under this body. This attribute is only supported by moving bodies which are the root of a kinematic tree. For the default auto, the compiler will set the sleep policy as follows:

    * A tree which is affected by actuators is not allowed to sleep (overridable).
    * Trees which are connected by tendons which have non-zero stiffness and damping are not allowed to sleep (overridable).
    * Trees which are connected by tendons which connect more than two trees are not allowed to sleep (not overridable).
    * flexes are not allowed to sleep (not overridable).
    * All other trees are allowed to sleep (overridable).

    The policies never and allowed constitute user overrides of the automatic compiler policy.

    The init sleep policy can only be specified by the user and means "initialize this tree as asleep". This policy is implemented in mj_resetData and mj_makeData and only applies to the default configuration. If a keyframe changes the configuration of (or assigns nonzero velocity to) a sleeping tree, it will be woken up. This policy is useful for very large models where waiting for the automatic sleeping mechanism to kick in can be expensive. Trees initialized as sleeping can be placed in unstable configurations like deep penetration or in mid-air, but will only move when woken up. Also note that this policy can fail. For example if a tree marked as sleep="init" is in contact with a tree not marked as such (i.e., they are in the same island) then it is impossible to put the tree to sleep; such models will lead to a compilation error.

    See implementation notes for more details."""


class Sleep(StrEnum):
    """Sleep policy for the tree under this body. This attribute is only supported by moving bodies which are the root of a kinematic tree."""

    AUTO = auto()
    """Compiler will set the sleep policy as follows:

    * A tree which is affected by actuators is not allowed to sleep (overridable).
    * Trees which are connected by tendons which have non-zero stiffness and damping are not allowed to sleep (overridable).
    * Trees which are connected by tendons which connect more than two trees are not allowed to sleep (not overridable).
    * flexes are not allowed to sleep (not overridable).
    * All other trees are allowed to sleep (overridable)."""

    NEVER = auto()
    """Constitute user overrides of the automatic compiler policy."""

    ALLOWED = auto()
    """Constitute user overrides of the automatic compiler policy."""

    INIT = auto()
    """Can only be specified by the user and means "initialize this tree as asleep". This policy is implemented in mj_resetData and mj_makeData and only applies to the default configuration. If a keyframe changes the configuration of (or assigns nonzero velocity to) a sleeping tree, it will be woken up. This policy is useful for very large models where waiting for the automatic sleeping mechanism to kick in can be expensive. Trees initialized as sleeping can be placed in unstable configurations like deep penetration or in mid-air, but will only move when woken up. Also note that this policy can fail. For example if a tree marked as sleep="init" is in contact with a tree not marked as such (i.e., they are in the same island) then it is impossible to put the tree to sleep; such models will lead to a compilation error."""


class JointType(StrEnum):
    """Types of joints supported in MuJoCo."""

    FREE = auto()
    """Free "joint" with three translational degrees of freedom followed by three rotational degrees of freedom. In other words it makes the body floating. The rotation is represented as a unit quaternion. This joint type is only allowed in bodies that are children of the world body. No other joints can be defined in the body if a free joint is defined. Unlike the remaining joint types, free joints do not have a position within the body frame. Instead the joint position is assumed to coincide with the center of the body frame. Thus at runtime the position and orientation data of the free joint correspond to the global position and orientation of the body frame. Free joints cannot have limits."""

    BALL = auto()
    """A ball joint with three rotational degrees of freedom. The rotation is represented as a unit quaternion. The quaternion (1,0,0,0) corresponds to the initial configuration in which the model is defined. Any other quaternion is interpreted as a 3D rotation relative to this initial configuration. The rotation is around the point defined by the pos attribute. If a body has a ball joint, it cannot have other rotational joints (ball or hinge). Combining ball joints with slide joints in the same body is allowed."""

    SLIDE = auto()
    """A sliding or prismatic joint with one translational degree of freedom. Such joints are defined by a position and a sliding direction. For simulation purposes only the direction is needed; the joint position is used for rendering purposes."""

    HINGE = auto()
    """A hinge joint with one rotational degree of freedom. The rotation takes place around a specified axis through a specified position. This is the most common type of joint and is therefore the default. Most models contain only hinge and free joints."""


class Limited(StrEnum):
    """Specifies if the joint has limits."""

    FALSE = auto()
    """Joint limits are disabled."""

    TRUE = auto()
    """Joint limits are enabled."""

    AUTO = auto()
    """Joint limits will be enabled if range is defined (if autolimits is set in compiler)."""


class ActuatorFrcLimited(StrEnum):
    """This attribute specifies whether actuator forces acting on the joint should be clamped. See Force limits for details. It is available only for scalar joints (hinge and slider) and ignored for ball and free joints."""

    FALSE = auto()
    """Actuator force clamping is disabled."""

    TRUE = auto()
    """Actuator force clamping is enabled."""

    AUTO = auto()
    """Actuator force clamping will be enabled if actuatorfrcrange is defined (if autolimits is set in compiler)."""


class Align(StrEnum):
    """Specifies alignment options for aligning body frame and free joint."""

    FALSE = auto()
    """No alignment will occur between the body frame and free joint."""

    TRUE = auto()
    """Body frame and free joint will automatically be aligned with inertial frame."""

    AUTO = auto()
    """Compiler's alignfree global attribute will be respected."""


class FluidShape(StrEnum):
    """Geometry-level fluid interaction model."""

    NONE = auto()
    """I have no clue."""  # BUG Gable (1/30/2026) - if you know let me know thx

    ELLIPSOID = auto()
    """Activates the geom-level fluid interaction model based on an ellipsoidal approximation of the geom shape. When active, the model based on body inertia sizes is disabled for the body in which the geom is defined. See section on ellipsoid-based fluid interaction model for details."""
