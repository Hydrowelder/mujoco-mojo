from pathlib import Path

import pytest
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource

from mujoco_mojo.settings import (
    AssetBundlingSettings,
    MujocoMojoSettings,
    SensAISettings,
    VisualizationSettings,
)


def test_defaults_are_valid_color_names():
    """Default values are valid Color member names."""
    s = VisualizationSettings()
    assert s.action_force == "EMERALD_500"
    assert s.reaction_force == "ROSE_500"
    assert s.torque == "AMBER_500"
    assert s.contact == "CYAN_400"
    assert s.clearance_line == "WHITE"


def test_defaults_arrow_scales_are_one():
    """Default force/torque length and width scales are 1.0 (no adjustment)."""
    s = VisualizationSettings()
    assert s.force_length_scale == 1.0
    assert s.force_width_scale == 1.0
    assert s.torque_length_scale == 1.0
    assert s.torque_width_scale == 1.0


def test_invalid_color_name_raises():
    """An unrecognized color name raises ValidationError."""
    with pytest.raises(ValidationError, match="not a valid Color name"):
        VisualizationSettings(action_force="NOT_A_COLOR")


def test_empty_string_coerces_to_none():
    """Empty string input is treated as None (TOML null equivalent)."""
    s = VisualizationSettings(action_force="")
    assert s.action_force is None


def test_none_accepted_directly():
    """Explicit None disables the color."""
    s = VisualizationSettings(torque=None)
    assert s.torque is None


def test_case_insensitive_acceptance():
    """Lowercase color names are accepted and normalized to uppercase."""
    s = VisualizationSettings(action_force="emerald_500")
    assert s.action_force == "EMERALD_500"


def test_none_serializes_as_empty_string():
    """None round-trips through serialization as `""` for TOML compatibility."""
    s = VisualizationSettings(action_force=None)
    dumped = s.model_dump()
    # field_serializer converts None -> "" for TOML
    assert dumped["action_force"] == ""


def test_color_value_serializes_as_string() -> None:
    """Set color names serialize back as their string name."""
    s = VisualizationSettings(action_force="ROSE_500")
    dumped: dict = s.model_dump()
    assert dumped["action_force"] == "ROSE_500"


def test_sensai_api_key_serializer_strips_secret_wrapper() -> None:
    """SensAISettings serializes api_key as a plain string, not SecretStr."""
    s = SensAISettings(api_key="my-secret-key")  # type: ignore[arg-type]
    dumped: dict = s.model_dump()
    assert dumped["api_key"] == "my-secret-key"
    assert isinstance(dumped["api_key"], str)


def test_settings_save_writes_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MujocoMojoSettings.save() persists a valid TOML file."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_FILE", toml_path)

    settings = MujocoMojoSettings()
    settings.save()

    assert toml_path.exists()
    content: str = toml_path.read_text()
    # the TOML file must contain at least the visualization section key
    assert "visualization" in content


def test_settings_save_writes_schema_header_on_first_save(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A freshly created settings.toml starts with a #:schema header for taplo-based editors."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_FILE", toml_path)

    MujocoMojoSettings().save()

    first_line = toml_path.read_text().splitlines()[0]
    assert first_line == "#:schema settings.schema.json"


def test_settings_save_preserves_hand_written_comments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-saving over an existing settings.toml updates values in place with tomlkit, keeping any comments a user added by hand."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_FILE", toml_path)

    toml_path.write_text(
        "#:schema settings.schema.json\n"
        "[assets]\n"
        "# I turned this on for my cluster, please don't revert it\n"
        "symlink = false\n",
        encoding="utf-8",
    )

    MujocoMojoSettings(assets=AssetBundlingSettings(symlink=True)).save()

    content = toml_path.read_text()
    assert "# I turned this on for my cluster, please don't revert it" in content
    assert "symlink = true" in content


def test_bare_constructor_does_not_reset_nested_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard: MujocoMojoSettings() resolves a missing nested field against the existing TOML file rather than the field's code default, so it must never be used to implement a settings reset - MujocoMojoSettings.defaults() is required instead."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setitem(MujocoMojoSettings.model_config, "toml_file", toml_path)

    toml_path.write_text(
        '[visualization]\naction_force = "CYAN_400"\n', encoding="utf-8"
    )

    # a bare constructor call quietly echoes back the customized file value...
    assert MujocoMojoSettings().visualization.action_force == "CYAN_400"

    # ...while MujocoMojoSettings.defaults() does not
    assert MujocoMojoSettings.defaults().visualization.action_force == "EMERALD_500"


def test_defaults_pattern_covers_any_field_without_hand_listing_them(
    tmp_path: Path,
) -> None:
    """
    The pattern `defaults()` uses - iterating `model_fields` and calling `get_default(call_default_factory=True)` - generically resets any `BaseSettings` subclass's nested fields, so a newly added settings field needs no corresponding update to `defaults()` to be covered.

    Exercised against a throwaway local class rather than `MujocoMojoSettings` itself, so this doesn't touch the real settings class's compiled schema.
    """

    class _Sub(BaseModel):
        volume: int = Field(default=11)

    class _LocalSettings(BaseSettings):
        model_config = SettingsConfigDict(toml_file=tmp_path / "local.toml")
        sub: _Sub = Field(default_factory=_Sub)

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls,
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        ):
            return (init_settings, env_settings, TomlConfigSettingsSource(settings_cls))

    (tmp_path / "local.toml").write_text("[sub]\nvolume = 999\n", encoding="utf-8")

    # a bare constructor echoes the file value, same pitfall as MujocoMojoSettings
    assert _LocalSettings().sub.volume == 999

    # the same generic pattern used by MujocoMojoSettings.defaults() resets it
    field_defaults = {
        name: info.get_default(call_default_factory=True)
        for name, info in _LocalSettings.model_fields.items()
    }
    assert _LocalSettings(**field_defaults).sub.volume == 11


def test_settings_reset_restores_defaults_and_keeps_comments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reset command's approach - MujocoMojoSettings.defaults().save() - restores every value to its default while keeping hand-written comments."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_FILE", toml_path)
    monkeypatch.setitem(MujocoMojoSettings.model_config, "toml_file", toml_path)

    toml_path.write_text(
        "#:schema settings.schema.json\n"
        "[visualization]\n"
        "# my customization, please keep\n"
        'action_force = "EMERALD_600"\n',
        encoding="utf-8",
    )

    MujocoMojoSettings.defaults().save()

    content = toml_path.read_text()
    assert "# my customization, please keep" in content
    assert 'action_force = "EMERALD_500"' in content


def test_write_schema_files_writes_schema_and_taplo_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """write_schema_files() emits a valid JSON schema (with defaults folded into each field's description) and a .taplo.toml rule pointing at it."""
    import json

    schema_path = tmp_path / "settings.schema.json"
    taplo_path = tmp_path / ".taplo.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_SCHEMA_FILE", schema_path)
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_TAPLO_FILE", taplo_path)

    MujocoMojoSettings.write_schema_files()

    assert schema_path.exists()
    schema = json.loads(schema_path.read_text())
    symlink_prop = schema["$defs"]["AssetBundlingSettings"]["properties"]["symlink"]
    assert symlink_prop["description"].endswith("Default: `false`.")

    assert taplo_path.exists()
    taplo_content = taplo_path.read_text()
    assert 'include = ["settings.toml"]' in taplo_content
    assert schema_path.as_uri() in taplo_content
