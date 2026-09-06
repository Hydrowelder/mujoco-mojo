from pathlib import Path

import pytest
from pydantic import BaseModel, Field, HttpUrl, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource

from mujoco_mojo.settings import (
    AssetBundlingSettings,
    DojoSettings,
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


def test_sensai_api_key_never_reveals_plaintext_on_dump() -> None:
    """api_key has no custom field_serializer (there used to be one that explicitly unwrapped it - that was the actual leak), so both dump modes stay masked, while .get_secret_value() on the live instance still returns the real value for actual API calls."""
    s = SensAISettings(api_key="my-secret-key")  # type: ignore[arg-type]

    # plain model_dump() keeps the SecretStr wrapper, never the raw string
    dumped = s.model_dump()
    assert isinstance(dumped["api_key"], SecretStr)

    # mode="json" (used by save()/set_project_value() before writing to disk)
    # masks it to a fixed placeholder, never the real value
    dumped_json = s.model_dump(mode="json")
    assert dumped_json["api_key"] == "**********"

    # the real value is still reachable where it's actually needed: the live field
    assert s.api_key.get_secret_value() == "my-secret-key"


def _isolate_project_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Points project_settings_file() at a guaranteed-nonexistent path, so a test controlling only the global file isn't accidentally affected by a real project settings file in whatever directory the test happens to run from."""
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file",
        lambda: tmp_path / "no-such-project" / "settings.toml",
    )


def test_settings_save_writes_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MujocoMojoSettings.save() persists a valid TOML file."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_FILE", toml_path)
    _isolate_project_settings(monkeypatch, tmp_path)

    settings = MujocoMojoSettings()
    settings.save()

    assert toml_path.exists()
    content: str = toml_path.read_text()
    # the TOML file must contain at least the visualization section key
    assert "visualization" in content


def test_settings_save_never_writes_a_real_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save() never persists api_key's real value, whether it's the harmless default or something set to look like a real key - only the masked placeholder ever reaches disk."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_FILE", toml_path)
    _isolate_project_settings(monkeypatch, tmp_path)

    settings = MujocoMojoSettings(
        dojo=DojoSettings(
            sensai=SensAISettings(api_key="sk-not-a-real-key-but-pretend")  # type: ignore[arg-type]
        )
    )
    settings.save()

    content = toml_path.read_text()
    assert "sk-not-a-real-key-but-pretend" not in content
    assert 'api_key = "**********"' in content

    # confirm the live object still has the real value, for actual API calls
    assert (
        settings.dojo.sensai.api_key.get_secret_value()
        == "sk-not-a-real-key-but-pretend"
    )


def test_settings_save_writes_schema_header_on_first_save(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A freshly created settings.toml starts with a #:schema header for taplo-based editors."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_FILE", toml_path)
    _isolate_project_settings(monkeypatch, tmp_path)

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
    _isolate_project_settings(monkeypatch, tmp_path)

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
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_FILE", toml_path)
    _isolate_project_settings(monkeypatch, tmp_path)

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


def test_project_and_global_settings_both_contribute_distinct_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project file setting one field and a global file setting an unrelated field both come through in the fully resolved settings - the deep-merge across sources doesn't drop either one."""
    global_path = tmp_path / "global.toml"
    project_path = tmp_path / "project.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_FILE", global_path)
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file", lambda: project_path
    )

    global_path.write_text(
        '[visualization]\naction_force = "CYAN_400"\n', encoding="utf-8"
    )
    project_path.write_text("[assets]\nsymlink = true\n", encoding="utf-8")

    settings = MujocoMojoSettings()
    assert settings.visualization.action_force == "CYAN_400"
    assert settings.assets.symlink is True


def test_project_settings_win_over_global_on_the_same_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When both layers set the same key, the project-local value wins - workspace beats user, same as VS Code."""
    global_path = tmp_path / "global.toml"
    project_path = tmp_path / "project.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_FILE", global_path)
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file", lambda: project_path
    )

    global_path.write_text(
        '[visualization]\naction_force = "CYAN_400"\n', encoding="utf-8"
    )
    project_path.write_text(
        '[visualization]\naction_force = "AMBER_500"\n', encoding="utf-8"
    )

    assert MujocoMojoSettings().visualization.action_force == "AMBER_500"


def test_init_project_file_writes_only_schema_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """init_project_file() writes just the #:schema header, no keys - unlike the global file, a project file should start as a blank slate. Re-running it is a no-op once the file exists."""
    project_path = tmp_path / "project.toml"
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file", lambda: project_path
    )

    returned = MujocoMojoSettings.init_project_file()

    assert returned == project_path
    content = project_path.read_text()
    assert len(content.splitlines()) == 1
    assert content.startswith("#:schema ")
    assert "=" not in content

    project_path.write_text(content + "\n[assets]\nsymlink = true\n", encoding="utf-8")
    MujocoMojoSettings.init_project_file()
    assert "symlink = true" in project_path.read_text()


