from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Self
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, ParseError

import mujoco
import numpy as np
from pydantic import Field

import mujoco_mojo.utils.utils as utils
from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.defaults import DEFAULT_ANGLE, DEFAULT_EULERSEQ
from mujoco_mojo.mjcf.dependency_path import DepPath
from mujoco_mojo.mjcf.extension import Extension
from mujoco_mojo.mjcf.mujoco_attr.actuator import Actuator
from mujoco_mojo.mjcf.mujoco_attr.asset import Asset
from mujoco_mojo.mjcf.mujoco_attr.body import WorldBody
from mujoco_mojo.mjcf.mujoco_attr.compiler import Compiler
from mujoco_mojo.mjcf.mujoco_attr.contact import Contact
from mujoco_mojo.mjcf.mujoco_attr.deformable import Deformable
from mujoco_mojo.mjcf.mujoco_attr.equality import Equality
from mujoco_mojo.mjcf.mujoco_attr.keyframe import Keyframe
from mujoco_mojo.mjcf.mujoco_attr.keyframe_attr.key import Key
from mujoco_mojo.mjcf.mujoco_attr.keyframe_attr.key_state import KeyVector
from mujoco_mojo.mjcf.mujoco_attr.option import Option
from mujoco_mojo.mjcf.mujoco_attr.sensor import Sensor
from mujoco_mojo.mjcf.mujoco_attr.size import Size
from mujoco_mojo.mjcf.mujoco_attr.statistic import Statistic
from mujoco_mojo.mjcf.mujoco_attr.tendon import Tendon
from mujoco_mojo.mjcf.mujoco_attr.visual import Visual
from mujoco_mojo.mjcf.pose import PoseQuat
from mujoco_mojo.mjcf.pose_context import HasPose, PoseContext
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.mjcf.xml_reader import read_xml
from mujoco_mojo.typing import Angle, EulerSeq, KeyName, ModelName
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.utils import is_empty_list, to_pretty_xml

if TYPE_CHECKING:
    from mujoco_mojo.stochas import UnitSystem

logger = get_logger(__name__)

__all__ = ["Mujoco"]


def _compiler_setting(root: Element, name: str) -> str | None:
    """The value every `compiler` element of a document gives for the attribute `name`, or `None` if none does."""
    values = {c.attrib[name] for c in root.findall("compiler") if name in c.attrib}
    if len(values) > 1:
        msg = f"Inconsistent compiler {name} settings: {sorted(values)}. All compiler tags must match."
        logger.error(msg)
        raise ValueError(msg)
    return next(iter(values), None)


def _fill_key_elements(
    element: Element, resolved: Mapping[str, Mapping[KeyVector, np.ndarray]]
) -> None:
    """Sets the vectors in `resolved` on the `key` elements of the same name in `element`."""
    for key_element in element.iter("key"):
        vectors = resolved.get(key_element.get("name", ""))
        if vectors is None:
            continue
        for vector, values in vectors.items():
            key_element.set(vector, " ".join(map(str, values.tolist())))


def _key_id(model: mujoco.MjModel, key: KeyName | int) -> int:
    """The ID of `key`, given by name or by index, raising when `model` has no such key."""
    if isinstance(key, int):
        if not 0 <= key < model.nkey:
            msg = f"The model has {model.nkey} keys, so it has no key {key}."
            logger.error(msg)
            raise ValueError(msg)
        return key

    key_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, key)
    if key_id == -1:
        msg = f"The model has no key named '{key}'."
        logger.error(msg)
        raise ValueError(msg)
    return key_id


def _with_compiler_dir(path: Path, directory: Path | None, strippath: bool) -> Path:
    """
    Completes a file name the way MuJoCo does: `strippath` removes any directory from it, an absolute path is then used as it is, and otherwise the compiler directory goes in front of it.

    A relative `directory` is relative to the working directory, which is where every `DepPath` is resolved from.
    """
    if strippath:
        path = Path(path.name)
    if path.is_absolute() or directory is None:
        return path
    return directory / path


