from pathlib import Path

import pytest
from pydantic import ValidationError

from mujoco_mojo.settings import (
    MujocoMojoSettings,
    ReloadedKeySettings,
    ReloadedSettings,
)


@pytest.fixture(autouse=True)
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty project directory to read settings from, with no global settings file anywhere."""
    monkeypatch.setattr(
        "mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", tmp_path / "home" / "settings.toml"
    )
    work = tmp_path / "project"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


def write_project_settings(project: Path, text: str) -> None:
    path = project / ".mujoco-mojo" / "settings.toml"
    path.parent.mkdir()
    path.write_text(text, encoding="utf-8")


def test_the_default_keys_are_the_ones_the_footer_has_always_shown() -> None:
    assert ReloadedKeySettings().model_dump() == {
        "generate": ["f2"],
        "run": ["f3"],
        "watch": ["f4"],
        "record": ["f7"],
        "explain": ["f8"],
        "help": ["f9", "f1"],
        "stop": ["escape"],
        "quit": ["f10", "ctrl+q"],
    }
    assert ReloadedSettings().keys == ReloadedKeySettings()


def test_key_names_are_lowercase_and_a_repeated_or_empty_one_is_dropped() -> None:
    keys = ReloadedKeySettings(generate=[" F5 ", "f6", "", "F5"])

    assert keys.generate == ["f5", "f6"]


@pytest.mark.parametrize("text", ["f5, f6", "F5,f6,", " f5 , F6 "])
def test_a_list_can_be_written_as_text_the_way_the_dojo_panel_and_the_cli_give_it(
    text: str,
) -> None:
    assert ReloadedKeySettings.model_validate({"generate": text}).generate == [
        "f5",
        "f6",
    ]


def test_an_action_can_have_no_keys() -> None:
    assert ReloadedKeySettings(quit=[]).quit == []
    assert ReloadedKeySettings.model_validate({"quit": ""}).quit == []


def test_a_key_cannot_do_two_things() -> None:
    with pytest.raises(ValidationError, match="`f3` is bound to both `run` and `help`"):
        ReloadedKeySettings(help=["f3"])


def test_an_action_that_does_not_exist_is_an_error_rather_than_ignored() -> None:
    with pytest.raises(ValidationError):
        ReloadedKeySettings.model_validate({"generat": ["f5"]})


def test_a_project_file_changes_one_action_and_leaves_the_rest(project: Path) -> None:
    write_project_settings(project, '[reloaded.keys]\ngenerate = ["f5", "ctrl+g"]\n')

    keys = MujocoMojoSettings().reloaded.keys

    assert keys.generate == ["f5", "ctrl+g"]
    assert keys.run == ["f3"]
    assert keys.quit == ["f10", "ctrl+q"]


def test_settings_set_takes_the_keys_as_text(project: Path) -> None:
    MujocoMojoSettings.set_project_value("reloaded.keys.generate", "F5, ctrl+g")

    assert MujocoMojoSettings().reloaded.keys.generate == ["f5", "ctrl+g"]


def test_the_schema_names_each_action_so_editors_and_the_dojo_can_show_them() -> None:
    schema = ReloadedKeySettings.model_json_schema()

    assert schema["title"] == "Keys"
    assert list(schema["properties"]) == [
        "generate",
        "run",
        "watch",
        "record",
        "explain",
        "help",
        "stop",
        "quit",
    ]
    assert all(prop["type"] == "array" for prop in schema["properties"].values())
