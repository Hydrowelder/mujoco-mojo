"""Global user settings for mujoco_mojo, persisted to ~/.mujoco-mojo/settings.toml."""

from __future__ import annotations

import ast
import inspect
import json
import textwrap
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, cast

import tomlkit
from dotenv import find_dotenv, load_dotenv
from filelock import FileLock
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    RootModel,
    SecretStr,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.json_schema import (
    GenerateJsonSchema,
    JsonSchemaMode,
    JsonSchemaValue,
    NoDefault,
)
from pydantic_core import CoreSchema, core_schema
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from tomlkit.items import Table

from mujoco_mojo.meta import MUJOCO_MOJO_DIR
from mujoco_mojo.typing import (
    Direction,
    ModelProvider,
    Sampler,
    SortDirection,
    SortMode,
    UserInterface,
)
from mujoco_mojo.utils.color import Color

SETTINGS_DIR = MUJOCO_MOJO_DIR
GLOBAL_SETTINGS_FILE = SETTINGS_DIR / "settings.toml"
SETTINGS_SCHEMA_FILE = SETTINGS_DIR / "settings.schema.json"
SETTINGS_TAPLO_FILE = SETTINGS_DIR / ".taplo.toml"

# resolved once, by walking up from *this file's own location* (not the
# process's current working directory) until a .env is found - "" if none
# exists anywhere above this file. A bare relative env_file=".env" (what
# MujocoMojoSettings used to pass to pydantic-settings below) only ever
# resolves against CWD with no upward search, so it silently found nothing
# whenever a command ran from anywhere other than the exact directory
# holding the .env file - e.g. this package's own src/ layout puts
# settings.py several directories below a repo-root .env.
_DOTENV_PATH = find_dotenv()

# populates the *real* process environment (os.environ) from that file, in
# addition to (not instead of) MujocoMojoSettings' own dotenv_settings
# source below. The two solve different problems: dotenv_settings only ever
# feeds values into this class's own MUJOCO_MOJO_-prefixed fields, while
# something like a pydantic_ai provider's GOOGLE_API_KEY/ANTHROPIC_API_KEY/etc.
# lookup calls os.getenv() directly, with no idea MujocoMojoSettings exists -
# only a real load_dotenv() call makes a plain .env entry visible there.
load_dotenv(_DOTENV_PATH)


def project_settings_file() -> Path:
    """
    Path to the project-local settings file, `<cwd>/.mujoco-mojo/settings.toml`.

    Computed fresh on every call rather than cached as a module-level constant, since `Path.cwd()` can legitimately differ across calls within one process (e.g. a long-running dashboard server, or tests).

    Returns:
        `Path.cwd() / ".mujoco-mojo" / "settings.toml"`.

    """
    return Path.cwd() / ".mujoco-mojo" / "settings.toml"


SlurmScalar = str | int | float | bool


_SBATCH_PREFIX = "sbatch."


def _is_color_widget_field(info: Any) -> bool:
    """Whether a `model_fields[name]` `FieldInfo` was tagged `json_schema_extra={"x-widget": "color"}` - the same tag the Dojo settings panel uses to pick a color-picker widget, reused here so a field only needs to be marked once to get both the frontend widget and this backend validation, instead of also being hand-listed in a separate tuple."""
    extra = info.json_schema_extra
    return isinstance(extra, dict) and extra.get("x-widget") == "color"


class VisualizationSettings(BaseModel):
    """Colors for force, torque, contact, and proximity overlays rendered during simulation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="Visualization",
        # x-icon: inner SVG markup (no outer <svg> tag - the Dojo settings
        # panel supplies that, with its own viewBox/stroke) shown next to
        # this section's title. Same json_schema_extra mechanism as
        # x-widget above: the schema is the single source of truth for
        # section metadata, not a second hand-maintained map in TypeScript.
        json_schema_extra={
            "x-icon": '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
        },
    )

    action_force: str | None = Field(
        default="EMERALD_500",
        title="Action Force Color",
        description='Color of action-site force arrows. Set to `""` to disable.',
        json_schema_extra={"x-widget": "color"},
    )

    reaction_force: str | None = Field(
        default="ROSE_500",
        title="Reaction Force Color",
        description='Color of reaction-site force arrows. Set to `""` to disable.',
        json_schema_extra={"x-widget": "color"},
    )

    torque: str | None = Field(
        default="AMBER_500",
        title="Torque Color",
        description='Color of torque arrows. Set to `""` to disable.',
        json_schema_extra={"x-widget": "color"},
    )

    reaction_torque: str | None = Field(
        default="FUCHSIA_500",
        title="Reaction Torque Color",
        description='Color of reaction-site torque arrows. Set to `""` to disable. Only applies to `BodyReactionForce` loads (`ScalarTorque`, `VectorTorque`, `GeneralLoad`) - `PointToPointForce` has no torque.',
        json_schema_extra={"x-widget": "color"},
    )

    contact: str | None = Field(
        default="CYAN_400",
        title="Contact Color",
        description='Color of contact force arrows. Set to `""` to disable.',
        json_schema_extra={"x-widget": "color"},
    )

    clearance_line: str | None = Field(
        default="WHITE",
        title="Clearance Line Color",
        description='Color of proximity clearance lines. Set to `""` to disable.',
        json_schema_extra={"x-widget": "color"},
    )

    trace_line: str | None = Field(
        default="VIOLET_500",
        title="Trace Line Color",
        description='Default color of `Tracer` trails. Set to `""` to disable. Overridden per-`Tracer` by passing `color`.',
        json_schema_extra={"x-widget": "color"},
    )

    force_length_scale: float = Field(
        default=1.0,
        title="Force Length Scale",
        description="Default length multiplier for action/reaction force arrows, on top of MuJoCo's native scaling. Overridden per-`Load` by `force_length_scale`.",
    )

    force_width_scale: float = Field(
        default=1.0,
        ge=0,
        title="Force Width Scale",
        description="Default width multiplier for action/reaction force arrows, on top of MuJoCo's native scaling. Overridden per-`Load` by `force_width_scale`.",
    )

    torque_length_scale: float = Field(
        default=1.0,
        title="Torque Length Scale",
        description="Default length multiplier for torque arrows, on top of MuJoCo's native scaling. Overridden per-`Load` by `torque_length_scale`.",
    )

    torque_width_scale: float = Field(
        default=1.0,
        ge=0,
        title="Torque Width Scale",
        description="Default width multiplier for torque arrows, on top of MuJoCo's native scaling. Overridden per-`Load` by `torque_width_scale`.",
    )

    @model_validator(mode="before")
    @classmethod
    def _parse_color_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        parsed = dict(data)
        for name, info in cls.model_fields.items():
            if name in parsed and _is_color_widget_field(info):
                parsed[name] = Color.parse(parsed[name])
        return parsed

    @model_serializer(mode="wrap")
    def _serialize_color_fields(self, handler: Any, info: Any) -> dict[str, Any]:
        data = handler(self)
        # exclude_none already dropped a None-valued color field from `data`
        # entirely (same as any other None field) - leave that alone. Only
        # when the caller *isn't* excluding Nones do we still want a hidden
        # color field to read as "" rather than null (its documented public
        # contract - see each field's description above).
        if info.exclude_none:
            return data
        for name, field_info in type(self).model_fields.items():
            if _is_color_widget_field(field_info) and getattr(self, name) is None:
                data[name] = ""
        return data


class SensAIModelEntry(BaseModel):
    """One entry in `SensAISettings.models` - a provider paired with that provider's own model identifier."""

    model_config = ConfigDict(extra="forbid", frozen=True, title="Model")

    provider: ModelProvider = Field(
        title="Provider",
        description="Which pydantic_ai provider to route this entry through.",
    )

    model_name: str = Field(
        title="Model Name",
        description="That provider's own identifier for the model, e.g. `gemini-3.5-flash-lite` for Google.",
    )