class Mujoco(XMLModel):
    """The unique top-level element, identifying the XML file as an MJCF model file."""

    tag = "mujoco"

    attributes = ("model",)
    children = (
        "options",
        "compilers",
        "sizes",
        "statistics",
        "assets",
        "worldbody",
        "deformables",
        "contacts",
        "equalities",
        "tendons",
        "actuators",
        "sensors",
        "keyframes",
        "visuals",
        # "defaults",
        # "customs",
        "extensions",
    )

    model: ModelName | None = None
    """The name of the model. This name is shown in the title bar of simulate.cc."""

    worldbody: WorldBody | None = None
    """World body of the model. There can be only one."""

    options: list[Option] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Simulation options."""

    compilers: list[Compiler] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Compiler options."""

    sizes: list[Size] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Size parameter options."""

    statistics: list[Statistic] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Model statistic overrides."""

    assets: list[Asset] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Assets definitions in the model."""

    deformables: list[Deformable] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Deformables elements definitions in the model."""

    contacts: list[Contact] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Contact elements definitions in the model."""

    equalities: list[Equality] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Equality constraint definition grouping."""

    tendons: list[Tendon] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Tendon definition grouping."""

    actuators: list[Actuator] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Actuator definition grouping."""

    sensors: list[Sensor] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Sensor definition grouping."""

    keyframes: list[Keyframe] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Keyframe definition grouping."""

    visuals: list[Visual] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Visual definition grouping."""

    # the following two are not planned for implementation
    # defaults: list[Default] = Field(
    #     default_factory=list,
    #     exclude_if=is_empty_list,
    # )
    # """Default definition grouping."""

    # customs: list[Custom] = Field(
    #     default_factory=list,
    #     exclude_if=is_empty_list,
    # )
    # """Custom definitions grouping."""

    extensions: list[Extension] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Extension definitions grouping."""

    @property
    def compiler_degree_settings(self) -> Angle:
        """
        Returns the unified Angle setting. If no compilers are defined, uses the Compiler class default.
        """
        default = DEFAULT_ANGLE

        if not self.compilers:
            return default
        elif len(self.compilers) == 1:
            return self.compilers[0].angle

        unique = {c.angle for c in self.compilers}
        if len(unique) > 1:
            msg = f"Inconsistent compiler angle settings: {unique}. All compiler tags must match."
            logger.error(msg)
            raise ValueError(msg)

        return next(iter(unique)) if unique else default

    @property
    def compiler_eulerseq_settings(self) -> EulerSeq:
        default = DEFAULT_EULERSEQ

        if not self.compilers:
            return default
        elif len(self.compilers) == 1:
            return self.compilers[0].eulerseq

        unique = {c.eulerseq for c in self.compilers}
        if len(unique) > 1:
            msg = f"Inconsistent compiler eulerseq settings: {unique}. All compiler tags must match."
            logger.error(msg)
            raise ValueError(msg)

        return next(iter(unique)) if unique else default

    def write_xml(self, file: Path, exclude_default: bool = True) -> str:
        """
        Writes the MuJoCo model to an XML file.

        A key with `states` needs the compiled model to lay its vectors out, so when one has them the model is compiled from `file` once it is written, and the file is written again with the vectors filled in.

        Args:
            file (Path): Filepath to save XML.
            exclude_default (bool, optional): Wheter or not to include default values. Values equal to None are always ignored. Attributes which are literals (such as Geom.type) are always included. Defaults to True.

        Returns:
            str: Prettified XML text.

        """
        return self._write_xml(file, exclude_default)[0]

    def _write_xml(
        self, file: Path, exclude_default: bool = True
    ) -> tuple[str, mujoco.MjModel | None]:
        """Writes the model as `write_xml` does, and returns the XML with the model compiled to lay out the keys' states, or `None` when no key has states and nothing was compiled."""
        element = self.to_xml(
            exclude_default=exclude_default,
            compiler_degrees=self.compiler_degree_settings,
            compiler_eulerseq=self.compiler_eulerseq_settings,
        )
        xml = utils.to_pretty_xml(element)
        file.write_text(xml, encoding="utf-8")
        if not self._has_key_states():
            return xml, None

        # compiled from the file, not the text, so assets written relative to it are found
        model = mujoco.MjModel.from_xml_path(str(file))
        _fill_key_elements(element, self._resolve_keys(model))
        xml = utils.to_pretty_xml(element)
        file.write_text(xml, encoding="utf-8")
        return xml, model

    def _keys(self) -> list[Key]:
        return [key for keyframe in self.keyframes for key in keyframe.keys]

    def _has_key_states(self) -> bool:
        return any(key.states for key in self._keys())

    @property
    def initial_key(self) -> Key | None:
        """The key marked `initial`, which `prep_for_sim` starts the simulation from, or `None` if no key is."""
        marked = [key for key in self._keys() if key.initial]
        if len(marked) > 1:
            msg = f"Only one key can be initial, but {', '.join(repr(k.name) for k in marked)} are."
            logger.error(msg)
            raise ValueError(msg)
        return marked[0] if marked else None

    def _resolve_keys(
        self, model: mujoco.MjModel
    ) -> dict[str, dict[KeyVector, np.ndarray]]:
        """Writes the vectors each key's `states` give into that key's row of `model` (`key_qpos`, `key_qvel`, and so on) and returns them by key name."""
        resolved: dict[str, dict[KeyVector, np.ndarray]] = {}
        for key in self._keys():
            if not key.states:
                continue
            assert key.name is not None, "checked by Key.check_states"
            key_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, key.name)
            vectors = key.resolve(model)
            for vector, values in vectors.items():
                getattr(model, f"key_{vector}")[key_id] = values
            resolved[key.name] = vectors
        return resolved

    @classmethod
    def from_xml(cls, source: str | Path, *, strict: bool = True) -> Self:
        """
        Reads a model from MJCF, the inverse of `write_xml`.

        A relative file in the XML (a mesh, a texture) is completed the way MuJoCo finds it, with the compiler's `meshdir`, `texturedir`, `assetdir` and `strippath` and then the folder of the file, so it points at the file wherever you run from. XML text has no folder, so there a relative path stays relative to the working directory like every `DepPath`.

        Elements are grouped by kind, so the order of different kinds within an element is not kept (the actuators of a `motor` and a `position` come out as all of one and then all of the other, which changes their order in `ctrl`).

        Args:
            source: The XML text if it is a `str`, or the file to read if it is a `Path`.
            strict: Whether an element or attribute that Mojo has no model for (`default`, `custom` and `include`, for instance) raises. With `strict=False` it is dropped and a warning is logged, and what the dropped element set (the values of a `default` class) is lost.

        Returns:
            The model.

        Raises:
            ValueError: If the XML is not well formed, is not a `mujoco` element, or in strict mode has something Mojo cannot read. The message lists everything.

        """
        base: Path | None = None
        try:
            if isinstance(source, Path):
                root = ElementTree.parse(source).getroot()
                base = source.resolve().parent
            else:
                root = ElementTree.fromstring(source)
        except ParseError as error:
            msg = f"The XML is not well formed: {error}."
            if isinstance(source, str) and not source.lstrip().startswith("<"):
                msg += " A str is read as XML text, so pass a Path to read a file."
            logger.error(msg)
            raise ValueError(msg) from error

        angle = _compiler_setting(root, "angle")
        eulerseq = _compiler_setting(root, "eulerseq")
        model = read_xml(
            cls,
            root,
            angle=DEFAULT_ANGLE if angle is None else Angle(angle),
            eulerseq=DEFAULT_EULERSEQ if eulerseq is None else EulerSeq(eulerseq),
            strict=strict,
        )
        if base is not None:
            model._complete_asset_paths(base)
        return model

    def _compiler_asset_dirs(self) -> tuple[Path | None, Path | None, bool]:
        """The effective `meshdir`, `texturedir`, and `strippath` across every compiler element, with `assetdir` standing in for whichever of the two directories is unset (the specific directory wins, as in MuJoCo)."""
        meshdir = texturedir = assetdir = None
        strippath = False
        for compiler in self.compilers:
            meshdir = compiler.meshdir or meshdir
            texturedir = compiler.texturedir or texturedir
            assetdir = compiler.assetdir or assetdir
            strippath = strippath or compiler.strippath
        return meshdir or assetdir, texturedir or assetdir, strippath

    def bundle_assets(self, target_dir: Path, rel_to_xml: Path) -> bool:
        """
        Bundles the model's `DepPath` assets (see `XMLModel.bundle_assets`), finding each file the way MuJoCo does.

        MuJoCo looks for a mesh, height field, skin, or flexcomp file in `meshdir`, and for a texture file in `texturedir` (`assetdir` sets both), after `strippath` removes any directory from the file name. A relative file name given as a `DepPath` is therefore completed with the matching compiler directory first, with a relative directory taken relative to the working directory like every `DepPath`.

        Bundled files are written with explicit paths relative to the XML, so once anything is bundled `meshdir`, `texturedir`, `assetdir`, and `strippath` are cleared. Left in the XML they would be put in front of those paths again, and MuJoCo would look in the wrong place.

        Returns:
            Whether any asset was bundled.

        """
        self._complete_asset_paths()

        bundled = super().bundle_assets(target_dir, rel_to_xml)
        if bundled:
            self._clear_compiler_asset_dirs()
        return bundled

    def _complete_asset_paths(self, base: Path | None = None) -> None:
        """
        Puts the compiler directory in front of every `DepPath` that MuJoCo would look for in one (see `bundle_assets`), then `base` in front of what is still relative, since MuJoCo reads a relative file from the folder of the model file.

        Without a `base`, nothing is changed when the compiler sets no directory and no `strippath`.
        """
        meshdir, texturedir, strippath = self._compiler_asset_dirs()
        if base is None and not (
            strippath or meshdir is not None or texturedir is not None
        ):
            return
        directories = {"meshdir": meshdir, "texturedir": texturedir}
        for obj in self._iter_tree():
            for attr in obj.attributes:
                value = getattr(obj, attr, None)
                if not isinstance(value, DepPath):
                    continue
                completed = value
                if obj.compiler_asset_dir is not None:
                    completed = _with_compiler_dir(
                        value, directories[obj.compiler_asset_dir], strippath
                    )
                if base is not None and not completed.is_absolute():
                    completed = base / completed
                if completed != value:
                    setattr(obj, attr, DepPath(completed))

    def _clear_compiler_asset_dirs(self) -> None:
        cleared = []
        for compiler in self.compilers:
            for name in ("meshdir", "texturedir", "assetdir"):
                if getattr(compiler, name) is not None:
                    setattr(compiler, name, None)
                    cleared.append(name)
            if compiler.strippath:
                compiler.strippath = False
                cleared.append("strippath")
        if cleared:
            logger.info(
                f"Bundled assets are written with explicit paths, so {', '.join(cleared)} "
                "were removed from the compiler."
            )

    def to_mj_spec(self) -> mujoco.MjSpec:
        """Creates an MjSpec from the Mujoco instance. A key with `states` is laid out by compiling the model first, so its vectors are in the spec."""
        element = self.to_xml(
            compiler_degrees=self.compiler_degree_settings,
            compiler_eulerseq=self.compiler_eulerseq_settings,
        )
        if self._has_key_states():
            model = mujoco.MjModel.from_xml_string(to_pretty_xml(element))
            _fill_key_elements(element, self._resolve_keys(model))
        return mujoco.MjSpec.from_string(to_pretty_xml(element))

    def to_mj_model(self) -> mujoco.MjModel:
        """Creates an MjModel from the Mujoco instance, with the vectors of each key's `states` in its keyframe arrays."""
        model = mujoco.MjModel.from_xml_string(
            to_pretty_xml(
                self.to_xml(
                    compiler_degrees=self.compiler_degree_settings,
                    compiler_eulerseq=self.compiler_eulerseq_settings,
                )
            )
        )
        self._resolve_keys(model)
        return model

    @property
    def pose_context(self) -> PoseContext:
        """
        Builds a PoseContext from the current worldbody tree.

        Raises ValueError if worldbody is not set.
        """
        if self.worldbody is None:
            raise ValueError("Cannot build pose graph: worldbody is not set.")
        return PoseContext(self.worldbody)

    def local_pose(
        self,
        frame: HasPose,
        relative_to: HasPose,
    ) -> PoseQuat:
        """
        Returns the pose of `frame` expressed in `relative_to`'s coordinate system.

        Always walks the live worldbody tree, so the result reflects the current
        state of the model regardless of any modifications since the last call.
        """
        return self.pose_context.local_pose(frame, relative_to)

    def prep_for_sim(
        self,
        save_path: Path | None = None,
        *,
        unit_system: UnitSystem | None = None,
        key: KeyName | int | None = None,
    ) -> MjState:
        """
        Creates an MjState (MjModel + MjData) from the Mujoco instance.

        The simulation starts from the key marked `initial`, or from the model's default state when no key is.

        Args:
            save_path: Where to write the model's XML, which is then compiled from that file. Without one the model is compiled from text.
            unit_system: The model's unit system, attached so that telemetry channels emit concrete unit strings instead of abstract Pint dimension expressions.
            key: A key to start from in place of the initial one: its name, or its index in the compiled model (what a viewer's key picker gives).

        """
        initial = self.initial_key
        if save_path:
            _, model = self._write_xml(save_path)
            if model is None:
                model = mujoco.MjModel.from_xml_path(str(save_path))
        else:
            model = self.to_mj_model()

        data = mujoco.MjData(model)
        start = key if key is not None else (initial.name if initial else None)
        if start is not None:
            mujoco.mj_resetDataKeyframe(model, data, _key_id(model, start))
        mujoco.mj_forward(model, data)
        mujoco.mj_rnePostConstraint(model, data)
        state = MjState(model, data)
        state.us = unit_system
        if unit_system is None:
            logger.warning(
                "No unit system declared on this model. Telemetry metadata will use "
                "abstract Pint dimension strings ([length], [mass]) instead of concrete "
                "units. Set mojo_model.us = UnitSystem.si() (or fps(), ips(), cgs()) "
                "to resolve this."
            )
        return state
