from __future__ import annotations

from enum import StrEnum
from typing import (
    TYPE_CHECKING,
    Annotated,
    NewType,
)

import numpy as np
from numpydantic import NDArray, Shape
from pydantic import Field

from mujoco_mojo.utils.utils import is_empty_list

__all__ = [
    "ActuatorControlLimited",
    "ActuatorForceLimited",
    "ActuatorGroup",
    "ActuatorLimited",
    "ActuatorName",
    "Align",
    "Angle",
    "BiasType",
    "BodyName",
    "CameraName",
    "CameraOutput",
    "CameraProjection",
    "ColorSpace",
    "CompositeInitial",
    "CompositeJointKind",
    "CompositeType",
    "Cone",
    "ContactExcludeName",
    "ContactPairName",
    "Coordinate",
    "DeformableSkinName",
    "DynType",
    "EnableDisable",
    "EulerSeq",
    "FlexCompDOF",
    "FlexCompType",
    "FlexName",
    "FluidShape",
    "GainType",
    "GeomGroup",
    "GeomName",
    "GeomType",
    "GridLayoutStr",
    "HFieldName",
    "Inertia",
    "InertiaFromGeom",
    "InertiaGroupRange",
    "InstanceName",
    "Integrator",
    "Jacobian",
    "JointLimited",
    "JointName",
    "JointType",
    "KeyName",
    "LayerRole",
    "LengthRangeMode",
    "LightName",
    "LightType",
    "Mark",
    "Mat2",
    "Mat3",
    "Mat4",
    "Mat5",
    "Mat6",
    "Mat7",
    "Mat9",
    "MatN",
    "MaterialName",
    "MeshName",
    "ModelName",
    "PluginName",
    "RangefinderData",
    "SensorAttachableName",
    "SensorInterp",
    "SensorName",
    "SensorObjectType",
    "SignalCategory",
    "SiteName",
    "Sleep",
    "Solver",
    "TendonLimited",
    "TendonName",
    "TextureBuiltInType",
    "TextureName",
    "TextureType",
    "TrackingMode",
    "Vec2",
    "Vec3",
    "Vec4",
    "Vec5",
    "Vec6",
    "Vec7",
    "Vec9",
    "VecN",
]

MeshName = NewType("MeshName", str)
"""Alias of string. Used to type hint a field is the name of a Mesh."""

HFieldName = NewType("HFieldName", str)
"""Alias of string. Used to type hint a field is the name of an HField."""

MaterialName = NewType("MaterialName", str)
"""Alias of string. Used to type hint a field is the name of a Material."""

TextureName = NewType("TextureName", str)
"""Alias of string. Used to type hint a field is the name of a Texture."""

ModelName = NewType("ModelName", str)
"""Alias of string. Used to type hint a field is the name of a Model."""

BodyName = NewType("BodyName", str)
"""Alias of string. Used to type hint a field is the name of a Body."""

JointName = NewType("JointName", str)
"""Alias of string. Used to type hint a field is the name of a Joint."""

GeomName = NewType("GeomName", str)
"""Alias of string. Used to type hint a field is the name of a Geom."""

SiteName = NewType("SiteName", str)
"""Alias of string. Used to type hint a field is the name of a Site."""

CameraName = NewType("CameraName", str)
"""Alias of string. Used to type hint a field is the name of a Camera."""

LightName = NewType("LightName", str)
"""Alias of string. Used to type hint a field is the name of a Light."""

FrameName = NewType("FrameName", str)
"""Alias of string. Used to type hint a field is the name of a Frame."""

ContactPairName = NewType("ContactPairName", str)
"""Alias of string. Used to type hint a field is the name of a contact Pair."""

ContactExcludeName = NewType("ContactExcludeName", str)
"""Alias of string. Used to type hint a field is the name of a contact Exclude."""

DeformableSkinName = NewType("DeformableSkinName", str)
"""Alias of string. Used to type hint a field is the name of a DeformableSkin."""

FlexName = NewType("FlexName", str)
"""Alias of string. Used to type hint a field is the name of a DeformableFlex."""

EqualityName = NewType("EqualityName", str)
"""Alias of string. Used to type hint a field is the name of an Eqaulity."""

TendonName = NewType("TendonName", str)
"""Alias of string. Used to type hint a field is the name of a Tendon."""

ActuatorName = NewType("ActuatorName", str)
"""Alias of string. Used to type hint a field is the name of an Actuator."""

PluginName = NewType("PluginName", str)
"""Alias of string. Used to type hint a field is the name of a Plugin."""

InstanceName = NewType("InstanceName", str)
"""Alias of string. Used to type hint a field is the name of a plugin Instance."""

SensorName = NewType("SensorName", str)
"""Alias of string. Used to type hint a field is the name of a Sensor."""

KeyName = NewType("KeyName", str)
"""Alias of string. Used to type hint a field is the name of a Key."""

SensorAttachableName = BodyName | GeomName | SiteName | CameraName
"""Alias of names which can have a sensor attached to them."""

Name = (
    MeshName
    | HFieldName
    | MaterialName
    | TextureName
    | ModelName
    | BodyName
    | JointName
    | GeomName
    | SiteName
    | CameraName
    | LightName
    | FrameName
    | ContactPairName
    | ContactExcludeName
    | DeformableSkinName
    | FlexName
    | EqualityName
    | TendonName
    | ActuatorName
    | PluginName
    | InstanceName
    | SensorName
    | KeyName
)
"""Alias of any name."""

