import io
import re
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

import mujoco_mojo.utils.layers.cli as cli_module
from mujoco_mojo.settings import (
    MujocoMojoSettings,
    find_project_settings_file,
    project_settings_file,
)
from mujoco_mojo.utils.layers.cli import cli_app


def _project_file(directory: Path, text: str = "") -> Path:
    """Creates `directory/.mujoco-mojo/settings.toml`."""
    path = directory / ".mujoco-mojo" / "settings.toml"
    path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture(autouse=True)
def _no_global_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Points the global settings file at a directory outside every test project, which has no file."""
    global_file = tmp_path / "home" / ".mujoco-mojo" / "settings.toml"
    monkeypatch.setattr("mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", global_file)
    return global_file


# --- the search ---


def test_finds_the_file_in_the_starting_directory(tmp_path: Path) -> None:
    project = tmp_path / "project"
    expected = _project_file(project)

    assert find_project_settings_file(project) == expected


def test_finds_the_file_in_a_parent_directory(tmp_path: Path) -> None:
    """The scenario from the bug: a script `cd`s into a subdirectory of the project."""
    project = tmp_path / "project"
    expected = _project_file(project)
    scripts = project / "scripts" / "nested"
    scripts.mkdir(parents=True)

    assert find_project_settings_file(scripts) == expected


def test_the_nearest_file_wins_and_files_are_not_merged(tmp_path: Path) -> None:
    outer = _project_file(tmp_path / "project", "[general]\nsymlink = true\n")
    inner = _project_file(tmp_path / "project" / "sub", "")
    start = tmp_path / "project" / "sub" / "deeper"
    start.mkdir()

    assert find_project_settings_file(start) == inner
    assert find_project_settings_file(start) != outer


def test_returns_none_when_no_directory_above_has_one(tmp_path: Path) -> None:
    start = tmp_path / "empty" / "deeper"
    start.mkdir(parents=True)

    found = find_project_settings_file(start)

    # something outside the test directory could legitimately exist on a developer machine
    assert found is None or tmp_path not in found.parents


def test_the_global_settings_directory_is_never_a_project(
    tmp_path: Path, _no_global_settings: Path
) -> None:
    """Without this, every project under the home directory would find `~/.mujoco-mojo` as its own."""
    _no_global_settings.parent.mkdir(parents=True)
    _no_global_settings.write_text("", encoding="utf-8")
    project = _no_global_settings.parent.parent / "project"
    project.mkdir()

    found = find_project_settings_file(project)

    assert found is None or found != _no_global_settings


def test_a_project_file_below_the_home_directory_is_still_found(
    tmp_path: Path, _no_global_settings: Path
) -> None:
    _no_global_settings.parent.mkdir(parents=True)
    _no_global_settings.write_text("", encoding="utf-8")
    project = _no_global_settings.parent.parent / "project"
    expected = _project_file(project)
    (project / "sub").mkdir()

    assert find_project_settings_file(project / "sub") == expected


def test_the_global_directory_is_recognized_through_a_symlink(
    tmp_path: Path, _no_global_settings: Path
) -> None:
    _no_global_settings.parent.mkdir(parents=True)
    _no_global_settings.write_text("", encoding="utf-8")
    home = _no_global_settings.parent.parent
    alias = tmp_path / "alias-of-home"
    alias.symlink_to(home, target_is_directory=True)
    (home / "project").mkdir()

    found = find_project_settings_file(alias / "project")

    assert found is None or found.resolve() != _no_global_settings.resolve()


def test_a_directory_that_cannot_be_read_counts_as_having_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outer = _project_file(tmp_path / "project")
    unreadable = _project_file(tmp_path / "project" / "locked")
    start = tmp_path / "project" / "locked" / "deeper"
    start.mkdir()
    original = Path.is_file

    def is_file(self: Path) -> bool:
        if self == unreadable:
            raise PermissionError(13, "denied")
        return original(self)

    monkeypatch.setattr(Path, "is_file", is_file)

    assert find_project_settings_file(start) == outer


# --- project_settings_file() ---


def test_project_settings_file_is_the_discovered_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    expected = _project_file(project)
    (project / "scripts").mkdir()
    monkeypatch.chdir(project / "scripts")

    assert project_settings_file() == expected


def test_project_settings_file_defaults_to_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no file anywhere, this is where `settings set --project` creates one."""
    monkeypatch.setattr("mujoco_mojo.settings.find_project_settings_file", lambda: None)
    monkeypatch.chdir(tmp_path)

    assert project_settings_file() == tmp_path / ".mujoco-mojo" / "settings.toml"


# --- settings values ---