class SensAISettings(BaseModel):
    """Settings for the SensAI assistant embedded in the Dojo dashboard."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="SensAI",
        # the exact sparkles path from _sensai.html's own FAB button (the
        # chat window's open/close toggle), copied verbatim rather than
        # redrawn, so it's guaranteed to be the same glyph, not a lookalike.
        json_schema_extra={
            "x-icon": (
                '<path stroke-linecap="round" stroke-linejoin="round" '
                'd="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 '
                "5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 "
                "9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 "
                '2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z"/>'
            ),
        },
    )

    enabled: bool = Field(
        default=False,
        title="Enabled",
        description="Whether or not to activate AI features.",
    )

    models: list[SensAIModelEntry] = Field(
        default_factory=list,
        title="Models",
        description="Models to fall back through, in priority order: earlier entries are tried first. Each provider reads its own credentials from its own environment variable (see each option above).",
    )

    base_url: str = Field(
        default="http://localhost:11434/v1",
        title="Base URL",
        description="Only needed if one of the models above uses the Ollama provider. Ollama has no built-in localhost default, unlike every other provider here. Ignored otherwise.",
    )


class DojoSettings(BaseModel):
    """Settings for the Dojo dashboard."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="Dojo",
        # globe: simple primitives (circle + a vertical ellipse meridian +
        # a horizontal equator line), not a hand-typed curve path - see
        # CLAUDE.md's "no browser, no screenshots" verification note for
        # this repo's Dojo UI: a primitive can't come out visually wrong
        # the way a curve nobody rendered to check could.
        json_schema_extra={
            "x-icon": '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><line x1="3" y1="12" x2="21" y2="12"/>',
        },
    )

    sensai: SensAISettings = Field(
        default_factory=SensAISettings,
        description="Settings for the SensAI assistant.",
    )

    chime_enabled: bool = Field(
        default=True,
        title="Chime Enabled",
        description="\n\n".join(
            (
                "Whether to play a sound on the Dojo monitor page when a job finishes.",
                "Independent of `chime_source` (which picks *what* plays, not *whether* anything does) and of each browser's own mute toggle.",
            )
        ),
    )

    chime_source: Annotated[
        HttpUrl | Path | None,
        Field(union_mode="left_to_right"),
    ] = Field(
        default=None,
        title="Chime Source",
        description="Custom sound for the job-finished chime on the Dojo monitor page (needs `chime_enabled` on) - a web URL or local file path. Set safely with `mujoco-mojo settings set dojo.chime_source <path-or-url>`.",
    )

    show_quick_filters: bool = Field(
        default=True,
        title="Show Quick Filters",
        description="Show quick filter chips on the X-axis, Y-axis, and reference frame selectors - faster searching, at the cost of some extra space in the selection element.",
    )

    default_to_fullscreen: bool = Field(
        default=False,
        title="Default to Fullscreen",
        description="Pages in Dojo have an option to expand to fullscreen. Selecting this option will default your page load to fullscreen.",
    )

    password: SecretStr | None = Field(
        default=None,
        title="Password",
        description="Password for the Dojo dashboard's HTTP Basic Auth (username ignored). Applies every launch unless `--password` overrides it. Only a masked placeholder is saved - see `MUJOCO_MOJO_DOJO__PASSWORD`.",
    )

    hide_invalid_profiles: bool = Field(
        default=False,
        title="Hide Invalid Profiles",
        description="Hide saved plot profiles that reference columns not present in the current trial, in the Profiles file browser.",
    )

    profile_sort_mode: SortMode = Field(
        default=SortMode.MODIFIED,
        title="Profile Sort Mode",
        description="How the Profiles file browser sorts saved profiles.",
    )

    profile_sort_dir: SortDirection = Field(
        default=SortDirection.DESC,
        title="Profile Sort Direction",
        description="Sort direction for the Profiles file browser.",
    )

    hide_invalid_labs: bool = Field(
        default=False,
        title="Hide Invalid Labs",
        description="Hide saved Signal Lab graphs that reference columns not present in the current trial, in the Signal Lab file browser.",
    )

    lab_sort_mode: SortMode = Field(
        default=SortMode.MODIFIED,
        title="Lab Sort Mode",
        description="How the Signal Lab file browser sorts saved labs.",
    )

    lab_sort_dir: SortDirection = Field(
        default=SortDirection.DESC,
        title="Lab Sort Direction",
        description="Sort direction for the Signal Lab file browser.",
    )

    @field_validator("chime_source", mode="before")
    @classmethod
    def _empty_chime_is_unset(cls, v: Any) -> Any:
        # an empty/blank string must become None *before* the HttpUrl | Path
        # union sees it - pathlib.Path("") silently normalizes to Path('.')
        # rather than raising or staying empty, so without this an
        # explicitly-cleared chime_source (or a pre-existing
        # `chime_source = ""` in settings.toml) would load as "." instead
        # of unset.
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class SlurmExtraSettings(RootModel[dict[str, SlurmScalar]]):
    # e.g. `"sbatch.account": "proj123"` becomes `#SBATCH --account=proj123`;
    # `"MLM_LICENSE_FILE": "27000@license.internal"` becomes
    # `export MLM_LICENSE_FILE="27000@license.internal"`. Nested objects/arrays
    # are rejected at load time - this can only ever describe a flat set of
    # settings, the shape of `MujocoMojoSettings.slurm`, layered automatically
    # between the global and project-local settings files (see
    # `project_settings_file`). Kept out of the docstring below (unlike this
    # comment, that becomes the JSON schema description shown in the Dojo
    # settings panel's hint bar - see settings_test.py's length-guard test.)
    """Flat key-value pairs used to extend a SLURM submission. `sbatch.`-prefixed keys become `#SBATCH` lines; everything else becomes an exported environment variable. Values must be scalars."""

    model_config = ConfigDict(
        title="Slurm",
        frozen=True,
        # An approximation, not a traced reproduction of the real Slurm
        # wordmark/logo - a hexagon (cluster/node motif, thematically
        # fitting for an HPC scheduler) with a center dot. This repo's Dojo
        # UI changes are verified by build/typecheck only (see CLAUDE.md),
        # never a rendered screenshot, and there's no reliable, verified
        # reference for the actual logo's geometry to trace faithfully
        # here - flagging that rather than guessing with false confidence.
        json_schema_extra={
            "x-icon": '<polygon points="12,2 20,7 20,17 12,22 4,17 4,7"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/>',
        },
    )

    def sbatch_lines(self) -> list[str]:
        return [
            f"#SBATCH --{key[len(_SBATCH_PREFIX) :]}={value}"
            for key, value in self.root.items()
            if key.startswith(_SBATCH_PREFIX)
        ]

    def env_lines(self) -> list[str]:
        return [
            f'export {key}="{value}"'
            for key, value in self.root.items()
            if not key.startswith(_SBATCH_PREFIX)
        ]