ActuatorGroup = Annotated[int, Field(ge=0, le=30)]
"""An integer representing an actuator group index. Must be between 0 and 30 inclusive."""

GeomGroup = Annotated[int, Field(ge=0, le=30)]
"""An integer representing a geom group index. Must be between 0 and 30 inclusive."""

InertiaGroupRange = tuple[GeomGroup, GeomGroup]
"""A tuple specifying the inclusive range of geom groups used for inertia computation."""

GridLayoutStr = Annotated[
    str,
    Field(
        pattern=r"^[\.RLUDFB]+$",
        description="String which may only use `'.'`, `'R'`, `'L'`, `'U'`, `'D'`, `'F'`, and `'B'`",
    ),
]
"""A string used for texture grid layout. May only include `'.'`, `'R'`, `'L'`, `'U'`, `'D'`, `'F'`, and `'B'`."""

if TYPE_CHECKING:
    type _VecBase = np.ndarray

    type Vec2 = _VecBase
    """A 2-element numeric array."""

    type Vec3 = _VecBase
    """A 3-element numeric array, often used for positions or directions."""

    type Vec4 = _VecBase
    """A 4-element numeric array, often used for RGBA colors or quaternions."""

    type Vec5 = _VecBase
    """A 5-element numeric array."""

    type Vec6 = _VecBase
    """A 6-element numeric array."""

    type Vec7 = _VecBase
    """A 7-element numeric array."""

    type Vec9 = _VecBase
    """A 9-element numeric array."""

    type VecN = _VecBase
    """An N-element numeric array of arbitrary length."""

    type Mat2 = _VecBase
    """A 2x2 numeric matrix."""

    type Mat3 = _VecBase
    """A 3x3 numeric matrix, often used for rotation matrices or inertia tensors."""

    type Mat4 = _VecBase
    """A 4x4 numeric matrix."""

    type Mat5 = _VecBase
    """A 5x5 numeric matrix."""

    type Mat6 = _VecBase
    """A 6x6 numeric matrix."""

    type Mat7 = _VecBase
    """A 7x7 numeric matrix."""

    type Mat9 = _VecBase
    """A 9x9 numeric matrix."""

    type MatN = _VecBase
    """An NxN numeric matrix of arbitrary length."""
else:
    Vec2 = Annotated[NDArray[Shape["2"], float | int], ...]
    Vec3 = Annotated[NDArray[Shape["3"], float | int], ...]
    Vec4 = Annotated[NDArray[Shape["4"], float | int], ...]
    Vec5 = Annotated[NDArray[Shape["5"], float | int], ...]
    Vec6 = Annotated[NDArray[Shape["6"], float | int], ...]
    Vec7 = Annotated[NDArray[Shape["7"], float | int], ...]
    Vec9 = Annotated[NDArray[Shape["9"], float | int], ...]
    VecN = Annotated[NDArray[Shape["*"], float | int], ...]  # type: ignore  # noqa: F722

    Mat2 = Annotated[NDArray[Shape["2, 2"], float | int], ...]
    Mat3 = Annotated[NDArray[Shape["3, 3"], float | int], ...]
    Mat4 = Annotated[NDArray[Shape["4, 4"], float | int], ...]
    Mat5 = Annotated[NDArray[Shape["5, 5"], float | int], ...]
    Mat6 = Annotated[NDArray[Shape["6, 6"], float | int], ...]
    Mat7 = Annotated[NDArray[Shape["7, 7"], float | int], ...]
    Mat9 = Annotated[NDArray[Shape["9, 9"], float | int], ...]
    MatN = Annotated[NDArray[Shape["*, *"], float | int], ...]  # type: ignore  # noqa: F722


def empty_list_field():
    return Field(default_factory=list, exclude_if=is_empty_list)


class SignalCategory(StrEnum):
    BODIES = "Bodies"
    SITES = "Sites"
    LOADS = "Loads"
    JOINTS = "Joints"
    SENSORS = "Sensors"
    GEOMS = "Geoms"
    ACTUATORS = "Actuators"
    TENDONS = "Tendons"
    CAMERAS = "Cameras"
    LIGHTS = "Lights"
    CONSTRAINTS = "Constraints"
    PLUGINS = "Plugins"
    DEFORMABLES = "Deformables"
    CUSTOM = "Custom"


