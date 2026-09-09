import json
from pathlib import Path

import pytest
from pydantic import BaseModel, Field, HttpUrl, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource

from mujoco_mojo.settings import (
    DojoSettings,
    GeneralSettings,
    MujocoMojoSettings,
    SensAISettings,
    VisualizationSettings,
)
from mujoco_mojo.utils.layers.dojo.routers.settings import (
    _dojo_settings_schema,
    _settings_payload,
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


def test_dojo_password_never_reveals_plaintext_on_dump() -> None:
    """dojo.password masks the same way api_key does on a mode='json' dump, while staying None by default (unlike api_key, which always has a placeholder value) so 'no password set' round-trips correctly."""
    assert DojoSettings().password is None

    d = DojoSettings(password="hunter2")  # type: ignore[arg-type]

    dumped = d.model_dump()
    assert isinstance(dumped["password"], SecretStr)

    dumped_json = d.model_dump(mode="json")
    assert dumped_json["password"] == "**********"

    assert d.password is not None
    assert d.password.get_secret_value() == "hunter2"


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
    monkeypatch.setattr("mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", toml_path)
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
    monkeypatch.setattr("mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", toml_path)
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


def test_settings_save_never_writes_a_real_dojo_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save() never persists dojo.password's real value - only the masked placeholder ever reaches disk, same guarantee as dojo.sensai.api_key."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", toml_path)
    _isolate_project_settings(monkeypatch, tmp_path)

    settings = MujocoMojoSettings(
        dojo=DojoSettings(password="hunter2")  # type: ignore[arg-type]
    )
    settings.save()

    content = toml_path.read_text()
    assert "hunter2" not in content
    assert 'password = "**********"' in content

    assert settings.dojo.password is not None
    assert settings.dojo.password.get_secret_value() == "hunter2"


def test_dojo_web_response_never_mentions_secret_fields_at_all() -> None:
    """
    The schema and values payload the Dojo web settings panel actually receives (`_dojo_settings_schema`/`_settings_payload`, as served by `GET/POST /settings`) must not contain the literal field names `password`/`api_key` anywhere - not just mask their values - since the frontend has no legitimate need to know these fields exist. Regression test for two bugs found while building this: a nested-model field's schema entry re-embeds a whole-object copy of its default one level up (leaking a secret field's name back in after removing it from `properties`), and a value-based `isinstance(value, SecretStr)` check misses `password`, whose default is `None`, not a `SecretStr` instance.
    """
    settings = MujocoMojoSettings(
        dojo=DojoSettings(
            password="SUPER_SECRET_VALUE",  # type: ignore[arg-type]
            sensai=SensAISettings(api_key="ANOTHER_SECRET_VALUE"),  # type: ignore[arg-type]
        )
    )
    combined = json.dumps(
        {"schema": _dojo_settings_schema(), **_settings_payload(settings)}
    )

    for needle in ("password", "api_key", "SUPER_SECRET_VALUE", "ANOTHER_SECRET_VALUE"):
        assert needle not in combined


def test_settings_save_writes_schema_header_on_first_save(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A freshly created settings.toml starts with a #:schema header for taplo-based editors."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", toml_path)
    _isolate_project_settings(monkeypatch, tmp_path)

    MujocoMojoSettings().save()

    first_line = toml_path.read_text().splitlines()[0]
    assert first_line == "#:schema settings.schema.json"


def test_settings_save_colocates_schema_and_taplo_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save() writes settings.schema.json and .taplo.toml alongside settings.toml in the same call, so a settings directory is always self-contained without a separate write_schema_files() step."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", toml_path)
    _isolate_project_settings(monkeypatch, tmp_path)

    MujocoMojoSettings().save()

    schema_path = tmp_path / "settings.schema.json"
    assert schema_path.exists()
    assert (tmp_path / ".taplo.toml").exists()
    assert schema_path.as_uri() in (tmp_path / ".taplo.toml").read_text()


def test_settings_save_writes_to_explicit_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save(directory) writes settings.toml, settings.schema.json, and .taplo.toml into the given directory instead of the global default - the same method serves both the global and project-local settings directories."""
    monkeypatch.setattr(
        "mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", tmp_path / "no-such-global.toml"
    )
    _isolate_project_settings(monkeypatch, tmp_path)
    other_dir = tmp_path / "somewhere-else"

    MujocoMojoSettings().save(other_dir)

    assert (other_dir / "settings.toml").exists()
    assert (other_dir / "settings.schema.json").exists()
    assert (other_dir / ".taplo.toml").exists()


def test_settings_save_preserves_hand_written_comments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-saving over an existing settings.toml updates values in place with tomlkit, keeping any comments a user added by hand."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.SETTINGS_DIR", tmp_path)
    monkeypatch.setattr("mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", toml_path)
    _isolate_project_settings(monkeypatch, tmp_path)

    toml_path.write_text(
        "#:schema settings.schema.json\n"
        "[general]\n"
        "# I turned this on for my cluster, please don't revert it\n"
        "symlink = false\n",
        encoding="utf-8",
    )

    MujocoMojoSettings(general=GeneralSettings(symlink=True)).save()

    content = toml_path.read_text()
    assert "# I turned this on for my cluster, please don't revert it" in content
    assert "symlink = true" in content


def test_bare_constructor_does_not_reset_nested_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard: MujocoMojoSettings() resolves a missing nested field against the existing TOML file rather than the field's code default, so it must never be used to implement a settings reset - MujocoMojoSettings.defaults() is required instead."""
    toml_path = tmp_path / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", toml_path)
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
    monkeypatch.setattr("mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", toml_path)

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


def test_write_schema_files_writes_schema_and_taplo_config(tmp_path: Path) -> None:
    """write_schema_files(directory) emits a valid JSON schema (with defaults folded into each field's description) and a .taplo.toml rule pointing at it, both colocated in the given directory."""
    import json

    MujocoMojoSettings.write_schema_files(tmp_path)

    schema_path = tmp_path / "settings.schema.json"
    taplo_path = tmp_path / ".taplo.toml"
    assert schema_path.exists()
    schema = json.loads(schema_path.read_text())
    symlink_prop = schema["$defs"]["GeneralSettings"]["properties"]["symlink"]
    assert symlink_prop["description"].endswith("Default: `false`")

    assert taplo_path.exists()
    taplo_content = taplo_path.read_text()
    assert 'include = ["settings.toml"]' in taplo_content
    assert schema_path.as_uri() in taplo_content


def test_enum_field_schema_has_no_ref_and_carries_its_own_default(
    tmp_path: Path,
) -> None:
    """A `StrEnum`-typed field (e.g. dojo.profile_sort_mode) must not be left as a bare `$ref` (or allOf-wrapped `$ref`) with `default`/`description` as sibling keys - not every schema consumer honors sibling keywords next to a `$ref` (taplo notably doesn't, showing only the enum type's own generic description instead). The enum definition's `enum`/`type`/`x-enum-descriptions` must be inlined directly onto the property instead, so every consumer sees the field's own appended "Default: ..." line and value descriptions with no ref resolution needed at all - the same self-contained shape a plain (non-shared) Literal-typed field already gets for free."""
    import json

    MujocoMojoSettings.write_schema_files(tmp_path)
    schema = json.loads((tmp_path / "settings.schema.json").read_text())

    prop = schema["$defs"]["DojoSettings"]["properties"]["profile_sort_mode"]
    assert "$ref" not in prop
    assert "allOf" not in prop
    assert prop["default"] == "modified"
    assert prop["description"].endswith("Default: `modified`")
    assert set(prop["enum"]) == {"name", "modified"}
    assert "x-enum-descriptions" in prop

    # the shared $defs entry itself is untouched - other tooling that reads
    # $defs directly (or a future property that does need the shared ref)
    # still finds the full, un-mutated enum definition there
    assert schema["$defs"]["SortMode"]["enum"] == ["name", "modified"]


def test_dict_shaped_settings_section_keeps_its_ref(tmp_path: Path) -> None:
    """Regression guard: a dict-shaped RootModel section (slurm) also lacks a "properties" key, same as an enum leaf - checking for "not an object with properties" alone isn't enough to identify an inlinable enum, since that also matches slurm and would strip its $ref, losing the section's own title/x-icon/additionalProperties in the Dojo settings panel. Only a target that actually has an "enum" key gets inlined."""
    import json

    MujocoMojoSettings.write_schema_files(tmp_path)
    schema = json.loads((tmp_path / "settings.schema.json").read_text())

    slurm_prop = schema["properties"]["slurm"]
    assert slurm_prop["$ref"] == "#/$defs/SlurmExtraSettings"

    slurm_def = schema["$defs"]["SlurmExtraSettings"]
    assert "x-icon" in slurm_def
    assert "title" in slurm_def


# The Dojo settings panel shows a field/section's own `description` in a
# hint bar that grows to fit its content, with no max-height or scrolling -
# scrolling turned out to be useless there anyway, since reaching a
# scrollbar means moving the mouse off whatever row is being hovered, which
# immediately hides the hint before the scroll would matter (settings-panel.ts,
# showSettingsHint/hideSettingsHint). A too-long description doesn't error
# or get clipped, it just quietly makes that hint bar (and the panel around
# it) awkwardly tall - the SlurmExtraSettings field description originally
# shipped at ~500 characters across three paragraphs before being trimmed
# for exactly this reason. This threshold is a soft guard against the same
# mistake happening again on some other field, not a hard technical limit -
# 200 characters is roughly 2-3 lines at the hint bar's actual rendered
# width (see settings_field_row / the hint bar markup, _settings_panel.html).
_MAX_DESCRIPTION_LENGTH = 200


def _collect_schema_descriptions(schema: dict) -> dict[str, str]:
    """Maps a dotted path (e.g. "MujocoMojoSettings.slurm" or "$defs.SlurmExtraSettings") to its `description`, for every property across the top-level schema and every named definition - the two places settings-panel.ts (buildGroup/buildField) ever reads a description from. The schema's own root-level description (MujocoMojoSettings' class docstring) is deliberately excluded - parseSettingsSchema only ever reads `schema.properties`, never `schema.description` itself, so nothing in the settings panel can ever show it."""
    descriptions: dict[str, str] = {}

    def walk(node: dict, prefix: str, *, include_self: bool = True) -> None:
        if include_self:
            description = node.get("description")
            if description:
                descriptions[prefix] = description
        for name, prop in node.get("properties", {}).items():
            walk(prop, f"{prefix}.{name}")

    walk(schema, "MujocoMojoSettings", include_self=False)
    for def_name, definition in schema.get("$defs", {}).items():
        walk(definition, f"$defs.{def_name}")

    return descriptions


def test_no_description_is_too_long_for_the_settings_panel_hint_bar() -> None:
    """Regression guard for the SlurmExtraSettings incident: every field/section description across the whole settings schema stays under a length that comfortably fits the Dojo settings panel's fixed-to-content hint bar, so a future overly-long Field(description=...) or class docstring gets caught here instead of silently making that hint bar (and the panel around it) awkwardly tall the next time someone hovers it."""
    from mujoco_mojo.settings import GenerateJsonSchemaWithDefaults

    schema = MujocoMojoSettings.model_json_schema(
        schema_generator=GenerateJsonSchemaWithDefaults
    )
    descriptions = _collect_schema_descriptions(schema)

    # the generator appends "\n\nDefault: `...`" to a leaf field's own
    # description (see GenerateJsonSchemaWithDefaults._append_defaults) -
    # strip that back off before measuring, since it isn't part of the
    # docstring/Field(description=...) text a settings.py author actually
    # controls the length of.
    offenders = {
        path: len(text.split("\n\nDefault:")[0])
        for path, text in descriptions.items()
        if len(text.split("\n\nDefault:")[0]) > _MAX_DESCRIPTION_LENGTH
    }
    assert not offenders, (
        f"These descriptions exceed {_MAX_DESCRIPTION_LENGTH} characters and should be "
        f"trimmed so the settings panel's hint bar doesn't grow awkwardly tall: {offenders}"
    )


def test_project_and_global_settings_both_contribute_distinct_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project file setting one field and a global file setting an unrelated field both come through in the fully resolved settings - the deep-merge across sources doesn't drop either one."""
    global_path = tmp_path / "global.toml"
    project_path = tmp_path / "project.toml"
    monkeypatch.setattr("mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", global_path)
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file", lambda: project_path
    )

    global_path.write_text(
        '[visualization]\naction_force = "CYAN_400"\n', encoding="utf-8"
    )
    project_path.write_text("[general]\nsymlink = true\n", encoding="utf-8")

    settings = MujocoMojoSettings()
    assert settings.visualization.action_force == "CYAN_400"
    assert settings.general.symlink is True


