from __future__ import annotations

from pathlib import Path
from typing import Optional

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.mujoco_attr.compiler_attr.lengthrange import LengthRange
from mujoco_mojo.typing import (
    Angle,
    Coordinate,
    EulerSeq,
    InertiaFromGeom,
    InertiaGroupRange,
)

__all__ = ["Compiler"]


class Compiler(XMLModel):
    """This element is used to set options for the built-in parser and compiler. After parsing and compilation it no longer has any effect. The settings here are global and apply to the entire model."""

    tag = "compiler"

    attributes = (
        "autolimits",
        "boundmass",
        "boundinertia",
        "settotalmass",
        "balanceinertia",
        "strippath",
        "coordinate",
        "angle",
        "fitaabb",
        "eulerseq",
        "meshdir",
        "texturedir",
        "discardvisual",
        "usethread",
        "fusestatic",
        "inertiafromgeom",
        "inertiagrouprange",
        "saveinertial",
        "assetdir",
        "alignfree",
    )
    children = ("lengthrange",)

    autolimits: bool = True
    """This attribute affects the behavior of attributes such as "limited" (on <body-joint> or <tendon>), "forcelimited", "ctrllimited", and "actlimited" (on <actuator>). If "true", these attributes are unnecessary and their value will be inferred from the presence of their corresponding "range" attribute. If "false", no such inference will happen: For a joint to be limited, both limited="true" and range="min max" must be specified. In this mode, it is an error to specify a range without a limit."""

    boundmass: float = 0
    """This attribute imposes a lower bound on the mass of each body except for the world body. Setting this attribute to a value greater than 0 can be used as a quick fix for poorly designed models that contain massless moving bodies, such as the dummy bodies often used in URDF models to attach sensors. Note that in MuJoCo there is no need to create dummy bodies."""

    boundinertia: float = 0
    """This attribute imposes a lower bound on the diagonal inertia components of each body except for the world body. Its use is similar to boundmass above."""

    settotalmass: float = -1
    """If this value is positive, the compiler will scale the masses and inertias of all bodies in the model, so that the total mass equals the value specified here. The world body has mass 0 and does not participate in any mass-related computations. This scaling is performed last, after all other operations affecting the body mass and inertia. The same scaling operation can be applied at runtime to the compiled mjModel with the function mj_setTotalmass."""

    balanceinertia: bool = False
    """A valid diagonal inertia matrix must satisfy A+B>=C for all permutations of the three diagonal elements. Some poorly designed models violate this constraint, which will normally result in a compile error. If this attribute is set to "true", the compiler will silently set all three diagonal elements to their average value whenever the above condition is violated."""

    strippath: bool = False
    """When this attribute is "true", the parser will remove any path information in file names specified in the model. This is useful for loading models created on a different system using a different directory structure."""

    coordinate: Coordinate = Coordinate.LOCAL
    """In previous versions, this attribute could be used to specify whether frame positions and orientations are expressed in local or global coordinates, but the "global" option has since been removed, and will cause an error to be generated. In order to convert older models which used the "global" option, load and save them in MuJoCo 2.3.3 or older."""

    angle: Angle = Angle.DEGREE
    """This attribute specifies whether the angles in the MJCF model are expressed in units of degrees or radians. The compiler converts degrees into radians, and mjModel always uses radians. For URDF models the parser sets this attribute to "radian" internally, regardless of the XML setting."""

    fitaabb: bool = False
    """The compiler is able to replace a mesh with a geometric primitive fitted to that mesh; see geom below. If this attribute is "true", the fitting procedure uses the axis-aligned bounding box (AABB) of the mesh, choosing the smallest primitive whose AABB contains the mesh AABB. Otherwise it uses the equivalent-inertia box of the mesh. The type of geometric primitive used for fitting is specified separately for each geom. The models used to generate the image on the right can be found here (fit inertia box) and here (fit aabb)."""

    eulerseq: EulerSeq | str = EulerSeq.xyz
    """This attribute specifies the sequence of Euler rotations for all euler attributes of elements that have spatial frames, as explained in Frame orientations. This must be a string with exactly 3 characters from the set {x, y, z, X, Y, Z}. The character at position n determines the axis around which the n-th rotation is performed. Lower case letters denote axes that rotate with the frame (intrinsic), while upper case letters denote axes that remain fixed in the parent frame (extrinsic). The "rpy" convention used in URDF corresponds to "XYZ" in MJCF."""

    meshdir: Optional[Path] = None
    """This attribute instructs the compiler where to look for mesh and height field files. The full path to a file is determined as follows. If the strippath attribute described above is "true", all path information from the file name is removed. The following checks are then applied in order: (1) if the file name contains an absolute path, it is used without further changes; (2) if this attribute is set and contains an absolute path, the full path is the string given here appended with the file name; (3) the full path is the path to the main MJCF model file, appended with the value of this attribute if specified, appended with the file name."""

    texturedir: Optional[Path] = None
    """This attribute is used to instruct the compiler where to look for texture files. It works in the same way as meshdir above."""

    assetdir: Optional[Path] = None
    """This attribute sets the values of both meshdir and texturedir above. Values in the latter attributes take precedence over assetdir."""

    discardvisual: bool = False
    """This attribute instructs the compiler to discard all model elements which are purely visual and have no effect on the physics (with one exception, see below). This often enables smaller mjModel structs and faster simulation.

    * All materials are discarded.
    * All textures are discarded.
    * All geoms with contype=conaffinity=0 are discarded, if they are not referenced in another MJCF element. If a discarded geom was used for inferring body inertia, an explicit inertial element is added to the body.
    * All meshes which are not referenced by any geom (in particular those discarded above) are discarded.

    The resulting compiled model will have exactly the same dynamics as the original model. The only engine-level computation which might change is the output of raycasting computations, as used for example by rangefinder sensors, since raycasting reports distances to visual geoms. When visualizing models compiled with this flag, it is important to remember that collision geoms are often placed in a group which is invisible by default.
    """

    usethread: bool = True
    """If this attribute is "true", the model compiler will run in multi-threaded mode. Currently multi-threading is used for computing the length ranges of actuators and for parallel loading of meshes."""

    fusestatic: bool = False
    """This attribute controls a compiler optimization feature where static bodies are fused with their parent, and any elements defined in those bodies are reassigned to the parent. Static bodies are fused with their parent unless

    * They are referenced by another element in the model.
    * They contain a site which is referenced by a force or torque sensor.

    This optimization is particularly useful when importing URDF models which often have many dummy bodies, but can also be used to optimize MJCF models. After optimization, the new model has identical kinematics and dynamics as the original but is faster to simulate."""

    inertiafromgeom: InertiaFromGeom = InertiaFromGeom.AUTO
    """This attribute controls the automatic inference of body masses and inertias from geoms attached to the body. If this setting is "false", no automatic inference is performed. In that case each body must have explicitly defined mass and inertia with the inertial element, or else a compile error will be generated. If this setting is "true", the mass and inertia of each body will be inferred from the geoms attached to it, overriding any values specified with the inertial element. The default setting "auto" means that masses and inertias are inferred automatically only when the inertial element is missing in the body definition. One reason to set this attribute to "true" instead of "auto" is to override inertial data imported from a poorly designed model. In particular, a number of publicly available URDF models have seemingly arbitrary inertias which are too large compared to the mass. This results in equivalent inertia boxes which extend far beyond the geometric boundaries of the model. Note that the built-in OpenGL visualizer can render equivalent inertia boxes."""

    alignfree: bool = False
    """This attribute toggles the default behaviour of an optimization that applies to bodies with a free joint and no child bodies. When true, the body frame and free joint will automatically be aligned with inertial frame, which leads to both faster and more stable simulation. See freejoint/align for details."""

    inertiagrouprange: InertiaGroupRange = (0, 5)
    """This attribute specifies the range of geom groups that are used to infer body masses and inertias (when such inference is enabled). The group attribute of geom is an integer. If this integer falls in the range specified here, the geom will be used in the inertial computation, otherwise it will be ignored. This feature is useful in models that have redundant sets of geoms for collision and visualization. Note that the world body does not participate in the inertial computations, so any geoms attached to it are automatically ignored. Therefore it is not necessary to adjust this attribute and the geom-specific groups so as to exclude world geoms from the inertial computation."""

    saveinertial: bool = False
    """If set to "true", the compiler will save explicit inertial clauses for all bodies."""

    lengthrange: LengthRange = LengthRange()