class EulerSeq(StrEnum):
    """
    Euler rotation sequences.

    - Lowercase letters denote intrinsic rotations (about the rotating frame).
    - Uppercase letters denote extrinsic rotations (about the fixed parent frame).
    """

    # Intrinsic Tait-Bryan
    xyz = "xyz"
    """Intrinsic Tait-Bryan xyz sequence."""
    xzy = "xzy"
    """Intrinsic Tait-Bryan xzy sequence."""
    yxz = "yxz"
    """Intrinsic Tait-Bryan yxz sequence."""
    yzx = "yzx"
    """Intrinsic Tait-Bryan yzx sequence."""
    zxy = "zxy"
    """Intrinsic Tait-Bryan zxy sequence."""
    zyx = "zyx"
    """Intrinsic Tait-Bryan zyx sequence."""

    # Intrinsic Proper Euler
    xyx = "xyx"
    """Intrinsic proper Euler xyx sequence."""
    xzx = "xzx"
    """Intrinsic proper Euler xzx sequence."""
    yxy = "yxy"
    """Intrinsic proper Euler yxy sequence."""
    yzy = "yzy"
    """Intrinsic proper Euler yzy sequence."""
    zxz = "zxz"
    """Intrinsic proper Euler zxz sequence."""
    zyz = "zyz"
    """Intrinsic proper Euler zyz sequence."""

    # Extrinsic Tait-Bryan
    XYZ = "XYZ"
    """Extrinsic Tait-Bryan XYZ sequence"""
    XZY = "XZY"
    """Extrinsic Tait-Bryan XZY sequence"""
    YXZ = "YXZ"
    """Extrinsic Tait-Bryan YXZ sequence"""
    YZX = "YZX"
    """Extrinsic Tait-Bryan YZX sequence"""
    ZXY = "ZXY"
    """Extrinsic Tait-Bryan ZXY sequence"""
    ZYX = "ZYX"
    """Extrinsic Tait-Bryan ZYX sequence"""

    # Extrinsic Proper Euler
    XYX = "XYX"
    """Extrinsic proper Euler XYX"""
    XZX = "XZX"
    """Extrinsic proper Euler XZX"""
    YXY = "YXY"
    """Extrinsic proper Euler YXY"""
    YZY = "YZY"
    """Extrinsic proper Euler YZY"""
    ZXZ = "ZXZ"
    """Extrinsic proper Euler ZXZ"""
    ZYZ = "ZYZ"
    """Extrinsic proper Euler ZYZ"""


class LayerRole(StrEnum):
    """Role of the texture. The valid values, expected number of channels, and the role semantics are:"""

    RGB = "rgb"
    """3 channels. base color / albedo [red, green, blue]."""

    NORMAL = "normal"
    """3 channels. bump map (surface normals)."""

    OCCLUSION = "occlusion"
    """1 channel. ambient occlusion."""

    ROUGHNESS = "roughness"
    """1 channel. roughness."""

    METALLIC = "metallic"
    """1 channel. metallicity."""

    OPACITY = "opacity"
    """1 channel. opacity (alpha channel)."""

    EMISSIVE = "emissive"
    """4 channels. RGB light emmision intensity, exposure weight in 4th channel."""

    ORM = "orm"
    """3 channels. packed 3 channel [occlusion, roughness, metallic]."""

    RGBA = "rgba"
    """4 channels. packed 4 channel [red, green, blue, alpha]."""


class GeomType(StrEnum):
    """Enumeration of supported geometric types in MuJoCo."""

    PLANE = "plane"
    """Plane which is infinite for collision detection purposes."""

    HFIELD = "hfield"
    """Height field geom."""

    SPHERE = "sphere"
    """Sphere geom."""

    CAPSULE = "capsule"
    """A capsule, which is a cylinder capped with two half-spheres."""

    ELLIPSOID = "ellipsoid"
    """Ellipoid geom."""

    CYLINDER = "cylinder"
    """Cylinder geom."""
    BOX = "box"
    """Box geom."""

    MESH = "mesh"
    """Mesh geom."""

    SDF = "sdf"
    """Signed distance field (SDF, also referred to as signed distance function)."""


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

    PYRAMIDAL = "pyramidal"
    """Sometimes make the solver faster and more robust."""

    ELLIPTIC = "elliptic"
    """Better model of the physical reality."""


class Jacobian(StrEnum):
    """Jacobian computation methods."""

    DENSE = "dense"
    """Dense jacobian."""

    SPARSE = "sparse"
    """Sparse jacobian."""

    AUTO = "auto"
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

    ENABLE = "enable"
    """Enable the feature."""

    DISABLE = "disable"
    """Disable the feature."""


class Coordinate(StrEnum):
    """In previous versions, this attribute could be used to specify whether frame positions and orientations are expressed in local or global coordinates, but the "global" option has since been removed, and will cause an error to be generated. In order to convert older models which used the "global" option, load and save them in MuJoCo 2.3.3 or older."""

    LOCAL = "local"
    GLOBAL = "global"


class Angle(StrEnum):
    """This attribute specifies whether the angles in the MJCF model are expressed in units of degrees or radians. The compiler converts degrees into radians, and mjModel always uses radians. For URDF models the parser sets this attribute to "radian" internally, regardless of the XML setting."""

    RADIAN = "radian"
    DEGREE = "degree"


class InertiaFromGeom(StrEnum):
    """This attribute controls the automatic inference of body masses and inertias from geoms attached to the body."""

    FALSE = "false"
    """No automatic inference is performed. In that case each body must have explicitly defined mass and inertia with the inertial element, or else a compile error will be generated."""

    TRUE = "true"
    """The mass and inertia of each body will be inferred from the geoms attached to it, overriding any values specified with the inertial element."""

    AUTO = "auto"
    """Masses and inertias are inferred automatically only when the inertial element is missing in the body definition."""


class LengthRangeMode(StrEnum):
    """Determines the type of actuators to which length range computation is applied."""

    NONE = "none"
    """Disables this functionality."""

    MUSCLE = "muscle"
    """Applies to actuators whose gaintype or biastype is set to `muscle`"""

    MUSCLEUSER = "muscleuser"
    """Applies to actuators whose gaintype or biastype is set to either `muscle` or `user`."""

    ALL = "all"
    """Applies to all actuators."""


