"""Tests for `mujoco-mojo docs path`, which tells a script or a coding assistant where the user guides that ship with the package are."""

import importlib
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

import mujoco_mojo.utils.layers.cli as cli_module
from mujoco_mojo.meta import USER_GUIDE_DIR
from mujoco_mojo.utils.layers.cli import cli_app

SCRIPTS = Path(__file__).parents[2] / "scripts"


def test_it_prints_the_folder_of_the_guides_and_nothing_else() -> None:
    result = CliRunner().invoke(cli_app, ["docs", "path"])

    assert result.exit_code == 0, result.output
    assert result.output == f"{USER_GUIDE_DIR}\n"


def test_the_folder_it_prints_holds_the_guides() -> None:
    assert (USER_GUIDE_DIR / "workflow" / "getting-started.md").is_file()
    assert (USER_GUIDE_DIR / "reference" / "cli.md").is_file()


def test_a_long_path_is_not_wrapped_or_styled(monkeypatch: pytest.MonkeyPatch) -> None:
    """A script reads this as one line. The command line's own console is made narrow here, because it is the one that would wrap the path if the command went through it."""
    monkeypatch.setattr(cli_module, "console", Console(width=20, force_terminal=True))

    result = CliRunner().invoke(cli_app, ["docs", "path"])

    assert result.output.splitlines() == [str(USER_GUIDE_DIR)]
    assert "\x1b" not in result.output


def test_it_is_in_the_help_of_the_docs_group() -> None:
    result = CliRunner().invoke(cli_app, ["docs", "--help"])

    assert result.exit_code == 0
    assert "path" in result.output


def test_it_is_a_command_of_the_program() -> None:
    result = CliRunner().invoke(cli_app, ["--help"])

    assert "docs" in result.output


def test_there_is_one_definition_of_where_the_guides_are(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The folder the command prints, the folder SensAI reads and the folder the generator writes have to be the same one."""
    from mujoco_mojo.utils.layers.dojo.sensai import guide_catalog

    monkeypatch.syspath_prepend(str(SCRIPTS))
    generator = importlib.import_module("gen_user_guide")

    assert guide_catalog.GUIDE_DIR == USER_GUIDE_DIR
    assert generator.OUTPUT_DIR == USER_GUIDE_DIR
