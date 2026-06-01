from pathlib import Path

import pytest
from pydantic import ValidationError

from mujoco_mojo.settings import (
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