class DynType(StrEnum):
    """Activation dynamics type of actuators."""

    NONE = "none"
    """No internal state"""

    INTEGRATOR = "integrator"
    """act_dot = ctrl"""

    FILTER = "filter"
    """act_dot = (ctrl - act) / dynprm[0]"""

    FILTEREXACT = "filterexact"
    """Like filter but with exact integration"""

    MUSCLE = "muscle"
    """act_dot = mju_muscleDynamics(...)"""

    USER = "user"
    """act_dot = mjcb_act_dyn(...)"""


class GainType(StrEnum):
    """Gain type of actuators."""

    FIXED = "fixed"
    """gain_term = gainprm[0]"""

    AFFINE = "affine"
    """gain_term = gain_prm[0] + gain_prm[1] * length + gain_prm[2] * velocity"""

    MUSCLE = "muscle"
    """gain_term = mju_muscleGain(...)"""

    USER = "user"
    """gain_term = mjcb_act_gain(...)"""


class BiasType(StrEnum):
    """Bias type of actuators."""

    NONE = "none"
    """bias_term = 0"""

    AFFINE = "affine"
    """bias_term = biasprm[0] + biasprm[1]*length + biasprm[2]*velocity"""

    MUSCLE = "muscle"
    """bias_term = mju_muscleBias(...)"""

    USER = "user"
    """bias_term = mjcb_act_bias(...)"""


class Inertia(StrEnum):
    """This attribute controls how the mesh is used when mass and inertia are inferred from geometry. The current default value legacy will be changed to convex in a future release."""

    CONVEX = "convex"
    """Use the mesh's convex hull to compute volume and inertia, assuming uniform density."""

    EXACT = "exact"
    """Compute volume and inertia exactly, even for non-convex meshes. This algorithm requires a well-oriented, watertight mesh and will error otherwise."""

    LEGACY = "legacy"
    """Use the legacy algorithm, leads to volume overcounting for non-convex meshes. Though currently the default to avoid breakages, it is not recommended."""

    SHELL = "shell"
    """Assume mass is concentrated on the surface of the mesh. Use the mesh's surface to compute the inertia, assuming uniform surface density."""


class TextureType(StrEnum):
    """This attribute determines how the texture is represented and mapped to objects. It also determines which of the remaining attributes are relevant."""

    D2 = "2d"
    """Maps a 2D image to a 3D object using texture coordinates (a.k.a UV coordinates). However, UV coordinates are only available for meshes."""

    CUBE = "cube"
    """Has the effect of shrink-wrapping a texture cube over an object. Apart from the adjustment provided by the texuniform attribute of material, the process is automatic."""

    SKYBOX = "skybox"
    """Very similar to cube mapping, and in fact the texture data is specified in exactly the same way. The only difference is that the visualizer uses the first such texture defined in the model to render a skybox."""


class ColorSpace(StrEnum):
    """This attribute determines the color space of the texture. The default value auto means that the color space will be determined from the image file itself. If no color space is defined in the file, then linear is assumed."""

    AUTO = "auto"
    """Color space will be determined from the image file itself. If no color space is defined in the file, then linear is assumed."""

    LINEAR = "linear"
    """Linear color space."""

    SRGB = "srgb"
    """SRGB color space."""


class TextureBuiltInType(StrEnum):
    """This and the remaining attributes control the generation of procedural textures. If the value of this attribute is different from "none", the texture is treated as procedural and any file names are ignored."""

    NONE = "none"
    """No builtin texture."""

    GRADIENT = "gradient"
    """Generates a color gradient from rgb1 to rgb2. The interpolation in color space is done through a sigmoid function. For cube and skybox textures the gradient is along the +Y axis, i.e., from top to bottom for skybox rendering."""

    CHECKER = "checker"
    """Generates a 2-by-2 checker pattern with alternating colors given by rgb1 and rgb2. This is suitable for rendering ground planes and also for marking objects with rotational symmetries. Note that 2d textures can be scaled so as to repeat the pattern as many times as necessary. For cube and skybox textures, the checker pattern is painted on each side of the cube."""

    FLAT = "flat"
    """Fills the entire texture with rgb1, except for the bottom face of cube and skybox textures which is filled with rgb2."""


class Mark(StrEnum):
    """Procedural textures can be marked with the markrgb color, on top of the colors determined by the builtin type. All markings are one-pixel wide, thus the markings appear larger and more diffuse on smaller textures."""

    NONE = "none"
    """No marks."""

    EDGE = "edge"
    """Edges of all texture images are marked."""

    CROSS = "cross"
    """A cross is marked in the middle of each image."""

    RANDOM = "random"
    """Randomly chosen pixels are marked."""


