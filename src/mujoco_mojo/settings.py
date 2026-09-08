"""Global user settings for mujoco_mojo, persisted to ~/.mujoco-mojo/settings.toml."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import tomlkit
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
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaMode, JsonSchemaValue
from pydantic_core import CoreSchema
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from tomlkit.items import Table

from mujoco_mojo.meta import MUJOCO_MOJO_DIR
from mujoco_mojo.utils.color import Color

SETTINGS_DIR = MUJOCO_MOJO_DIR
GLOBAL_SETTINGS_FILE = SETTINGS_DIR / "settings.toml"
SETTINGS_SCHEMA_FILE = SETTINGS_DIR / "settings.schema.json"
SETTINGS_TAPLO_FILE = SETTINGS_DIR / ".taplo.toml"


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
        description='Color of action-site force arrows. Set to `""` to disable.',
        json_schema_extra={"x-widget": "color"},
    )

    reaction_force: str | None = Field(
        default="ROSE_500",
        description='Color of reaction-site force arrows. Set to `""` to disable.',
        json_schema_extra={"x-widget": "color"},
    )

    torque: str | None = Field(
        default="AMBER_500",
        description='Color of torque arrows. Set to `""` to disable.',
        json_schema_extra={"x-widget": "color"},
    )

    reaction_torque: str | None = Field(
        default="FUCHSIA_500",
        description='Color of reaction-site torque arrows. Set to `""` to disable. `PointToPointForce` has no torque component (it\'s a scalar force along the line of action between two sites), so this only ever applies to `BodyReactionForce`-derived loads (`ScalarTorque`, `VectorTorque`, `GeneralLoad`).',
        json_schema_extra={"x-widget": "color"},
    )

    contact: str | None = Field(
        default="CYAN_400",
        description='Color of contact force arrows. Set to `""` to disable.',
        json_schema_extra={"x-widget": "color"},
    )

    clearance_line: str | None = Field(
        default="WHITE",
        description='Color of proximity clearance lines. Set to `""` to disable.',
        json_schema_extra={"x-widget": "color"},
    )

    trace_line: str | None = Field(
        default="VIOLET_500",
        description='Default color of `Tracer` trails. Set to `""` to disable. Overridden per-`Tracer` by passing `color`.',
        json_schema_extra={"x-widget": "color"},
    )

    force_length_scale: float = Field(
        default=1.0,
        description="Default length multiplier for action/reaction force arrows, on top of MuJoCo's native scaling. Overridden per-`Load` by `force_length_scale`.",
    )

    force_width_scale: float = Field(
        default=1.0,
        ge=0,
        description="Default width multiplier for action/reaction force arrows, on top of MuJoCo's native scaling. Overridden per-`Load` by `force_width_scale`.",
    )

    torque_length_scale: float = Field(
        default=1.0,
        description="Default length multiplier for torque arrows, on top of MuJoCo's native scaling. Overridden per-`Load` by `torque_length_scale`.",
    )

    torque_width_scale: float = Field(
        default=1.0,
        ge=0,
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


class SensAISettings(BaseModel):
    """Settings for the SensAI assistant embedded in the Dojo dashboard."""

    model_config = ConfigDict(
        extra="forbid",
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
        description="Whether or not to activate AI features.",
    )

    model_name: str = Field(
        default="qwen2.5:0.5b",
        description="Model identifier (e.g. `qwen2.5:0.5b`, `llama3.2:3b`).",
    )

    base_url: str = Field(
        default="http://localhost:11434/v1",
        description="Base URL for the OpenAI-compatible endpoint.",
    )

    api_key: SecretStr = Field(
        default=SecretStr("ollama"),
        description="\n\n".join(
            (
                "API key sent with each request.",
                "For security, only a masked placeholder is ever saved to a settings file - set the real value via the `MUJOCO_MOJO_DOJO__SENSAI__API_KEY` environment variable instead. Ollama ignores the value, but its client library still requires a non-empty string.",
            )
        ),
    )


class DojoSettings(BaseModel):
    """Settings for the Dojo dashboard."""

    model_config = ConfigDict(
        extra="forbid",
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
        description="\n\n".join(
            (
                "A custom sound to play on the Dojo monitor page when a job finishes, instead of the built-in chime. Only takes effect when `chime_enabled` above is enabled.",
                "Set this to either a web URL (e.g. `https://example.com/sound.mp3`) or the path to a local audio file (e.g. `/home/alex/sounds/ding.wav`, or on Windows `C:/Users/alex/ding.mp3` - use forward slashes rather than backslashes.",
                "Easiest to set safely with `mujoco-mojo settings set dojo.chime_source <path-or-url>`, which writes it correctly for you. Leave unset to keep the default chime.",
            )
        ),
    )

    show_quick_filters: bool = Field(
        default=True,
        description="\n\n".join(
            (
                "For the X-axis, Y-axis, and reference frame selectors, this setting will show or hide the quick filter chips.",
                "This can be helpful for a more interactive way to search, but takes up some space in the selection element.",
            )
        ),
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
    """
    Flat key-value pairs used to extend a SLURM submission.

    Keys prefixed with `sbatch.` become extra `#SBATCH` lines in the generated submission script, e.g. `"sbatch.account": "proj123"` becomes `#SBATCH --account=proj123`. Every other key is exported as an environment variable before the worker command runs, e.g. `"MLM_LICENSE_FILE": "27000@license.internal"` becomes `export MLM_LICENSE_FILE="27000@license.internal"`.

    Values must be scalars (string, int, float, or bool). Nested objects or arrays are rejected at load time since this file can only ever describe a flat set of settings - the shape of `MujocoMojoSettings.slurm`, layered automatically between the global and project-local settings files (see `project_settings_file`).
    """

    model_config = ConfigDict(
        title="Slurm",
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


class AssetBundlingSettings(BaseModel):
    """Settings for how MuJoCo Mojo bundles a model's dependency files (meshes, textures, etc.) into a shared assets folder."""

    model_config = ConfigDict(
        extra="forbid",
        title="Assets",
        # stacked boxes: two overlapping rounded squares, offset diagonally.
        json_schema_extra={
            "x-icon": '<rect x="3" y="9" width="12" height="12" rx="1.5"/><rect x="8" y="3" width="12" height="12" rx="1.5"/>',
        },
    )

    symlink: bool = Field(
        default=False,
        description="\n\n".join(
            (
                "Link to the source file instead of copying its bytes.",
                "This saves disk space and is instant regardless of file size, but the bundle is no longer self-contained or immutable: moving/sharing the bundle directory without its original source files breaks it, and editing a source file after bundling silently changes every trial that linked to it.",
                "Only takes effect on POSIX (Linux, macOS); Windows does not reliably allow unprivileged symlink creation, so this setting is ignored there and a normal copy is always made.",
            )
        ),
    )


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