class GeneralSettings(BaseModel):
    """General-purpose defaults shared across `mujoco-mojo`'s CLI commands, plus asset-bundling behavior."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="General",
        # stacked boxes: two overlapping rounded squares, offset diagonally.
        json_schema_extra={
            "x-icon": '<rect x="3" y="9" width="12" height="12" rx="1.5"/><rect x="8" y="3" width="12" height="12" rx="1.5"/>',
        },
    )

    symlink: bool = Field(
        default=False,
        title="Symlink",
        description="Link to dependency files instead of copying when bundling - saves disk space, but the bundle is no longer self-contained (breaks if moved without its sources). Ignored on Windows (always copies).",
    )

    verbose: int = Field(
        default=0,
        ge=0,
        title="Verbose",
        description="Baseline verbosity, added to however many times `-v`/`--verbose` is repeated on the command line.",
    )

    quiet: int = Field(
        default=0,
        ge=0,
        title="Quiet",
        description="Baseline quietness, added to however many times `-q`/`--quiet` is repeated on the command line.",
    )

    model_config_name: str | None = Field(
        default=None,
        title="Model Config Name",
        description="Default file name for a dumped model config (e.g. `model_config.json`). Leave unset to not dump one.",
    )

    xml_name: str = Field(
        default="model.xml",
        title="XML Name",
        description="Default file name for the generated MJCF XML file.",
    )

    n_proc: int = Field(
        default=1,
        ge=1,
        title="Parallel Processes",
        description="Default number of parallel processes for Monte Carlo/optimization trials and Dojo's status-file rescanning.",
    )

    default_host: str = Field(
        default="127.0.0.1",
        title="Default Host",
        description="Default host IP for `mujoco-mojo dojo` and `mujoco-mojo reloaded`'s web-based viewers.",
    )

    default_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        title="Default Port",
        description="Starting port for `dojo`/`reloaded`'s web viewers - both probe upward and bind the first free one, so running both with no `--port` never collides.",
    )


class ReloadedSettings(BaseModel):
    """Settings for `mujoco-mojo reloaded`."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="Reloaded",
        # a reload/refresh arrow: two arcs forming a broken circle with an
        # arrowhead, built from primitives (a path arc + a small triangle)
        # rather than a hand-traced icon-font glyph.
        json_schema_extra={
            "x-icon": '<path d="M4 12a8 8 0 0 1 14-5.3M20 12a8 8 0 0 1-14 5.3"/><polygon points="18,3 18,8 13,8"/><polygon points="6,21 6,16 11,16"/>',
        },
    )

    ui: UserInterface = Field(
        default=UserInterface.OPENGL,
        title="UI Backend",
        description="Which viewer backend to use.",
    )

    watch: bool = Field(
        default=True,
        title="Watch",
        description="Automatically reload when `*.py` source files change.",
    )

    record: bool = Field(
        default=False,
        title="Record",
        description="Record telemetry to a per-trial `telemetry.parquet` and capture frames for any registered video recorders. Off by default since interactive sessions can run indefinitely.",
    )