"""Sleep policy for the tree under this body. This attribute is only supported by moving bodies which are the root of a kinematic tree. For the default auto, the compiler will set the sleep policy as follows:

    - A tree which is affected by actuators is not allowed to sleep (overridable).
    - Trees which are connected by tendons which have non-zero stiffness and damping are not allowed to sleep (overridable).
    - Trees which are connected by tendons which connect more than two trees are not allowed to sleep (not overridable).
    - flexes are not allowed to sleep (not overridable).
    - All other trees are allowed to sleep (overridable).

    The policies never and allowed constitute user overrides of the automatic compiler policy.

    The init sleep policy can only be specified by the user and means "initialize this tree as asleep". This policy is implemented in mj_resetData and mj_makeData and only applies to the default configuration. If a keyframe changes the configuration of (or assigns nonzero velocity to) a sleeping tree, it will be woken up. This policy is useful for very large models where waiting for the automatic sleeping mechanism to kick in can be expensive. Trees initialized as sleeping can be placed in unstable configurations like deep penetration or in mid-air, but will only move when woken up. Also note that this policy can fail. For example if a tree marked as sleep="init" is in contact with a tree not marked as such (i.e., they are in the same island) then it is impossible to put the tree to sleep; such models will lead to a compilation error.

    See implementation notes for more details."""


class Sleep(StrEnum):
    """Sleep policy for the tree under this body. This attribute is only supported by moving bodies which are the root of a kinematic tree."""

    AUTO = "auto"
    """Compiler will set the sleep policy as follows:

    - A tree which is affected by actuators is not allowed to sleep (overridable).
    - Trees which are connected by tendons which have non-zero stiffness and damping are not allowed to sleep (overridable).
    - Trees which are connected by tendons which connect more than two trees are not allowed to sleep (not overridable).
    - flexes are not allowed to sleep (not overridable).
    - All other trees are allowed to sleep (overridable)."""

    NEVER = "never"
    """Constitute user overrides of the automatic compiler policy."""

    ALLOWED = "allowed"
    """Constitute user overrides of the automatic compiler policy."""

    INIT = "init"
    """Can only be specified by the user and means "initialize this tree as asleep". This policy is implemented in mj_resetData and mj_makeData and only applies to the default configuration. If a keyframe changes the configuration of (or assigns nonzero velocity to) a sleeping tree, it will be woken up. This policy is useful for very large models where waiting for the automatic sleeping mechanism to kick in can be expensive. Trees initialized as sleeping can be placed in unstable configurations like deep penetration or in mid-air, but will only move when woken up. Also note that this policy can fail. For example if a tree marked as sleep="init" is in contact with a tree not marked as such (i.e., they are in the same island) then it is impossible to put the tree to sleep; such models will lead to a compilation error."""


class JointType(StrEnum):
    """Types of joints supported in MuJoCo."""

    FREE = "free"
    """Free "joint" with three translational degrees of freedom followed by three rotational degrees of freedom. In other words it makes the body floating. The rotation is represented as a unit quaternion. This joint type is only allowed in bodies that are children of the world body. No other joints can be defined in the body if a free joint is defined. Unlike the remaining joint types, free joints do not have a position within the body frame. Instead the joint position is assumed to coincide with the center of the body frame. Thus at runtime the position and orientation data of the free joint correspond to the global position and orientation of the body frame. Free joints cannot have limits."""

    BALL = "ball"
    """A ball joint with three rotational degrees of freedom. The rotation is represented as a unit quaternion. The quaternion (1,0,0,0) corresponds to the initial configuration in which the model is defined. Any other quaternion is interpreted as a 3D rotation relative to this initial configuration. The rotation is around the point defined by the pos attribute. If a body has a ball joint, it cannot have other rotational joints (ball or hinge). Combining ball joints with slide joints in the same body is allowed."""

    SLIDE = "slide"
    """A sliding or prismatic joint with one translational degree of freedom. Such joints are defined by a position and a sliding direction. For simulation purposes only the direction is needed; the joint position is used for rendering purposes."""

    HINGE = "hinge"
    """A hinge joint with one rotational degree of freedom. The rotation takes place around a specified axis through a specified position. This is the most common type of joint and is therefore the default. Most models contain only hinge and free joints."""


class JointLimited(StrEnum):
    """Specifies if the joint has limits."""

    FALSE = "false"
    """Joint limits are disabled."""

    TRUE = "true"
    """Joint limits are enabled."""

    AUTO = "auto"
    """Joint limits will be enabled if range is defined (if autolimits is set in compiler)."""


class TendonLimited(StrEnum):
    """Specifies if the tendon has limits."""

    FALSE = "false"
    """Tendon limits are disabled."""

    TRUE = "true"
    """Tendon limits are enabled."""

    AUTO = "auto"
    """Tendon limits will be enabled if range is defined (if autolimits is set in compiler)."""


class ActuatorControlLimited(StrEnum):
    """Specifies if the actuator control input has limits."""

    FALSE = "false"
    """Control input clamping is disabled."""

    TRUE = "true"
    """Control input to this actuator is automatically clamped to ctrlrange at runtime."""

    AUTO = "auto"
    """If `autolimits` is set in compiler, control clamping will automatically be set to true if `ctrlrange` is defined without explicitly setting this attribute to "true"."""


class ActuatorForceLimited(StrEnum):
    """This attribute specifies whether actuator forces acting on the joint should be clamped. See Force limits for details. It is available only for scalar joints (hinge and slider) and ignored for ball and free joints."""

    FALSE = "false"
    """Actuator force clamping is disabled."""

    TRUE = "true"
    """Actuator force clamping is enabled."""

    AUTO = "auto"
    """If `autolimits` is set in compiler, actuator force clamping will be enabled if `actuatorfrcrange`/`forcerange` is defined."""


