from pathlib import Path

import pytest
from typer.testing import CliRunner

import mujoco_mojo.settings as settings_module
from mujoco_mojo.utils.layers.cli import cli_app


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty directory to run `init` in, with a global settings file already present so it does not ask to make one."""
    global_settings = tmp_path / "global" / "settings.toml"
    global_settings.parent.mkdir()
    global_settings.write_text("")
    monkeypatch.setattr(settings_module, "GLOBAL_SETTINGS_FILE", global_settings)
    work = tmp_path / "project"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


def test_the_reloaded_script_leaves_the_viewer_to_the_settings(project: Path) -> None:
    """A viewer written into the script would be right for the machine `init` ran on and wrong for any other the project is used on."""
    result = CliRunner().invoke(cli_app, ["init"])

    assert result.exit_code == 0, result.output
    script = project / "reloaded.sh"
    assert "-ui" not in script.read_text()
    assert "-g simulation.generate" in script.read_text()
    assert script.stat().st_mode & 0o111