class GenerateJsonSchemaWithDefaults(GenerateJsonSchema):
    """Appends each field's default value to its `description`, so editors that only surface `description` on hover (e.g. VS Code's Even Better TOML) still show it, without hand-duplicating every `Field(default=...)` into its own description text."""

    def generate(
        self, schema: CoreSchema, mode: JsonSchemaMode = "validation"
    ) -> JsonSchemaValue:
        json_schema = super().generate(schema, mode=mode)
        self._append_defaults(json_schema)
        for definition in json_schema.get("$defs", {}).values():
            self._append_defaults(definition)
        return json_schema

    @staticmethod
    def _append_defaults(node: JsonSchemaValue) -> None:
        for prop in node.get("properties", {}).values():
            if "default" in prop and "description" in prop:
                default = prop["default"]
                rendered = (
                    ("true" if default else "false")
                    if isinstance(default, bool)
                    else str(default)
                )
                prop["description"] = f"{prop['description']}\n\nDefault: `{rendered}`."


class MujocoMojoSettings(BaseSettings):
    """
    Global user-level settings persisted to ~/.mujoco-mojo/settings.toml, layered with an optional project-local override file - the same User-settings-vs-Workspace-settings model VS Code uses.

    Instantiate to load. Sources are checked in priority order: constructor kwargs > environment variables > project settings file (`project_settings_file()`, `<cwd>/.mujoco-mojo/settings.toml`) > global settings file (`~/.mujoco-mojo/settings.toml`) > defaults. Every field can be overridden at the project level, not just a specific subset - a project file is expected to hold only the handful of keys that genuinely differ from the global defaults (e.g. per-project SLURM extras or force-scaling), not a full copy. Environment variables use the prefix `MUJOCO_MOJO_` with `__` as the nested delimiter, e.g. `MUJOCO_MOJO_DOJO__SENSAI__MODEL_NAME=llama3.2:3b`.
    """

    model_config = SettingsConfigDict(
        toml_file=GLOBAL_SETTINGS_FILE,
        env_prefix="MUJOCO_MOJO_",
        env_nested_delimiter="__",
    )

    visualization: VisualizationSettings = Field(
        default_factory=VisualizationSettings,
        description="Colors and visibility for simulation visual overlays.",
    )

    assets: AssetBundlingSettings = Field(
        default_factory=AssetBundlingSettings,
        description="Settings for how dependency files get bundled into a shared assets folder.",
    )

    dojo: DojoSettings = Field(
        default_factory=DojoSettings,
        description="Settings for the Dojo dashboard.",
    )

    slurm: SlurmExtraSettings = Field(
        default_factory=lambda: SlurmExtraSettings({}),
        description="\n\n".join(
            (
                "Extra SLURM `#SBATCH` lines / environment variables (e.g. account number, email), applied to every SLURM submission.",
                "Edit the global settings and/or project settings for per-project overrides. The project file's `[slurm]` table wins over the global one on any key collision.",
                "Keys prefixed `sbatch.` become `#SBATCH` lines, everything else is exported as an environment variable.",
            )
        ),
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
            key: Dotted path, e.g. "dojo.sensai.model_name", "assets.symlink", or "slurm.sbatch.account".
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

        Either way, a brand-new file starts with a `#:schema` header pointing at the colocated settings.schema.json - a bare relative filename, resolved by taplo against the TOML file's own directory, rather than a cross-directory reference to another directory's schema. The latter is what broke under SSH/SSHFS-style setups where only one of the two directories was visible to the editor - every settings directory is now self-contained.

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
                    doc = tomlkit.parse(toml_path.read_text(encoding="utf-8"))
                else:
                    doc = tomlkit.parse("#:schema settings.schema.json\n")

                if not project:
                    # mode="json" turns any SecretStr field (e.g. dojo.sensai.api_key)
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