class ActuatorLimited(StrEnum):
    """Specifies if the internal state (activation) associated with an actuator is clamped to `actrange` at runtime."""

    FALSE = "false"
    """Activation clamping is disabled."""

    TRUE = "true"
    """Activation clamping is enabled."""

    AUTO = "auto"
    """If `autolimits` is set in compiler, activation clamping will automatically be set to true if `actrange` is defined without explicitly setting this attribute to "true"."""


class Align(StrEnum):
    """Specifies alignment options for aligning body frame and free joint."""

    FALSE = "false"
    """No alignment will occur between the body frame and free joint."""

    TRUE = "true"
    """Body frame and free joint will automatically be aligned with inertial frame."""

    AUTO = "auto"
    """Compiler's alignfree global attribute will be respected."""


class FluidShape(StrEnum):
    """Geometry-level fluid interaction model."""

    NONE = "none"
    """I have no clue."""  # BUG Gable (1/30/2026) - if you know let me know thx

    ELLIPSOID = "ellipsoid"
    """Activates the geom-level fluid interaction model based on an ellipsoidal approximation of the geom shape. When active, the model based on body inertia sizes is disabled for the body in which the geom is defined. See section on ellipsoid-based fluid interaction model for details."""


class TrackingMode(StrEnum):
    """Specifies how the camera/light position and orientation in world coordinates are computed in forward kinematics (which in turn determine what the camera/light sees)."""

    FIXED = "fixed"
    """The position and orientation specified are fixed relative to the body where the camera/light is defined."""

    TRACK = "track"
    """The camera/light position is at a constant offset from the body in world coordinates, while the camera/light orientation is constant in world coordinates. These constants are determined by applying forward kinematics in qpos0 and treating the camera/light as fixed. Tracking can be used for example to position a camera/light above a body, point it down so it sees the body, and have it always remain above the body no matter how the body translates and rotates."""

    TRACKCOM = "trackcom"
    """similar to "track" but the constant spatial offset is defined relative to the center of mass of the kinematic subtree starting at the body in which the camera/light is defined. This can be used to keep an entire mechanism in view. Note that the subtree center of mass for the world body is the center of mass of the entire model. So if a camera/light is defined in the world body in mode "trackcom", it will track the entire model."""

    TARGETBODY = "targetbody"
    """The camera/light position is fixed in the body frame, while the camera/light orientation is adjusted so that it always points towards the targeted body (which is specified with the target attribute below). This can be used for example to model an eye that fixates a moving object; the object will be the target, and the camera/light/eye will be defined in the body corresponding to the head."""

    TARGETBODYCOM = "targetbodycom"
    """The same as "targetbody" but the camera/light is oriented towards the center of mass of the subtree starting at the target body."""


class LightType(StrEnum):
    """Determines the type of light. Note that some light types may not be supported by some renderers (e.g. only spot and directional lights are supported by the default native renderer)."""

    SPOT = "spot"
    """Supported by default native renderer"""

    DIRECTIONAL = "directional"
    """Supported by default native renderer"""

    POINT = "point"
    """Not supported by default native renderer"""

    IMAGE = "image"
    """Not supported by default native renderer"""


class CompositeType(StrEnum):
    CABLE = "cable"


class CompositeInitial(StrEnum):
    FREE = "free"
    BALL = "ball"
    NONE = "none"


class CompositeJointKind(StrEnum):
    MAIN = "main"


class FlexCompDOF(StrEnum):
    """The parametrization of the flex's degrees of freedom (dofs)."""

    FULL = "full"
    """Three translational dofs per vertex. This is the most expressive but also the most expensive option."""

    RADIAL = "radial"
    """A single radial translational dof per vertex. Note that unlike in the "full" case, the radial parametrization requires a free joint at the flex's parent in order for free body motion to be possible. This type of parametrization is appropriate for shapes that are relatively spherical."""

    TRILINEAR = "trilinear"
    """Three translational dofs at each corner of the bounding box of the flex, for a total of 24 dofs for the entire flex, independent of the number of vertices. The positions of the vertices are updated using trilinear interpolation over the bounding box."""