def test_project_settings_win_over_global_on_the_same_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When both layers set the same key, the project-local value wins - workspace beats user, same as VS Code."""
    global_path = tmp_path / "global.toml"
    project_path = tmp_path / "project.toml"
    monkeypatch.setattr("mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", global_path)
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


def test_save_project_mode_writes_only_schema_header(tmp_path: Path) -> None:
    """save(directory, project=True) writes just the #:schema header, no keys - unlike the global file, a project file should start as a blank slate. Re-running it leaves an existing file's contents untouched."""
    project_dir = tmp_path / "project"
    project_path = project_dir / "settings.toml"

    returned = MujocoMojoSettings.model_construct().save(project_dir, project=True)

    assert returned == project_path
    content = project_path.read_text()
    assert len(content.splitlines()) == 1
    assert content.startswith("#:schema ")
    assert "=" not in content

    project_path.write_text(content + "\n[general]\nsymlink = true\n", encoding="utf-8")
    MujocoMojoSettings.model_construct().save(project_dir, project=True)
    assert "symlink = true" in project_path.read_text()


def test_save_project_mode_colocates_its_own_schema(tmp_path: Path) -> None:
    """save(directory, project=True) writes its own settings.schema.json/.taplo.toml directly in that directory and points the #:schema header at that relative filename, rather than an absolute reference into the global ~/.mujoco-mojo directory - a cross-directory reference is what broke under SSH/SSHFS setups where only the project directory is visible to the editor."""
    project_dir = tmp_path / "project"
    project_path = project_dir / "settings.toml"

    MujocoMojoSettings.model_construct().save(project_dir, project=True)

    assert project_path.read_text().splitlines()[0] == "#:schema settings.schema.json"

    schema_path = project_dir / "settings.schema.json"
    taplo_path = project_dir / ".taplo.toml"
    assert schema_path.exists()
    assert taplo_path.exists()
    # the taplo rule's schema url must point at the colocated schema file,
    # not the global ~/.mujoco-mojo/settings.schema.json
    assert schema_path.as_uri() in taplo_path.read_text()