class _RunDefaults(BaseModel):
    """Fields shared by every `mujoco-mojo run` subcommand."""

    # inherited by every subclass below (MonteCarloRunSettings, etc.) - a
    # subclass's own model_config only overrides the keys it explicitly
    # sets, so this one doesn't need repeating on each of them.
    model_config = ConfigDict(frozen=True)

    resume: bool = Field(
        default=True,
        title="Resume",
        description="Resume from previous state on disk.",
    )

    clean_workdir: bool = Field(
        default=False,
        title="Clean Working Directory",
        description="Delete the workdir before running (mutually exclusive with `resume`).",
    )


class MonteCarloRunSettings(_RunDefaults):
    """Settings for `mujoco-mojo run monte-carlo`."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="Monte Carlo",
        # a die face: a rounded square with a five-pip pattern.
        json_schema_extra={
            "x-icon": '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.2" fill="currentColor" stroke="none"/><circle cx="16" cy="8" r="1.2" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="8" cy="16" r="1.2" fill="currentColor" stroke="none"/><circle cx="16" cy="16" r="1.2" fill="currentColor" stroke="none"/>',
        },
    )


class SingleRunSettings(_RunDefaults):
    """Settings for `mujoco-mojo run single`."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="Single",
        # a plain box.
        json_schema_extra={
            "x-icon": '<rect x="4" y="4" width="16" height="16" rx="2"/>',
        },
    )


class OptimizeRunSettings(_RunDefaults):
    """Settings for `mujoco-mojo run optimization`."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="Optimize",
        # a small network graph: three nodes joined by two edges.
        json_schema_extra={
            "x-icon": '<circle cx="12" cy="4" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><line x1="12" y1="6" x2="6" y2="17.3"/><line x1="12" y1="6" x2="18" y2="17.3"/>',
        },
    )

    study_name: str = Field(
        default="mojo-study",
        title="Study Name",
        description="Unique identifier for the Optuna study. Useful for resuming or tracking in a database.",
    )

    sampler: Sampler = Field(
        default=Sampler.TPE,
        title="Sampler",
        description="The search algorithm to use.",
    )

    direction: Direction = Field(
        default=Direction.MINIMIZE,
        title="Direction",
        description="The optimization goal.",
    )

    storage: bool = Field(
        default=True,
        title="Storage",
        description="Whether to use database storage. Required for multi-process optimization.",
    )

    timeout: float | None = Field(
        default=None,
        title="Timeout",
        description="Stop searching for new design parameters after this many seconds have elapsed. Leave unset to run without a timeout.",
    )

    evals_per_trial: int = Field(
        default=1,
        ge=1,
        title="Evaluations per Trial",
        description="Number of evaluations (different seeds) per trial to average.",
    )

    refine_search_factor: float | None = Field(
        default=None,
        title="Refine Search Factor",
        description="Shrink search bounds by this factor on resume (0.1 = aggressive). Leave unset to disable.",
    )

    prune_failed_trials: bool = Field(
        default=True,
        title="Prune Failed Trials",
        description="Immediately stop trials that hit physics instabilities.",
    )


class RunSettings(BaseModel):
    """Settings for `mujoco-mojo run`'s subcommands."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        title="Run",
        # a solid running-figure silhouette, unlike every other icon here -
        # a user-supplied glyph (SVG Repo, fill-based) rather than a
        # hand-drawn stroke primitive, so it's reproduced verbatim
        # (`d` untouched) instead of hand-traced. Its native viewBox
        # ("-48 0 512 512") doesn't match the 0-24 viewBox every x-icon
        # renders into (base.html's wrapping <svg>), so a `transform`
        # remaps it instead of hand-editing its coordinates: `translate(48,
        # 0)` first shifts x from [-48, 464] to [0, 512] (y is already
        # [0, 512]), then `scale(24/512)` fits that into [0, 24] on both
        # axes - transforms apply right-to-left, so translate runs before
        # scale. `fill="currentColor" stroke="none"` overrides the wrapping
        # <svg>'s own `fill="none" stroke="currentColor"` locally, since
        # this glyph (unlike this file's other icons) is a filled
        # silhouette, not line art. Verified by rendering the exact
        # transformed markup, wrapped exactly as the frontend wraps it, to
        # a PNG at both full size and this icon's actual ~20px display
        # size, and inspecting both directly.
        json_schema_extra={
            "x-icon": '<path d="M272 96c26.51 0 48-21.49 48-48S298.51 0 272 0s-48 21.49-48 48 21.49 48 48 48zM113.69 317.47l-14.8 34.52H32c-17.67 0-32 14.33-32 32s14.33 32 32 32h77.45c19.25 0 36.58-11.44 44.11-29.09l8.79-20.52-10.67-6.3c-17.32-10.23-30.06-25.37-37.99-42.61zM384 223.99h-44.03l-26.06-53.25c-12.5-25.55-35.45-44.23-61.78-50.94l-71.08-21.14c-28.3-6.8-57.77-.55-80.84 17.14l-39.67 30.41c-14.03 10.75-16.69 30.83-5.92 44.86s30.84 16.66 44.86 5.92l39.69-30.41c7.67-5.89 17.44-8 25.27-6.14l14.7 4.37-37.46 87.39c-12.62 29.48-1.31 64.01 26.3 80.31l84.98 50.17-27.47 87.73c-5.28 16.86 4.11 34.81 20.97 40.09 3.19 1 6.41 1.48 9.58 1.48 13.61 0 26.23-8.77 30.52-22.45l31.64-101.06c5.91-20.77-2.89-43.08-21.64-54.39l-61.24-36.14 31.31-78.28 20.27 41.43c8 16.34 24.92 26.89 43.11 26.89H384c17.67 0 32-14.33 32-32s-14.33-31.99-32-31.99z" fill="currentColor" stroke="none" transform="scale(0.046875) translate(48,0)"/>',
        },
    )

    monte_carlo: MonteCarloRunSettings = Field(default_factory=MonteCarloRunSettings)
    single: SingleRunSettings = Field(default_factory=SingleRunSettings)
    optimize: OptimizeRunSettings = Field(default_factory=OptimizeRunSettings)