class FlexCompType(StrEnum):
    """The type of flexcomp object."""

    GRID = "grid"
    """`grid` generates a rectangular grid of points in 1D, 2D or 3D as specified by dim. The number of points in each dimension is determined by count while the grid spacing in each dimension is determined by spacing. Make sure the spacing is sufficiently large relative to radius to avoid permanent contacts. In 2D and 3D the grid is automatically triangulated, and corresponding flex elements are created (triangles or tetrahedra). In 1D the elements are capsules connecting consecutive pairs of points."""

    BOX = "box"
    """`box` generates a 3D box object, however flex bodies are only generated on the outer shell. Each flex body has a radial slider joint allowing it to move in and out from the center of the box. The parent body would normally be a floating body. The box surface is triangulated, and each flex element is a tetrahedron connecting the center of the box with one triangle face. count and spacing determine the count and spacing of the flex bodies, similar to the grid type in 3D. Note that the resulting flex has the same topology as the box generated by composite."""

    CYLINDER = "cylinder"
    """`cylinder` is the same as box, except the points are projected on the surface of a cylinder."""

    ELLIPSOID = "ellipsoid"
    """`ellipsoid` is the same as box, except the points are projected on the surface of an ellipsoid."""

    DISC = "disc"
    """`disc` is the same as box, except the points are projected on the surface of a disc. It is only compatible with dim=2."""

    CIRCLE = "circle"
    """`circle` is the same as grid, except the points are sampled along a circle so that the first and last points are the same. The radius of the circle is computed such that each segment has the requested spacing. It is only compatible with dim=1."""

    MESH = "mesh"
    """`mesh` loads the flexcomp points and elements (i.e. triangles) from a mesh file, in the same file formats as mesh assets, excluding the legacy .msh format. A mesh asset is not actually added to the model. Instead the vertex and face data from the mesh file are used to populate the point and element data of the flexcomp. dim is automatically set to 2. Recall that a mesh asset in MuJoCo can be used as a rigid geom attached to a single body. In contrast, the flex generated here corresponds to a soft mesh with the same initial shape, where each vertex is a separate moving body (unless pinned)."""

    GMSH = "gmsh"
    """`gmsh` is similar to mesh, but it loads a GMSH file in format 4.1 and format 2.2 (ascii or binary). The file extension can be anything; the parser recognizes the format by examining the file header. This is a very rich file format, allowing all kinds of elements with different dimensionality and topology. MuJoCo only supports GMSH element types 1, 2, 4 which happen to correspond to our 1D, 2D and 3D flexes and assumes that the nodes are specified in a single block. Only the Nodes and Elements sections of the GMHS file are processed, and used to populate the point and element data of the flexcomp. The parser will generate an error if the GMSH file contains meshes that are not supported by MuJoCo. dim is automatically set to the dimensionality specified in the GMSH file. Presently this is the only mechanism to load a large tetrahedral mesh in MuJoCo and generate a corresponding soft entity. If such a mesh is available in a different file format, use the freely available GMSH software to convert it to GMSH in one of the supported versions."""

    DIRECT = "direct"
    """`direct` allows the user to specify the point and element data of the flexcomp directly in the XML. Note that flexcomp will still generate moving bodies automatically, as well as automate other settings; so it still provides convenience compared to specifing the corresponding flex directly."""


class FlexElastic2D(StrEnum):
    """Elastic contribution to passive forces of 2D flexes."""

    NONE = "none"
    """None."""

    BEND = "bend"
    """Bending only."""

    STRETCH = "stretch"
    """Stretching only."""

    BOTH = "both"
    "Bending and stretching."


class SelfCollide(StrEnum):
    """This determines the strategy for midphase collision pruning of element pairs belonging to the same flex."""

    NONE = "none"
    """Flex elements cannot collide with each other."""

    NARROW = "narrow"
    """Narrow phase only (i.e. all pairs are checked). This is a diagnostic tool and is never a good idea in practice."""

    BVH = "bvh"
    """Bounding volume hierarchies (strategy for midphase collision pruning)."""

    SAP = "sap"
    """Sweep-and-prune (strategy for midphase collision pruning)."""

    AUTO = "auto"
    """Select sap in 1D and 2D, and bvh in 3D. Which strategy performs better depends on the specifics of the model. The automatic setting is just a simple rule which we have found to perform well in general."""


class SensorObjectType(StrEnum):
    """Types of objects to which a sensor may be attached. This must be an object type that has a spatial frame."""

    BODY = "body"
    """Attach to a body in the inertial frame."""

    XBODY = "xbody"
    """Attach to a body in the regular frame of the body (usually centered at the joint with the parent body)."""

    GEOM = "geom"
    """Attach to a geom."""

    SITE = "site"
    """Attach to a site."""

    CAMERA = "camera"
    """Attach to a camera."""


class ContactReduce(StrEnum):
    """Reduces the number of matched contacts to exactly num sub-arrays, or "slots". If less than num contacts match, the remaining slots are set to be identically zero. Note that the default, "unsorted" reduction criterion is potentitally non-deterministic. See reduce below."""

    NONE = "none"
    """Returns the first num contacts that satisfy the matching criterion, in the order that they appear in mjData.contact. Note that while this is the fastest option, it is also potentially non-deterministic: future changes to collision detection code may cause the identity and order of matching contacts to change."""

    MINDIST = "mindist"
    """Returns num contacts with the smallest penetration depth, ascending order."""

    MAXFORCE = "maxforce"
    """Returns num contacts with the largest force norm, descending order."""

    NETFORCE = "netforce"
    """This reduction criterion returns one new "synthetic" contact, located at the force-weighted centroid of all matched contacts. The frame of the contact is the global frame, so normal and tangent directions lose their natural semantic. The force and torque are computed such that a wrench applied at the computed position will have the same net effect as all the matching contacts combined. Note that this reduction criterion always returns exactly one contact."""