def test_save_project_mode_never_writes_field_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save(directory, project=True) ignores the instance's own field values entirely, even non-default ones - unlike the global file, a project file is meant to hold only a small, deliberate diff (see set_project_value), not a full mirror of every setting."""
    project_dir = tmp_path / "project"
    monkeypatch.setattr(
        "mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", tmp_path / "no-such-global.toml"
    )
    _isolate_project_settings(monkeypatch, tmp_path)

    MujocoMojoSettings(general=GeneralSettings(symlink=True)).save(
        project_dir, project=True
    )

    content = (project_dir / "settings.toml").read_text()
    assert "symlink" not in content
    assert "[general]" not in content


def test_save_project_mode_tolerates_an_invalid_existing_file(tmp_path: Path) -> None:
    """save(directory, project=True) must work even when the project file already there is currently invalid (e.g. a stray top-level key from a hand-edit-in-progress) - re-running `settings init --project` is meant to be a safe, idempotent no-op, and must not require constructing a validated MujocoMojoSettings from the very file it's about to leave untouched. Regression test: an earlier version called MujocoMojoSettings.defaults(), which fully validates every settings source (including this file) before save() ever runs, defeating the whole point of the untouched-when-it-exists guarantee."""
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)
    project_path = project_dir / "settings.toml"
    project_path.write_text(
        "#:schema settings.schema.json\ncustom = true\n", encoding="utf-8"
    )

    MujocoMojoSettings.model_construct().save(project_dir, project=True)

    assert project_path.read_text() == "#:schema settings.schema.json\ncustom = true\n"