def test_slurm_extras_are_found_from_a_subdirectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reported bug end to end: settings next to the project, process started in a subfolder."""
    project = tmp_path / "project"
    _project_file(project, '[slurm]\n"sbatch.account" = "PROJECT"\n')
    (project / "scripts").mkdir()
    monkeypatch.chdir(project / "scripts")

    assert MujocoMojoSettings().slurm.sbatch_lines() == ["#SBATCH --account=PROJECT"]


def test_set_project_value_writes_to_the_discovered_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    existing = _project_file(project, '[slurm]\n"sbatch.qos" = "high"\n')
    scripts = project / "scripts"
    scripts.mkdir()
    monkeypatch.chdir(scripts)

    written = MujocoMojoSettings.set_project_value("slurm.sbatch.account", "proj123")

    assert written == existing
    assert '"sbatch.account" = "proj123"' in existing.read_text()
    assert '"sbatch.qos" = "high"' in existing.read_text()
    # no second file was started in the subdirectory
    assert not (scripts / ".mujoco-mojo").exists()


def test_set_project_value_creates_the_file_in_the_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mujoco_mojo.settings.find_project_settings_file", lambda: None)
    monkeypatch.chdir(tmp_path)

    written = MujocoMojoSettings.set_project_value("slurm.sbatch.account", "proj123")

    assert written == tmp_path / ".mujoco-mojo" / "settings.toml"
    assert '"sbatch.account" = "proj123"' in written.read_text()


# --- commands ---


@pytest.fixture
def output(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Replaces the CLI's console with a wide one that records what is printed, so long paths never wrap."""
    buffer = io.StringIO()
    monkeypatch.setattr(
        cli_module,
        "console",
        Console(file=buffer, width=400, force_terminal=False, highlight=False),
    )
    return buffer


def _text(buffer: io.StringIO) -> str:
    """Printed text without panel borders, with whitespace collapsed."""
    return " ".join(re.sub(r"[│╭╮╰╯─]", " ", buffer.getvalue()).split())


def test_init_project_creates_a_nested_file_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: io.StringIO
) -> None:
    project = tmp_path / "project"
    parent_file = _project_file(project)
    sub = project / "sub"
    sub.mkdir()
    monkeypatch.chdir(sub)

    result = CliRunner().invoke(cli_app, ["settings", "init", "--project"])

    assert result.exit_code == 0, result.output
    assert (sub / ".mujoco-mojo" / "settings.toml").is_file()
    text = _text(output)
    assert f"{parent_file} already applies to this directory" in text
    assert "nested" in text


def test_init_project_has_no_note_when_there_is_no_parent_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: io.StringIO
) -> None:
    monkeypatch.setattr("mujoco_mojo.settings.find_project_settings_file", lambda: None)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli_app, ["settings", "init", "--project"])

    assert result.exit_code == 0, result.output
    assert (tmp_path / ".mujoco-mojo" / "settings.toml").is_file()
    assert "already applies" not in _text(output)


def test_show_project_scope_reads_the_parent_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: io.StringIO
) -> None:
    project = tmp_path / "project"
    parent_file = _project_file(project, '[slurm]\n"sbatch.account" = "PROJECT"\n')
    (project / "sub").mkdir()
    monkeypatch.chdir(project / "sub")

    result = CliRunner().invoke(cli_app, ["settings", "show", "--scope", "project"])

    assert result.exit_code == 0, result.output
    text = _text(output)
    assert '"sbatch.account" = "PROJECT"' in text
    assert str(parent_file) in text


def test_show_effective_names_the_parent_file_relative_to_here(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: io.StringIO
) -> None:
    """Used to raise ValueError: the file is not below the current directory."""
    project = tmp_path / "project"
    _project_file(project)
    (project / "sub").mkdir()
    monkeypatch.chdir(project / "sub")

    result = CliRunner().invoke(cli_app, ["settings", "show"])

    assert result.exit_code == 0, result.output
    assert "../.mujoco-mojo/settings.toml" in _text(output)


def test_show_project_scope_says_where_it_searched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: io.StringIO
) -> None:
    monkeypatch.setattr("mujoco_mojo.settings.find_project_settings_file", lambda: None)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli_app, ["settings", "show", "--scope", "project"])

    assert result.exit_code == 0, result.output
    assert f"in {tmp_path} or any parent directory" in _text(output)


def test_reset_project_deletes_the_discovered_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: io.StringIO
) -> None:
    project = tmp_path / "project"
    parent_file = _project_file(project, "[general]\nsymlink = true\n")
    (project / "sub").mkdir()
    monkeypatch.chdir(project / "sub")

    result = CliRunner().invoke(
        cli_app, ["settings", "reset", "--project"], input="y\n"
    )

    assert result.exit_code == 0, result.output
    assert not parent_file.exists()


def test_set_project_reports_which_file_it_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: io.StringIO
) -> None:
    project = tmp_path / "project"
    parent_file = _project_file(project)
    (project / "sub").mkdir()
    monkeypatch.chdir(project / "sub")

    result = CliRunner().invoke(
        cli_app, ["settings", "set", "--project", "slurm.sbatch.account", "proj123"]
    )

    assert result.exit_code == 0, result.output
    assert str(parent_file) in _text(output)