class ContactData(StrEnum):
    """
    Specification of which data field(s) to report from the selected contacts.

    Importantly, the data attribute can contain multiple sequential data types, as long as the relative order—as listed above—is maintained. For example, data = "found force dist" will return 5 numbers per contact (the concateneated values of [found, force, dist]), while data = "force found dist" is an error because found must come before force.

    !!! quote "Missing contacts"
        If less than num contacts satisfy the matching criterion, the entire data slot is set to be identically zero. Because most data types can take 0 as a valid value, only the zero-ness of the normal and tangent unit vectors can be used to unambiguously detect an empty slot. For this reason, the found data type is in place to allow for simple detection of missing contacts.

    !!! quote "Size of sensordata block"
        Unlike other sensors, the size of the corresponding sensordata block depends on the values of its attributes num and data. The total size of the output of a contact sensor is the product num x size(selected data fields). For example, requesting num = 6 contacts with data = "force dist normal" (3+1+3=7), will result in a sensordata block of 42 numbers (6 consecutive slots x 7 numbers per slot).

    !!! quote "Direction convention"
        Because contacts create two equal-and-opposite forces between contacting bodies, there is freedom in the choice of which body impinges on which.

        The sensor's convention is for "geom1/body1/subtree1" and "geom2/body2/subtree2" to determine the direction of the normal. The normal always points from the first to the second.

        In the case that a direction cannot be determined, as when only a site is used as the matching criterion, or when both subtrees are the same, the normal direction is the same as it is in mjData.contact, where the normal points from the first to the second geom, and the two geoms are sorted according to their order in mjtGeom.
    """

    FOUND = "found"
    """`float`: This field serves two purposes. First, it indicates whether a contact was found in this slot, 0 means not found while a positive number means found. Second, the positive value equals the number of matching contacts. So if num = 3 contacts were requested but only 2 were matched, the found fields will equal (2, 2, 0); if 6 were matched they will equal (6, 6, 6)."""

    FORCE = "force"
    """`Vec3`: The contact force, in the contact frame."""

    TORQUE = "torque"
    """`Vec3`: The contact torque, in the contact frame."""

    DIST = "dist"
    """`float`: The penetration distance."""

    POS = "pos"
    """`float`: The contact position, in the global frame."""

    NORMAL = "normal"
    """`Vec3`: The contact normal direction, in the global frame."""

    TANGENT = "tangent"
    """`Vec3`: The first tangent direction, in the global frame. In order to complete the full 3x3 contact frame, use tangent2 = cross(normal, tangent)."""


class DataType(StrEnum):
    """The type of output generated by this sensor."""

    AXIS = "axis"
    """Unit-length 3D vector."""

    QUATERNION = "quaternion"
    """Unit quaternion. These need to be declared because when MuJoCo adds noise, it must respect the vector normalization."""

    REAL = "real"
    """Generic array (or scalar) of real values to which noise can be added independently."""

    POSITIVE = "positive"
    """"""


class NeedStage(StrEnum):
    """The MuJoCo computation stage that must be completed before the user callback mjcb_sensor() is able to evaluate the output of this sensor."""

    POS = "pos"
    """Position stage."""

    VEL = "vel"
    """Velocity stage."""

    ACC = "acc"
    """Acceleration stage."""


class TextureMIME(StrEnum):
    """Enumerations for valid Texture MIME types."""

    PNG = "image/png"
    """Texture file is a PNG texture."""

    KTX = "image/ktx"
    """Texture file is a Khronos Texture."""

    VND = "image/vnd.mujoco.texture"
    """Texture file is a vnd.mujoco.texture (whatever that is)."""


class ActuatorInput(StrEnum):
    """Specifies the input signal semantics. (see tech note, Section 2.5)"""

    VOLTAGE = "voltage"
    """The control directly sets applied motor voltage"""

    POSITION = "position"
    """The PID controller uses the control as a reference setpoint relative to the joint position."""

    VELOCITY = "velocity"
    """The PID controller uses the control as a reference setpoint relative to the joint velocity."""


class CameraProjection(StrEnum):
    """Whether the camera uses a perspective (the default) or orthographic projection. Setting this attribute to "orthographic" changes the semantic of the fovy attribute."""

    PERSPECTIVE = "perspective"

    ORTHOGRAPHIC = "orthographic"


class CameraOutput(StrEnum):
    """Types of output images supported by the camera."""

    RGB = "rgb"
    """RGB image."""

    DEPTH = "depth"
    """Depth image (distance from camera plane)."""

    DISTANCE = "distance"
    """Distance image (distance from camera origin)."""

    NORMAL = "normal"
    """Surface normal image."""

    SEGMENTATION = "segmentation"
    """Segmentation image."""


class RangefinderData(StrEnum):
    DIST = "dist"
    """The distance from the ray origin to the nearest geom surface, -1 if no surface was hit. If this data type is included, rays will be visualized as lines."""

    DIR = "dir"
    """Normalized direction of the ray, or (0, 0, 0) if no surface was hit."""

    ORIGIN = "origin"
    """The point from which the ray emanates (global frame). For sites and perspective cameras, this is the site/camera xpos. However for orthographic cameras, ray origins are spatially distributed along the image plane."""

    POINT = "point"
    """The point where the ray intersects the nearest geom surface in the global frame, or (0, 0, 0) if no surface was hit. If this data type is included, intersection points will be visualized as spheres."""

    NORMAL = "normal"
    """The geom surface normal at the point where the ray intersects it, in the global frame, or (0, 0, 0) if no surface was hit. Note that normals always point towards the outside of the geom surface, regardless of the ray origin. If this data type is included along with either dist or point, normals will be visualized as arrows at the intersection points."""

    DEPTH = "depth"
    """The distance of the hit point from the camera plane, -1 if no surface was hit. Note that this depth semantic corresponds to depth images in the computer graphics sense."""


class SensorInterp(StrEnum):
    """The interpolation method used when reading from the history buffer. Corresponds to the interp argument in mj_readSensor."""

    ZOH = "zoh"
    """Zero-order hold (piecewise constant)."""

    LINEAR = "linear"
    """Piecewise linear interpolation."""

    CUBIC = "cubic"
    """Cubic spline interpolation (Catmull-Rom)."""
