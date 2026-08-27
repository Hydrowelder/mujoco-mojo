from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import mujoco
from pydantic import Field

import mujoco_mojo.utils.utils as utils
from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.defaults import DEFAULT_ANGLE, DEFAULT_EULERSEQ
from mujoco_mojo.mjcf.extension import Extension
from mujoco_mojo.mjcf.mujoco_attr.actuator import Actuator
from mujoco_mojo.mjcf.mujoco_attr.asset import Asset
from mujoco_mojo.mjcf.mujoco_attr.body import WorldBody
from mujoco_mojo.mjcf.mujoco_attr.compiler import Compiler
from mujoco_mojo.mjcf.mujoco_attr.contact import Contact
from mujoco_mojo.mjcf.mujoco_attr.deformable import Deformable
from mujoco_mojo.mjcf.mujoco_attr.equality import Equality
from mujoco_mojo.mjcf.mujoco_attr.keyframe import Keyframe
from mujoco_mojo.mjcf.mujoco_attr.option import Option
from mujoco_mojo.mjcf.mujoco_attr.sensor import Sensor
from mujoco_mojo.mjcf.mujoco_attr.size import Size
from mujoco_mojo.mjcf.mujoco_attr.statistic import Statistic
from mujoco_mojo.mjcf.mujoco_attr.tendon import Tendon
from mujoco_mojo.mjcf.mujoco_attr.visual import Visual
from mujoco_mojo.mjcf.pose import PoseQuat
from mujoco_mojo.mjcf.pose_context import HasPose, PoseContext
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import Angle, EulerSeq, ModelName
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.utils import is_empty_list, to_pretty_xml

if TYPE_CHECKING:
    from mujoco_mojo.stochas import UnitSystem

logger = get_logger(__name__)

__all__ = ["Mujoco"]


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

        Args:
            file (Path): Filepath to save XML.
            exclude_default (bool, optional): Wheter or not to include default values. Values equal to None are always ignored. Attributes which are literals (such as Geom.type) are always included. Defaults to True.

        Returns:
            str: Prettified XML text.

        """
        xml = utils.to_pretty_xml(
            self.to_xml(
                exclude_default=exclude_default,
                compiler_degrees=self.compiler_degree_settings,
                compiler_eulerseq=self.compiler_eulerseq_settings,
            )
        )
        file.write_text(xml, encoding="utf-8")
        return xml

    def to_mj_spec(self) -> mujoco.MjSpec:
        """Creates an MjSpec from the Mujoco instance."""
        return mujoco.MjSpec.from_string(
            to_pretty_xml(
                self.to_xml(
                    compiler_degrees=self.compiler_degree_settings,
                    compiler_eulerseq=self.compiler_eulerseq_settings,
                )
            )
        )

    def to_mj_model(self) -> mujoco.MjModel:
        """Creates an MjModel from the Mujoco instance."""
        return mujoco.MjModel.from_xml_string(
            to_pretty_xml(
                self.to_xml(
                    compiler_degrees=self.compiler_degree_settings,
                    compiler_eulerseq=self.compiler_eulerseq_settings,
                )
            )
        )

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
        self, save_path: Path | None = None, *, unit_system: UnitSystem | None = None
    ) -> MjState:
        """Creates an MjState (MjModel + MjData) from the Mujoco instance. Pass `unit_system` to attach the model's unit system so that telemetry channels emit concrete unit strings instead of abstract Pint dimension expressions."""
        if save_path:
            self.write_xml(save_path)
            model = mujoco.MjModel.from_xml_path(str(save_path))
        else:
            model = self.to_mj_model()

        data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)
        mujoco.mj_rnePostConstraint(model, data)
        state = MjState(model, data)
        state.us = unit_system
        if unit_system is None:
            logger.warning(
                "No unit system declared on this model. Telemetry metadata will use "
                "abstract Pint dimension strings ([length], [mass]) instead of concrete "
                "units. Set mojo_model.u = UnitSystem.si() (or fps(), ips(), cgs()) "
                "to resolve this."
            )
        return state
