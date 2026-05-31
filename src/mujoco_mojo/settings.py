"""Global user settings for mujoco_mojo, persisted to ~/.mujoco-mojo/settings.toml."""

from __future__ import annotations

import tomli_w
from pydantic import BaseModel, Field, SecretStr, field_serializer, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from mujoco_mojo.meta import MUJOCO_MOJO_DIR
from mujoco_mojo.utils.color import Color

SETTINGS_DIR = MUJOCO_MOJO_DIR
SETTINGS_FILE = SETTINGS_DIR / "settings.toml"

_COLOR_FIELDS = (
    "action_force",
    "reaction_force",
    "torque",
    "contact",
    "clearance_line",
)


class VisualizationSettings(BaseModel):
    """Colors for force, torque, contact, and proximity overlays rendered during simulation."""

    action_force: str | None = "EMERALD_500"
    """Color of action-site force arrows. Set to null (or `""` in TOML) to hide."""

    reaction_force: str | None = "ROSE_500"
    """Color of reaction-site force arrows. Set to null (or `""` in TOML) to hide."""

    torque: str | None = "AMBER_500"
    """Color of torque arrows. Set to null (or `""` in TOML) to hide."""

    contact: str | None = "CYAN_400"
    """Color of contact force arrows. Set to null (or `""` in TOML) to hide."""

    clearance_line: str | None = "WHITE"
    """Color of proximity clearance lines. Set to null (or `""` in TOML) to hide."""

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

    model_name: str = Field(default="qwen2.5:0.5b")
    """Ollama model identifier (e.g. `qwen2.5:0.5b`, `llama3.2:3b`)."""

    base_url: str = Field(default="http://localhost:11434/v1")
    """Base URL for the OpenAI-compatible endpoint. Defaults to local Ollama."""

    api_key: SecretStr = Field(default=SecretStr("ollama"))
    """API key sent with each request. For real keys prefer the `MUJOCO_MOJO_SENSAI__API_KEY` env var over storing here. Ollama ignores the value but the client requires a non-empty string."""

    enabled: bool = Field(default=False)
    """Whether SensAI is active. Opt-in; toggled from the dashboard."""

    @field_serializer("api_key")
    def _serialize_api_key(self, v: SecretStr) -> str:
        return v.get_secret_value()


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

    sensai: SensAISettings = Field(default_factory=SensAISettings)
    """Settings for the SensAI assistant."""

    visualization: VisualizationSettings = Field(default_factory=VisualizationSettings)
    """Colors and visibility for simulation visual overlays."""

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

    def save(self) -> None:
        """Persist current settings to ~/.mujoco-mojo/settings.toml."""
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_bytes(tomli_w.dumps(self.model_dump()).encode())
