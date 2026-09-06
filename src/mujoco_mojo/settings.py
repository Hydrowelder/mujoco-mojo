"""Global user settings for mujoco_mojo, persisted to ~/.mujoco-mojo/settings.toml."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import tomlkit
from pydantic import (
    BaseModel,
    Field,
    RootModel,
    SecretStr,
    field_serializer,
    field_validator,
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
SETTINGS_FILE = SETTINGS_DIR / "settings.toml"
SETTINGS_SCHEMA_FILE = SETTINGS_DIR / "settings.schema.json"
SETTINGS_TAPLO_FILE = SETTINGS_DIR / ".taplo.toml"

SlurmScalar = str | int | float | bool

_SBATCH_PREFIX = "sbatch."

_COLOR_FIELDS = (
    "action_force",
    "reaction_force",
    "torque",
    "contact",
    "clearance_line",
    "trace_line",
)


class VisualizationSettings(BaseModel):
    """Colors for force, torque, contact, and proximity overlays rendered during simulation."""

    action_force: str | None = Field(
        default="EMERALD_500",
        description='Color of action-site force arrows. Set to `""` to hide.',
    )

    reaction_force: str | None = Field(
        default="ROSE_500",
        description='Color of reaction-site force arrows. Set to `""` to hide.',
    )

    torque: str | None = Field(
        default="AMBER_500",
        description='Color of torque arrows. Set to `""` to hide.',
    )

    contact: str | None = Field(
        default="CYAN_400",
        description='Color of contact force arrows. Set to `""` to hide.',
    )

    clearance_line: str | None = Field(
        default="WHITE",
        description='Color of proximity clearance lines. Set to `""` to hide.',
    )

    trace_line: str | None = Field(
        default="VIOLET_500",
        description='Default color of `Tracer` trails. Set to `""` to hide. Overridden per-`Tracer` by passing `color`.',
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

    @field_validator(*_COLOR_FIELDS, mode="before")
    @classmethod
    def _parse_color(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.upper()
        if v not in Color.__members__:
            raise ValueError(
                f"'{v}' is not a valid Color name (e.g. 'ROSE_500', 'EMERALD_500')."
            )
        return v

    @field_serializer(*_COLOR_FIELDS)
    def _serialize_color(self, v: str | None) -> str:
        return v if v is not None else ""


class SensAISettings(BaseModel):
    """Settings for the SensAI assistant embedded in the Dojo dashboard."""

    model_name: str = Field(
        default="qwen2.5:0.5b",
        description="Ollama model identifier (e.g. `qwen2.5:0.5b`, `llama3.2:3b`).",
    )

    base_url: str = Field(
        default="http://localhost:11434/v1",
        description="Base URL for the OpenAI-compatible endpoint. Defaults to local Ollama.",
    )

    api_key: SecretStr = Field(
        default=SecretStr("ollama"),
        description="API key sent with each request. For real keys prefer the `MUJOCO_MOJO_SENSAI__API_KEY` env var over storing here. Ollama ignores the value but the client requires a non-empty string.",
    )

    enabled: bool = Field(
        default=False,
        description="Whether SensAI is active. Opt-in; toggled from the dashboard.",
    )

    @field_serializer("api_key")
    def _serialize_api_key(self, v: SecretStr) -> str:
        return v.get_secret_value()


class SlurmExtraSettings(RootModel[dict[str, SlurmScalar]]):
    """
    Flat key-value pairs used to extend a SLURM submission.

    Keys prefixed with `sbatch.` become extra `#SBATCH` lines in the generated submission script, e.g. `"sbatch.account": "proj123"` becomes `#SBATCH --account=proj123`. Every other key is exported as an environment variable before the worker command runs, e.g. `"MLM_LICENSE_FILE": "27000@license.internal"` becomes `export MLM_LICENSE_FILE="27000@license.internal"`.

    Values must be scalars (string, int, float, or bool). Nested objects or arrays are rejected at load time since this file can only ever describe a flat set of settings - used both as the shape of `MujocoMojoSettings.slurm` and as the optional `--slurm-config` per-job JSON file.
    """

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

    @classmethod
    def load(cls, path: Path) -> SlurmExtraSettings:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    @classmethod
    def merge(cls, *sources: SlurmExtraSettings) -> SlurmExtraSettings:
        """Later sources win on key collisions (e.g. `merge(global, per_job)` lets a per-job file override a user's global defaults)."""
        merged: dict[str, SlurmScalar] = {}
        for source in sources:
            merged.update(source.root)
        return cls(merged)


class AssetBundlingSettings(BaseModel):
    """Settings for how MuJoCo Mojo bundles a model's dependency files (meshes, textures, etc.) into a shared assets folder."""

    symlink: bool = Field(
        default=False,
        description="Link to the source file instead of copying its bytes. This saves disk space and is instant regardless of file size, but the bundle is no longer self-contained or immutable: moving/sharing the bundle directory without its original source files breaks it, and editing a source file after bundling silently changes every trial that linked to it. Only takes effect on POSIX (Linux, macOS); Windows does not reliably allow unprivileged symlink creation, so this setting is ignored there and a normal copy is always made.",
    )


def _merge_into_toml(doc: tomlkit.TOMLDocument | Table, data: dict[str, Any]) -> None:
    """
    Writes `data` into an existing `tomlkit` document or table, key by key, so any comments and formatting attached to a key that already exists survive.

    Args:
        doc: A parsed `tomlkit` document or table to update in place.
        data: Nested settings data, as returned by `MujocoMojoSettings.model_dump()`.

    """
    for key, value in data.items():
        if isinstance(value, dict):
            if key not in doc or not isinstance(doc[key], (Table, dict)):
                doc[key] = tomlkit.table()
            _merge_into_toml(doc[key], value)
        else:
            doc[key] = value


class _GenerateJsonSchemaWithDefaults(GenerateJsonSchema):
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
                prop["description"] = f"{prop['description']} Default: `{rendered}`."


class MujocoMojoSettings(BaseSettings):
    """
    Global user-level settings persisted to ~/.mujoco-mojo/settings.toml.

    Instantiate to load. Sources are checked in priority order: constructor kwargs > environment variables > TOML file > defaults. Environment variables use the prefix `MUJOCO_MOJO_` with `__` as the nested delimiter, e.g. `MUJOCO_MOJO_SENSAI__MODEL_NAME=llama3.2:3b`.
    """

    model_config = SettingsConfigDict(
        toml_file=SETTINGS_FILE,
        env_prefix="MUJOCO_MOJO_",
        env_nested_delimiter="__",
    )

    sensai: SensAISettings = Field(
        default_factory=SensAISettings,
        description="Settings for the SensAI assistant.",
    )

    visualization: VisualizationSettings = Field(
        default_factory=VisualizationSettings,
        description="Colors and visibility for simulation visual overlays.",
    )

    slurm: SlurmExtraSettings = Field(
        default_factory=lambda: SlurmExtraSettings({}),
        description="Global default extra SLURM `#SBATCH` lines / environment variables (e.g. account number, email), applied to every SLURM submission. Edit the `[slurm]` table in `~/.mujoco-mojo/settings.toml` directly - keys prefixed `sbatch.` become `#SBATCH` lines, everything else is exported as an environment variable. A `--slurm-config` file passed at submission time is merged on top and wins on any key collision.",
    )

    assets: AssetBundlingSettings = Field(
        default_factory=AssetBundlingSettings,
        description="Settings for how dependency files get bundled into a shared assets folder.",
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
        return (init_settings, env_settings, TomlConfigSettingsSource(settings_cls))

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

    def save(self) -> None:
        """
        Persist current settings to ~/.mujoco-mojo/settings.toml.

        If the file already exists, its values are updated in place with `tomlkit` rather than regenerated from scratch, preserving any comments or formatting you have added by hand. A key that exists in the file but no longer has a corresponding settings value (e.g. a removed `slurm` entry) is left as-is rather than deleted. A brand-new file starts with a `#:schema` header pointing at settings.schema.json so taplo-based editors (e.g. VS Code's Even Better TOML) pick up hover hints and validation even before `write_schema_files` has been run.
        """
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

        if SETTINGS_FILE.exists():
            doc = tomlkit.parse(SETTINGS_FILE.read_text(encoding="utf-8"))
        else:
            doc = tomlkit.parse(f"#:schema {SETTINGS_SCHEMA_FILE.name}\n")

        _merge_into_toml(doc, self.model_dump())
        SETTINGS_FILE.write_text(tomlkit.dumps(doc), encoding="utf-8")

    @classmethod
    def write_schema_files(cls) -> None:
        """Writes settings.schema.json and a companion .taplo.toml next to the settings file, so taplo-based editors (VS Code's Even Better TOML, Neovim, etc.) get hover hints and validation for ~/.mujoco-mojo/settings.toml. Safe to re-run any time, e.g. after upgrading mujoco-mojo changes the settings shape."""
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        schema = cls.model_json_schema(schema_generator=_GenerateJsonSchemaWithDefaults)
        SETTINGS_SCHEMA_FILE.write_text(json.dumps(schema, indent=2), encoding="utf-8")

        # taplo requires a file:// URI for the schema url - a relative path is not supported
        schema_uri = SETTINGS_SCHEMA_FILE.as_uri()
        SETTINGS_TAPLO_FILE.write_text(
            f'[[rule]]\ninclude = ["settings.toml"]\n\n[rule.schema]\nurl = "{schema_uri}"\n',
            encoding="utf-8",
        )