_SCHEMA_HEADER = "#:schema settings.schema.json"


def _ensure_schema_header(text: str) -> str:
    """
    Prepends the `#:schema settings.schema.json` header to raw TOML `text` if its first line isn't already that header, so a settings.toml written before schema support existed - or hand-edited to drop the line - gets it back on the next save.

    Operates on the raw text rather than a parsed `tomlkit` document because `tomlkit.Container` keeps a private key->index map alongside its body list; splicing an item into `doc.body` directly (as opposed to through `Container.__setitem__`/`add`) leaves that map's indices stale and corrupts later in-place edits.
    """
    lines = text.splitlines()
    if lines and lines[0].strip() == _SCHEMA_HEADER:
        return text
    return f"{_SCHEMA_HEADER}\n\n{text}"


def _merge_into_toml(
    doc: tomlkit.TOMLDocument | Table,
    data: dict[str, Any],
    model_cls: type[BaseModel] | None,
) -> None:
    """
    Writes `data` into an existing `tomlkit` document or table, key by key, so any comments and formatting attached to a key that already exists survive.

    A key present in `doc` but absent from `data` is normally left alone rather than deleted - for a fixed-schema section (e.g. `[dojo.sensai]`), a key can only be absent from `data` because `exclude_none` omitted an unset `Optional` field, and leaving whatever was last written for it untouched is the right call. That reasoning doesn't hold for a free-form (`RootModel`-backed) table like `[slurm]`: every key in `data` there *is* the complete, authoritative set of entries the caller wants, so a table for one of those fields is fully replaced instead (stale keys deleted) - otherwise, removing an entry via the Dojo settings panel wouldn't actually delete it from settings.toml, and it would silently reappear on the next load.

    Args:
        doc: A parsed `tomlkit` document or table to update in place.
        data: Nested settings data, as returned by `MujocoMojoSettings.model_dump()`.
        model_cls: The Pydantic model `data` was dumped from, used to look up each key's declared field type - `None` once recursed into a free-form table, whose own keys aren't declared fields of anything.

    """
    for key, value in data.items():
        field_info = model_cls.model_fields.get(key) if model_cls else None
        annotation = field_info.annotation if field_info else None
        nested_model = (
            annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel)
            else None
        )
        is_root_model = nested_model is not None and issubclass(nested_model, RootModel)

        if isinstance(value, dict):
            if key not in doc or not isinstance(doc[key], (Table, dict)):
                doc[key] = tomlkit.table()
            elif is_root_model:
                for stale_key in [k for k in doc[key] if k not in value]:
                    del doc[key][stale_key]
            _merge_into_toml(doc[key], value, None if is_root_model else nested_model)
        else:
            doc[key] = value


