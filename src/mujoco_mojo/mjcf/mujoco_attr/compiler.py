from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator

from mujoco_mojo.mjcf.defaults import DEFAULT_ANGLE, DEFAULT_EULERSEQ
from mujoco_mojo.mjcf.mujoco_attr.compiler_attr.lengthrange import LengthRange
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import (
    Angle,
    Conflict,
    Coordinate,
    EulerSeq,
    InertiaFromGeom,
    InertiaGroupRange,
    Passthrough,
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
        "savecompiled",
        "savecanonical",
        "conflict",
        "passthrough",
    )
    children = ("lengthrange",)

    autolimits: bool = True
    """This attribute affects the behavior of attributes such as "limited" (on <body-joint> or <tendon>), "forcelimited", "ctrllimited", and "actlimited" (on <actuator>). If "true", these attributes are unnecessary and their value will be inferred from the presence of their corresponding "range" attribute. If "false", no such inference will happen: For a joint to be limited, both limited="true" and range="min max" must be specified. In this mode, it is an error to specify a range without a limit."""

    boundmass: float = 0
    """This attribute imposes a lower bound on the mass of each body except for the world body. Setting this attribute to a value greater than 0 can be used as a quick fix for poorly designed models that contain massless moving bodies, such as the dummy bodies often used in URDF models to attach sensors. Note that in MuJoCo there is no need to create dummy bodies."""

    boundinertia: float = 0
    """This attribute imposes a lower bound on the diagonal inertia components of each body except for the world body. Its use is similar to boundmass above."""

    settotalmass: float = -1
    """This attribute is deprecated and will be removed in a future release; compiling a model which sets it gives a warning. If this value is positive, the compiler will scale the masses and inertias of all bodies in the model, so that the total mass equals the value specified here. The world body has mass 0 and does not participate in any mass-related computations. This scaling is performed last, after all other operations affecting the body mass and inertia. The same scaling operation can be applied at runtime to the compiled mjModel with the function mj_setTotalmass, followed by mj_setConst."""

    balanceinertia: bool = False
    """A valid diagonal inertia matrix must satisfy A+B>=C for all permutations of the three diagonal elements. Some poorly designed models violate this constraint, which will normally result in a compile error. If this attribute is set to "true", the compiler will silently set all three diagonal elements to their average value whenever the above condition is violated."""

    strippath: bool = False
    """When this attribute is "true", the parser will remove any path information in file names specified in the model. This is useful for loading models created on a different system using a different directory structure.

    Like the directories below, it is turned off in the saved XML when assets are bundled."""

    coordinate: Coordinate = Coordinate.LOCAL
    """In previous versions, this attribute could be used to specify whether frame positions and orientations are expressed in local or global coordinates, but the "global" option has since been removed, and will cause an error to be generated. In order to convert older models which used the "global" option, load and save them in MuJoCo 2.3.3 or older."""

    angle: Angle = DEFAULT_ANGLE
    """This attribute specifies whether the angles in the MJCF model are expressed in units of degrees or radians. The compiler converts degrees into radians, and mjModel always uses radians. For URDF models the parser sets this attribute to "radian" internally, regardless of the XML setting."""

    fitaabb: bool = False
    """The compiler is able to replace a mesh with a geometric primitive fitted to that mesh; see geom below. If this attribute is "true", the fitting procedure uses the axis-aligned bounding box (AABB) of the mesh, choosing the smallest primitive whose AABB contains the mesh AABB. Otherwise it uses the equivalent-inertia box of the mesh. The type of geometric primitive used for fitting is specified separately for each geom. The models used to generate the image on the right can be found here (fit inertia box) and here (fit aabb)."""

    eulerseq: EulerSeq = DEFAULT_EULERSEQ
    """This attribute specifies the sequence of Euler rotations for all euler attributes of elements that have spatial frames, as explained in Frame orientations. This must be a string with exactly 3 characters from the set {x, y, z, X, Y, Z}. The character at position n determines the axis around which the n-th rotation is performed. Lower case letters denote axes that rotate with the frame (intrinsic), while upper case letters denote axes that remain fixed in the parent frame (extrinsic). The "rpy" convention used in URDF corresponds to "XYZ" in MJCF."""

    meshdir: Path | None = None
    """This attribute instructs the compiler where to look for mesh and height field files. The full path to a file is determined as follows. If the strippath attribute described above is "true", all path information from the file name is removed. The following checks are then applied in order: (1) if the file name contains an absolute path, it is used without further changes; (2) if this attribute is set and contains an absolute path, the full path is the string given here appended with the file name; (3) the full path is the path to the main MJCF model file, appended with the value of this attribute if specified, appended with the file name.

    When assets are bundled (see `DepPath`), a relative directory is relative to the working directory, and it is removed from the saved XML because bundled files are written with explicit paths."""

    texturedir: Path | None = None
    """This attribute is used to instruct the compiler where to look for texture files. It works in the same way as meshdir above.

    Includes when assets are bundled."""

    assetdir: Path | None = None
    """This attribute sets the values of both meshdir and texturedir above. Values in the latter attributes take precedence over assetdir.

    Like them, it is removed from the saved XML when assets are bundled."""

    discardvisual: bool = False
    """This attribute instructs the compiler to discard all model elements which are purely visual and have no effect on the physics (with one exception, see below). This often enables smaller mjModel structs and faster simulation.

    - All materials and textures are discarded, unless they are referenced by a sensor or a custom tuple.
    - All geoms with `contype=conaffinity=0` are discarded, if they are not referenced in another MJCF element and do not use the ellipsoid fluid model. If a discarded geom was used for inferring body inertia, an explicit inertial element is added to the body. This is not possible when inertiafromgeom is "true", which is then a compilation error.
    - All meshes which are not used by a remaining geom or by a site, and are not referenced in another MJCF element, are discarded (in particular those of the geoms discarded above).

    The resulting compiled model will have exactly the same dynamics as the original model. The only engine-level computation which might change is the output of raycasting computations, as used for example by rangefinder sensors, since raycasting reports distances to visual geoms. When visualizing models compiled with this flag, it is important to remember that collision geoms are often placed in a group which is invisible by default.

    Discarding is an operation on the model itself, mjs_discardVisual, which is applied before compiling. A model which is saved or compiled again afterwards is the one without the visual elements.
    """

    usethread: bool = True
    """If this attribute is "true", the model compiler will run in multi-threaded mode. Currently multi-threading is used for computing the length ranges of actuators and for parallel loading of meshes."""

    fusestatic: bool = False
    """This attribute controls a compiler optimization feature where static bodies are fused with their parent, and any elements defined in those bodies are reassigned to the parent. Static bodies are fused with their parent unless

    - They are referenced by another element in the model.
    - They contain a site which is referenced by a force or torque sensor.
    - Their fuse attribute is "false".
    - They have a plugin or a sleep policy.
    - They have mass, and either a gravcomp different from that of their parent, or the model is in a fluid (non-zero density or viscosity); in a fluid, bodies with an ellipsoid-fluid geom are kept too.
    - inertiafromgeom is "true" and the compiler adjusted their inertia or their parent's (boundmass, boundinertia, balanceinertia), so that the geoms of both in one body would have a different inertia.

    Fusing is an operation on the model itself, mjs_fuseStatic, which is applied before compiling: each fused body becomes a frame in its parent. A model which is saved or compiled again afterwards is the fused one.

    This optimization is particularly useful when importing URDF models which often have many dummy bodies, but can also be used to optimize MJCF models. After optimization, the new model has identical kinematics and dynamics as the original but is faster to simulate."""

    inertiafromgeom: InertiaFromGeom = InertiaFromGeom.AUTO
    """This attribute controls the automatic inference of body masses and inertias from geoms attached to the body. If this setting is "false", no automatic inference is performed. In that case each body must have explicitly defined mass and inertia with the inertial element, or else a compile error will be generated. If this setting is "true", the mass and inertia of each body will be inferred from the geoms attached to it, overriding any values specified with the inertial element. The default setting "auto" means that masses and inertias are inferred automatically only when the inertial element is missing in the body definition. One reason to set this attribute to "true" instead of "auto" is to override inertial data imported from a poorly designed model. In particular, a number of publicly available URDF models have seemingly arbitrary inertias which are too large compared to the mass. This results in equivalent inertia boxes which extend far beyond the geometric boundaries of the model. Note that the built-in OpenGL visualizer can render equivalent inertia boxes."""

    alignfree: bool = False
    """This attribute toggles the default behaviour of an optimization that applies to bodies with a free joint and no child bodies. When true, the body frame and free joint will automatically be aligned with inertial frame, which leads to both faster and more stable simulation. See freejoint/align for details."""

    inertiagrouprange: InertiaGroupRange = (0, 5)
    """This attribute specifies the range of geom groups that are used to infer body masses and inertias (when such inference is enabled). The group attribute of geom is an integer. If this integer falls in the range specified here, the geom will be used in the inertial computation, otherwise it will be ignored. This feature is useful in models that have redundant sets of geoms for collision and visualization. Note that the world body does not participate in the inertial computations, so any geoms attached to it are automatically ignored. Therefore it is not necessary to adjust this attribute and the geom-specific groups so as to exclude world geoms from the inertial computation."""

    saveinertial: bool = False
    """If set to "true", the compiler will save explicit inertial clauses for all bodies."""

    savecompiled: bool = True
    """This attribute and the next one say how the model is saved as MJCF; like saveinertial, they are not saved themselves. If "true", the values which compilation made of the model are saved: for example the size of a geom which was fitted to a mesh, or the pose of a body after alignment with its free joint. If "false", the model is saved as it is written in the mjSpec, and the saved file compiles to the same model; the spec need not have been compiled."""

    savecanonical: bool = True
    """If "true", orientations are saved as quaternions, angles in radians, sizes and poses which were given with fromto as size, pos and quat, and a fullinertia as diaginertia and quat. If "false", they are saved in the notation in which they were written. This attribute has an effect only if savecompiled is "false": compiled values are always saved in the canonical notation."""

    conflict: Conflict = Conflict.WARNING
    """This attribute controls how conflicting global attributes (physics options, sizes, visual settings) are resolved when a child spec is attached to a parent using mjs_attach. A conflict occurs when both the parent and child specify authored values for the same field and those values differ. See Attribute Merging for details and a per-field table.

    warning

        Parent values take precedence. When a conflict is detected, a warning is emitted but the parent value is not modified. This is the default and preserves the pre-existing attachment behavior.

    merge

        Fields are merged using field-specific strategies (minimum, maximum, OR, or error), depending on the field's semantics. When only the child specifies an authored value, it is adopted by the parent. See the merging table for per-field details.

    error

        Any conflict between authored values results in a compile error. This is the strictest mode and is useful for detecting unintended attribute mismatches.

    """

    passthrough: Passthrough = Passthrough.NONE
    """Which assets the compiler leaves by reference instead of loading into the compiled model. With "textures", a texture loaded from a single file is not read: the model holds its resolved path and the parameters a consumer needs to load it, and no pixels. Textures which the compiler would transform (flipped, composite grids, six separate files), procedural textures, textures given as a buffer and files served from memory by a virtual file system stay embedded. The per-texture `embed` attribute overrides this policy. The policy is that of the model being compiled, so it also applies to the textures of attached models. Only textures can be by reference for now; other asset types will be added to the list of values."""

    lengthrange: LengthRange = Field(default_factory=LengthRange)
    """This element controls the computation of actuator length ranges. For an overview of this functionality see Length range section. Note that if this element is omitted the defaults shown below still apply. In order to disable length range computations altogether, include this element and set mode="none"."""

    @field_validator("meshdir", "texturedir", "assetdir")
    @classmethod
    def validate_asset_dir(cls, value: Path | None) -> Path | None:
        """Keeps these as plain paths: a `DepPath` here (accepted for compatibility) would otherwise be mistaken for a file to bundle."""
        return None if value is None else Path(value)