def test_set_project_value_creates_file_and_auto_vivifies_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """set_project_value() creates the project file (and any intermediate tables) on demand, writing only the one changed key."""
    project_path = tmp_path / "project.toml"
    monkeypatch.setattr(
        "mujoco_mojo.settings.SETTINGS_FILE", tmp_path / "no-such-global.toml"
    )
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file", lambda: project_path
    )

    MujocoMojoSettings.set_project_value("assets.symlink", True)

    content = project_path.read_text()
    assert "[assets]" in content
    assert "symlink = true" in content
    assert MujocoMojoSettings().assets.symlink is True


def test_set_project_value_preserves_siblings_and_comments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """set_project_value() only touches the one key being set, leaving sibling keys and hand-written comments in the project file alone."""
    project_path = tmp_path / "project.toml"
    monkeypatch.setattr(
        "mujoco_mojo.settings.SETTINGS_FILE", tmp_path / "no-such-global.toml"
    )
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file", lambda: project_path
    )

    project_path.write_text(
        "#:schema settings.schema.json\n"
        "[dojo.sensai]\n"
        "# pinned for this project's demo\n"
        'model_name = "llama3.2:3b"\n',
        encoding="utf-8",
    )

    MujocoMojoSettings.set_project_value("dojo.sensai.enabled", True)

    content = project_path.read_text()
    assert "# pinned for this project's demo" in content
    assert 'model_name = "llama3.2:3b"' in content
    assert "enabled = true" in content


def test_set_project_value_treats_slurm_key_as_one_literal_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The slurm group is a free-form dict whose own keys legitimately contain dots (e.g. "sbatch.account"), so "slurm.sbatch.account" must set that one flat key rather than being split into three nested table levels."""
    project_path = tmp_path / "project.toml"
    monkeypatch.setattr(
        "mujoco_mojo.settings.SETTINGS_FILE", tmp_path / "no-such-global.toml"
    )
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file", lambda: project_path
    )

    MujocoMojoSettings.set_project_value("slurm.sbatch.account", "proj123")
    MujocoMojoSettings.set_project_value("slurm.sbatch.qos", "high")

    content = project_path.read_text()
    assert '"sbatch.account" = "proj123"' in content
    assert '"sbatch.qos" = "high"' in content

    settings = MujocoMojoSettings()
    assert settings.slurm.root == {"sbatch.account": "proj123", "sbatch.qos": "high"}
    assert settings.slurm.sbatch_lines() == [
        "#SBATCH --account=proj123",
        "#SBATCH --qos=high",
    ]


def test_set_project_value_rejects_bad_value_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An invalid value (wrong type, bad color name) raises ValidationError and never touches the project file."""
    project_path = tmp_path / "project.toml"
    monkeypatch.setattr(
        "mujoco_mojo.settings.SETTINGS_FILE", tmp_path / "no-such-global.toml"
    )
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file", lambda: project_path
    )

    with pytest.raises(ValidationError):
        MujocoMojoSettings.set_project_value(
            "visualization.action_force", "NOT_A_COLOR"
        )

    assert not project_path.exists()


def test_set_project_value_rejects_unknown_path_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unrecognized top-level table raises KeyError, and an unrecognized leaf within a real table raises ValidationError (nested settings groups forbid extra keys precisely so this can't silently vanish) - neither writes anything."""
    project_path = tmp_path / "project.toml"
    monkeypatch.setattr(
        "mujoco_mojo.settings.SETTINGS_FILE", tmp_path / "no-such-global.toml"
    )
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file", lambda: project_path
    )

    with pytest.raises(KeyError):
        MujocoMojoSettings.set_project_value("no_such_table.foo", 1)
    assert not project_path.exists()

    with pytest.raises(ValidationError):
        MujocoMojoSettings.set_project_value("dojo.sensai.bogus_key", 1)
    assert not project_path.exists()


def test_chime_defaults_to_none() -> None:
    """dojo.chime is unset by default, so the Dojo monitor falls back to the built-in chime."""
    assert DojoSettings().chime is None


def test_chime_url_string_round_trips_as_http_url() -> None:
    """A web URL is resolved as HttpUrl rather than being mangled into a Path by pydantic's default union matching."""
    settings = DojoSettings(chime="https://example.com/sound.mp3")  # type: ignore[arg-type]
    assert isinstance(settings.chime, HttpUrl)
    assert str(settings.chime) == "https://example.com/sound.mp3"


def test_chime_path_string_round_trips_as_path() -> None:
    """A plain local path string is resolved as Path, not misread as a URL."""
    settings = DojoSettings(chime="./my-sound.mp3")  # type: ignore[arg-type]
    assert isinstance(settings.chime, Path)
    assert settings.chime == Path("./my-sound.mp3")


def test_chime_serializes_as_plain_string_in_json_mode() -> None:
    """model_dump(mode="json") turns both the HttpUrl and Path branches into plain strings, so either can be written to TOML."""
    url_settings = DojoSettings(chime="https://example.com/sound.mp3")  # type: ignore[arg-type]
    assert (
        url_settings.model_dump(mode="json")["chime"] == "https://example.com/sound.mp3"
    )

    path_settings = DojoSettings(chime="./my-sound.mp3")  # type: ignore[arg-type]
    assert path_settings.model_dump(mode="json")["chime"] == "my-sound.mp3"