def _enum_value_descriptions(enum_cls: type[Enum]) -> dict[str, str]:
    """
    Maps each member's own VALUE (not its Python attribute name) to the
    attribute-docstring immediately following its assignment, e.g. a
    GridMode.ALL member documented with its own docstring ("Major and minor
    tick grid lines.") becomes `{"all": "Major and minor tick grid lines."}`.

    This is the same convention `ConfigDict(use_attribute_docstrings=True)`
    reads for model fields, applied here to plain Enum members instead -
    that pydantic config option doesn't cover them itself, since its
    extraction (pydantic._internal._docs_extraction) only visits
    *annotated* assignments (`x: int = 1`), not an Enum member's bare
    `X = 1`. Standard JSON Schema's `enum` keyword has no room for
    per-value metadata, so `GenerateJsonSchemaWithDefaults.enum_schema`
    below attaches this as an `x-enum-descriptions` extension instead of
    trying to reshape `enum` into `oneOf`.

    Returns {} if the source isn't available (e.g. a dynamically-built
    enum) rather than raising - a missing per-value description just means
    a caller's tooltip has nothing to show, not a broken schema endpoint.
    """
    try:
        source = inspect.getsource(enum_cls)
        tree = ast.parse(textwrap.dedent(source))
    except (OSError, TypeError, SyntaxError):
        return {}
    class_def = tree.body[0]
    if not isinstance(class_def, ast.ClassDef):
        return {}
    result: dict[str, str] = {}
    pending_name: str | None = None
    for node in class_def.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            pending_name = node.targets[0].id
            continue
        if (
            pending_name is not None
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            member = getattr(enum_cls, pending_name, None)
            if member is not None:
                result[str(member.value)] = inspect.cleandoc(node.value.value)
        pending_name = None
    return result


class GenerateJsonSchemaWithDefaults(GenerateJsonSchema):
    """
    Appends each field's default value to its `description`, so editors that only surface `description` on hover (e.g. VS Code's Even Better TOML) still show it, without hand-duplicating every `Field(default=...)` into its own description text.

    Also attaches an `x-enum-descriptions` extension (value -> that member's own attribute-docstring, via `_enum_value_descriptions` above) to every enum schema - generic to any StrEnum with attribute-docstring'd members, not specific to whichever model happens to use this generator, so a consumer like the Dojo settings panel and PlotConfig's Plot Editor/JSON editor tooltips (dojo/plot_config.py) both get per-dropdown-option descriptions for free from the same one generator, rather than each redefining this behavior in its own subclass.
    """

    def generate(
        self, schema: CoreSchema, mode: JsonSchemaMode = "validation"
    ) -> JsonSchemaValue:
        json_schema = super().generate(schema, mode=mode)
        defs = json_schema.get("$defs", {})
        self._append_defaults(json_schema, defs)
        for definition in defs.values():
            self._append_defaults(definition, defs)
        return json_schema

    def get_default_value(self, schema: core_schema.WithDefaultSchema) -> Any:
        """
        Pydantic's own default implementation only ever surfaces a static `default=`, never a `default_factory=` result, since a factory could be expensive or side-effecting. Every `default_factory` actually used across this codebase (`dict`, `list`, `lambda: SlurmExtraSettings({})`, and the nested settings-group constructors) is cheap and side-effect-free, so calling it here is safe, and it's what lets `_append_defaults` below show a real "Default: ..." for fields like `PlotConfig.y_axes`/`annotations`/`shapes` that would otherwise silently show none.
        """
        default = super().get_default_value(schema)
        if default is not NoDefault:
            return default
        factory = schema.get("default_factory")
        if factory is None or schema.get("default_factory_takes_data"):
            return NoDefault
        # `default_factory_takes_data` being falsy is what actually
        # guarantees the zero-argument overload at runtime; the stub's
        # `Callable[[], Any] | Callable[[dict[str, Any]], Any]` union
        # can't express that correlation itself.
        no_arg_factory = cast("Callable[[], Any]", factory)
        try:
            return no_arg_factory()
        except Exception:
            return NoDefault

    @staticmethod
    def _append_defaults(
        node: JsonSchemaValue, defs: dict[str, JsonSchemaValue]
    ) -> None:
        for prop_name, prop in node.get("properties", {}).items():
            ref = prop.get("$ref")
            if not ref:
                all_of = prop.get("allOf")
                if isinstance(all_of, list) and len(all_of) == 1:
                    ref = all_of[0].get("$ref")
            target = defs.get(ref.removeprefix("#/$defs/")) if ref else None
            if target is not None and "properties" in target:
                # a field whose value is itself a nested named model (e.g.
                # MujocoMojoSettings.dojo/visualization/assets) - that
                # model's own leaf fields already carry their own
                # "Default: ..." individually, so repeating the whole
                # nested object here would just dump an unreadable wall of
                # JSON into one description line. An enum field is also a
                # bare $ref (e.g. YAxisConfig.dash -> #/$defs/DashStyle),
                # but its $defs target has no "properties" key (it's an
                # "enum"/"type" leaf, not a modeled object), so it isn't
                # caught by this check and still gets its default appended
                # (and inlined below).
                continue
            if "default" in prop and "description" in prop:
                default = prop["default"]
                rendered = (
                    ("true" if default else "false")
                    if isinstance(default, bool)
                    else "(empty)"
                    if default == ""
                    else str(default)
                )
                prop["description"] = f"{prop['description']}\n\nDefault: `{rendered}`"
            if target is not None and "enum" in target:
                # an enum field ends up here as a bare `$ref` (or
                # allOf-wrapped `$ref`) with `default`/`description` as
                # sibling keys next to it, since it isn't caught by the
                # nested-model check above (checking "not an object with
                # properties" alone isn't enough to mean "is an enum" - a
                # dict-shaped RootModel like SlurmExtraSettings also lacks
                # "properties" but must keep its $ref, since the settings
                # panel resolves that ref for the section's own title/
                # x-icon/additionalProperties; checking for "enum" directly
                # is what actually distinguishes the two). JSON Schema
                # 2020-12 (what pydantic emits) allows sibling keywords next
                # to a $ref, but not every consumer of this schema honors
                # them - taplo in particular resolves the ref and shows only
                # the enum type's own generic description, silently
                # dropping this property's freshly-appended "Default: ..."
                # line (and every other per-field override) instead of
                # merging them. Inlining the enum definition's own `enum`/
                # `type`/`x-enum-descriptions` directly into the property
                # and dropping the `$ref`/`allOf` indirection entirely
                # removes the ambiguity for every consumer at once - the
                # same shape a plain (non-shared) `Literal`-typed field
                # already gets for free, since pydantic never gives those a
                # `$ref` to begin with. The enum type's own title (e.g.
                # "SortMode") is deliberately NOT copied here: pydantic
                # never generates a title for a bare-$ref property itself
                # (a plain field like n_proc gets one, but not this kind),
                # relying on a consumer resolving the $ref and using the
                # target's title instead - which is exactly what dropping
                # the $ref here breaks. Backfilling from the field name
                # below (the same naive field_name.replace("_", " ").title()
                # algorithm pydantic itself uses for a plain field) is what
                # actually replaces what was lost, instead of leaving the
                # frontend's raw-snake_case-key fallback as the only option.
                prop.pop("$ref", None)
                prop.pop("allOf", None)
                for key in ("type", "enum", "x-enum-descriptions"):
                    if key in target and key not in prop:
                        prop[key] = target[key]
                if "title" not in prop:
                    prop["title"] = prop_name.replace("_", " ").title()

    def enum_schema(self, schema: core_schema.EnumSchema) -> JsonSchemaValue:
        result = super().enum_schema(schema)
        descriptions = _enum_value_descriptions(schema["cls"])
        if schema["cls"] is ModelProvider:
            # ModelProvider has no attribute-docstrings of its own (nothing worth
            # saying statically beyond the provider's name) - what's useful here,
            # each member's environment variable, only exists as a computed
            # property (see ModelProvider.env_var_name's own docstring for why
            # it can't be a lookup table), so it's merged in here instead of
            # written by hand into descriptions above.
            descriptions = {
                **descriptions,
                **{
                    member.value: f"Set via the `{env_var}` environment variable."
                    for member in ModelProvider
                    if (env_var := member.env_var_name) is not None
                },
            }
        if descriptions:
            result["x-enum-descriptions"] = descriptions
        return result


class MujocoMojoSettings(BaseSettings):
    """
    Global user-level settings persisted to ~/.mujoco-mojo/settings.toml, layered with an optional project-local override file - the same User-settings-vs-Workspace-settings model VS Code uses.

    Instantiate to load. Sources are checked in priority order: constructor kwargs > environment variables > `.env` file (`env_file` in `model_config`) > project settings file (`project_settings_file()`, `<cwd>/.mujoco-mojo/settings.toml`) > global settings file (`~/.mujoco-mojo/settings.toml`) > defaults. Every field can be overridden at the project level, not just a specific subset - a project file is expected to hold only the handful of keys that genuinely differ from the global defaults (e.g. per-project SLURM extras or force-scaling), not a full copy. Environment variables (real ones and `.env` entries alike) use the prefix `MUJOCO_MOJO_` with `__` as the nested delimiter, e.g. `MUJOCO_MOJO_DOJO__SENSAI__MODEL_NAME=llama3.2:3b`.
    """

    model_config = SettingsConfigDict(
        toml_file=GLOBAL_SETTINGS_FILE,
        env_prefix="MUJOCO_MOJO_",
        env_nested_delimiter="__",
        frozen=True,
        # an absolute path (not a bare ".env") so this resolves the same way
        # regardless of the process's current working directory - see
        # _DOTENV_PATH's own comment above for why a relative one doesn't.
        env_file=_DOTENV_PATH or None,
        env_file_encoding="utf-8",
        # a .env file is often shared with other tools, so it may well carry
        # secrets (e.g. GITHUB_TOKEN) that have nothing to do with mujoco-mojo -
        # BaseSettings otherwise defaults to extra="forbid", and pydantic-settings'
        # DotEnvSettingsSource stuffs every unmatched .env key into the data dict
        # regardless of prefix, so without this an unrelated secret would crash
        # settings loading entirely. Nested settings models (DojoSettings,
        # SensAISettings, etc.) keep their own extra="forbid", so a typo inside an
        # actual mujoco-mojo table is still caught.
        extra="ignore",
    )

    general: GeneralSettings = Field(
        default_factory=GeneralSettings,
        description="General-purpose CLI defaults, plus settings for how dependency files get bundled into a shared assets folder.",
    )

    visualization: VisualizationSettings = Field(
        default_factory=VisualizationSettings,
        description="Colors and visibility for simulation visual overlays.",
    )

    dojo: DojoSettings = Field(
        default_factory=DojoSettings,
        description="Settings for the Dojo dashboard.",
    )

    reloaded: ReloadedSettings = Field(
        default_factory=ReloadedSettings,
        description="Settings for `mujoco-mojo reloaded`.",
    )

    run: RunSettings = Field(
        default_factory=RunSettings,
        description="Settings for `mujoco-mojo run`'s subcommands.",
    )

    slurm: SlurmExtraSettings = Field(
        default_factory=lambda: SlurmExtraSettings({}),
        description="Extra SLURM `#SBATCH` lines / env vars for every submission. `sbatch.`-prefixed keys (e.g. `sbatch.account`) become `#SBATCH` lines; everything else is an exported environment variable.",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls, toml_file=project_settings_file()),
            TomlConfigSettingsSource(settings_cls, toml_file=GLOBAL_SETTINGS_FILE),
        )

    @classmethod
    def defaults(cls) -> MujocoMojoSettings:
        """
        Builds a fresh instance from pure code-level defaults, ignoring environment variables and any existing settings.toml.

        A constructor kwarg left unset resolves against this class's other settings sources (env vars, then the TOML file) rather than the field's own default - that layering is the entire reason `BaseSettings` exists - so every field's default must be passed explicitly here to get a true reset. Iterating `model_fields` rather than hand-listing field names means a newly added settings field is automatically covered, with nothing to remember to update.

        Returns:
            A `MujocoMojoSettings` instance with every field at its code-level default.

        """
        field_defaults = {
            name: info.get_default(call_default_factory=True)
            for name, info in cls.model_fields.items()
        }
        return cls(**field_defaults)

    @classmethod
    def set_project_value(cls, key: str, value: Any) -> None:
        """
        Sets a single dotted-path setting (e.g. "assets.symlink") in the project-local settings file, creating any intermediate tables as needed, without touching anything else already there.

        `key.split(".")` is ambiguous for a free-form group like `slurm` (a `RootModel[dict[str, ...]]`), whose own keys legitimately contain literal dots (e.g. `"sbatch.account"`) - `"slurm.sbatch.account"` must set that one flat key, not descend two more table levels. Resolved by walking the *declared field types* (not the current data) until a `RootModel` field is reached; everything after that point is rejoined into a single literal key instead of split further.

        Validated by overlaying the new value onto the full currently-effective settings (project + global + env + defaults) and calling `model_validate` on the result - `model_config` forbids extra fields on every fixed-shape settings group, so a typo'd leaf and a wrong-typed value both raise `pydantic.ValidationError` before anything is written. The *validated and re-dumped* leaf value is what actually gets persisted, not the raw `value` argument, so e.g. the CLI's loosely-typed input string `"true"` for a `bool` field is written to TOML as a real boolean, not a quoted string. Only that one changed leaf is written into the project file, keeping it a small, deliberate diff rather than a full mirror of every setting - contrast with `save()`, which always persists every field (correct for the global file, wrong here).

        Args:
            key: Dotted path, e.g. "dojo.sensai.base_url", "assets.symlink", or "slurm.sbatch.account".
            value: The value to set, already parsed to its target Python type.

        Raises:
            KeyError: If an intermediate segment of `key` isn't a real settings table.
            pydantic.ValidationError: If the resulting settings are invalid (unknown leaf, wrong type, etc.).

        """
        parts = key.split(".")

        # stop splitting once a free-form (RootModel) group is reached - the
        # rest of the path is that group's own literal key, dots and all
        model: type[BaseModel] = cls
        for i, part in enumerate(parts[:-1]):
            field_info = model.model_fields.get(part)
            annotation = field_info.annotation if field_info else None
            if not (isinstance(annotation, type) and issubclass(annotation, BaseModel)):
                msg = f"Unknown settings path: {key}"
                raise KeyError(msg)
            if issubclass(annotation, RootModel):
                parts = [*parts[: i + 1], ".".join(parts[i + 1 :])]
                break
            model = annotation

        # mode="json" turns any SecretStr field into its masked string rather
        # than a raw object tomlkit can't write, and exclude_none=True omits
        # an unset Optional field entirely - see save()
        effective = cls().model_dump(mode="json", exclude_none=True)
        overlay = effective
        for part in parts[:-1]:
            nxt = overlay.get(part)
            if not isinstance(nxt, dict):
                msg = f"Unknown settings path: {key}"
                raise KeyError(msg)
            overlay = nxt
        overlay[parts[-1]] = value
        validated = cls.model_validate(effective).model_dump(
            mode="json", exclude_none=True
        )

        coerced = validated
        for part in parts[:-1]:
            coerced = coerced[part]
        coerced_leaf = coerced[parts[-1]]

        path = project_settings_file()
        if path.exists():
            doc = tomlkit.parse(path.read_text(encoding="utf-8"))
        else:
            # model_construct() bypasses BaseSettings' usual env/TOML-reading
            # __init__ entirely - safe here since save(project=True) never
            # reads the instance's field values, and this path must not
            # require the *global* settings file (a wholly separate file) to
            # currently be valid just to bootstrap a fresh project file
            cls.model_construct().save(path.parent, project=True)
            doc = tomlkit.parse(path.read_text(encoding="utf-8"))

        node = doc
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], (Table, dict)):
                node[part] = tomlkit.table()
            node = node[part]
        node[parts[-1]] = coerced_leaf

        path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    def save(self, directory: Path | None = None, *, project: bool = False) -> Path:
        """
        Persist settings to `directory` (defaults to the global settings directory, `~/.mujoco-mojo`), alongside a freshly (re)generated `settings.schema.json`/`.taplo.toml` pair (see `write_schema_files`) - one method covers both the global settings file and a project-local override file, so there's no separate `init_project_file`-style method to keep in sync with this one.

        `project=False` (the default - the global file): every field's current value is merged into `settings.toml` with `tomlkit`, preserving any comments or formatting added by hand. A key that exists in the file but no longer has a corresponding settings value (e.g. a removed `slurm` entry) is left as-is rather than deleted.

        `project=True` (for `<cwd>/.mujoco-mojo/settings.toml`): `self`'s field values are never written - a project file is meant to hold only a small, deliberate diff from the global defaults, not a full mirror of every setting (see `set_project_value`) - so an existing file's contents are left completely untouched, and a fresh one gets just the `#:schema` header. Also drops a `.gitignore` (`*`) next to it if one isn't already there, so a project's local overrides - which may be machine-specific - don't get committed by accident.

        Either way, a brand-new file starts with a `#:schema` header pointing at the colocated settings.schema.json - a bare relative filename, resolved by taplo against the TOML file's own directory, rather than a cross-directory reference to another directory's schema. The latter is what broke under SSH/SSHFS-style setups where only one of the two directories was visible to the editor - every settings directory is now self-contained. An existing file that's missing that header (written before schema support existed, or hand-edited to drop the line) gets it prepended on the next save too, except for the already-exists project-file case just above, which skips reading the file at all.

        Args:
            directory: Where to write `settings.toml`, `settings.schema.json`, and `.taplo.toml`. Defaults to `SETTINGS_DIR` (looked up at call time, not import time, so tests can monkeypatch it).
            project: Write the sparse project-local form described above instead of the full global one.

        Returns:
            The `settings.toml` path written to.

        """
        if directory is None:
            directory = SETTINGS_DIR
        directory.mkdir(parents=True, exist_ok=True)
        toml_path = directory / "settings.toml"

        if project:
            gitignore = directory / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text("*\n", encoding="utf-8")

        if not (project and toml_path.exists()):
            # guards the read-modify-write below against concurrent writers -
            # the CLI, the Dojo settings panel, and multiple browser tabs can
            # all call save() around the same time
            lock_path = toml_path.with_suffix(toml_path.suffix + ".lock")
            with FileLock(lock_path):
                if toml_path.exists():
                    text = _ensure_schema_header(toml_path.read_text(encoding="utf-8"))
                    doc = tomlkit.parse(text)
                else:
                    doc = tomlkit.parse("#:schema settings.schema.json\n")

                if not project:
                    # mode="json" turns any SecretStr field (e.g. dojo.password)
                    # into its masked "**********" string rather than a raw object
                    # tomlkit can't write at all - the real value is never persisted
                    # by this method. exclude_none=True omits an unset Optional field
                    # (e.g. dojo.chime) entirely, since TOML has no null literal to write.
                    _merge_into_toml(
                        doc, self.model_dump(mode="json", exclude_none=True), type(self)
                    )

                toml_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

        self.write_schema_files(directory)
        return toml_path

    @classmethod
    def write_schema_files(cls, directory: Path | None = None) -> None:
        """
        Writes settings.schema.json and a companion .taplo.toml into `directory`, so taplo-based editors (VS Code's Even Better TOML, Neovim, etc.) get hover hints and validation for whatever settings.toml lives there. Safe to re-run any time, e.g. after upgrading mujoco-mojo changes the settings shape.

        The schema and taplo config are always colocated with the settings.toml they describe, rather than one directory's file referencing another's schema by absolute path - that cross-directory reference is exactly what broke under SSH/SSHFS-style setups where only one of the two directories (typically just the project one) is visible to the editor.

        Args:
            directory: Where to write `settings.schema.json` and `.taplo.toml`. Defaults to `SETTINGS_DIR` (looked up at call time, not import time, so tests can monkeypatch it).

        """
        if directory is None:
            directory = SETTINGS_DIR
        directory.mkdir(parents=True, exist_ok=True)

        schema_file = directory / "settings.schema.json"
        taplo_file = directory / ".taplo.toml"

        schema = cls.model_json_schema(schema_generator=GenerateJsonSchemaWithDefaults)
        schema_file.write_text(json.dumps(schema), encoding="utf-8")

        # taplo requires a file:// URI for the schema url - a relative path is not supported
        schema_uri = schema_file.as_uri()
        taplo_file.write_text(
            f'[[rule]]\ninclude = ["settings.toml"]\n\n[rule.schema]\nurl = "{schema_uri}"\n',
            encoding="utf-8",
        )