def test_save_project_mode_drops_gitignore(tmp_path: Path) -> None:
    """save(directory, project=True) drops a `.gitignore` (`*`) next to the project settings file, so machine-specific overrides aren't committed by accident - but never touches one already there."""
    project_dir = tmp_path / "project"

    MujocoMojoSettings.model_construct().save(project_dir, project=True)
    assert (project_dir / ".gitignore").read_text() == "*\n"

    (project_dir / ".gitignore").write_text("custom\n", encoding="utf-8")
    MujocoMojoSettings.model_construct().save(project_dir, project=True)
    assert (project_dir / ".gitignore").read_text() == "custom\n"


def test_set_project_value_creates_file_and_auto_vivifies_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """set_project_value() creates the project file (and any intermediate tables) on demand, writing only the one changed key."""
    project_path = tmp_path / "settings.toml"
    monkeypatch.setattr(
        "mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", tmp_path / "no-such-global.toml"
    )
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file", lambda: project_path
    )

    MujocoMojoSettings.set_project_value("general.symlink", True)

    content = project_path.read_text()
    assert "[general]" in content
    assert "symlink = true" in content
    assert MujocoMojoSettings().general.symlink is True


def test_set_project_value_preserves_siblings_and_comments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """set_project_value() only touches the one key being set, leaving sibling keys and hand-written comments in the project file alone."""
    project_path = tmp_path / "project.toml"
    monkeypatch.setattr(
        "mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", tmp_path / "no-such-global.toml"
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
    project_path = tmp_path / "settings.toml"
    monkeypatch.setattr(
        "mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", tmp_path / "no-such-global.toml"
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
        "mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", tmp_path / "no-such-global.toml"
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
        "mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", tmp_path / "no-such-global.toml"
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
    assert DojoSettings().chime_source is None


def test_chime_url_string_round_trips_as_http_url() -> None:
    """A web URL is resolved as HttpUrl rather than being mangled into a Path by pydantic's default union matching."""
    settings = DojoSettings(chime_source="https://example.com/sound.mp3")  # type: ignore[arg-type]
    assert isinstance(settings.chime_source, HttpUrl)
    assert str(settings.chime_source) == "https://example.com/sound.mp3"


def test_chime_path_string_round_trips_as_path() -> None:
    """A plain local path string is resolved as Path, not misread as a URL."""
    settings = DojoSettings(chime_source="./my-sound.mp3")  # type: ignore[arg-type]
    assert isinstance(settings.chime_source, Path)
    assert settings.chime_source == Path("./my-sound.mp3")


def test_chime_serializes_as_plain_string_in_json_mode() -> None:
    """model_dump(mode="json") turns both the HttpUrl and Path branches into plain strings, so either can be written to TOML."""
    url_settings = DojoSettings(chime_source="https://example.com/sound.mp3")  # type: ignore[arg-type]
    assert (
        url_settings.model_dump(mode="json")["chime_source"]
        == "https://example.com/sound.mp3"
    )

    path_settings = DojoSettings(chime_source="./my-sound.mp3")  # type: ignore[arg-type]
    assert path_settings.model_dump(mode="json")["chime_source"] == "my-sound.mp3"
