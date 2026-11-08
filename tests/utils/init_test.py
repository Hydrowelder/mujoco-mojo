import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

import mujoco_mojo.settings as settings_module
from mujoco_mojo.meta import USER_GUIDE_DIR
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


def run_init() -> str:
    result = CliRunner().invoke(cli_app, ["init"])

    assert result.exit_code == 0, result.output
    return result.output


class TestTheAgentsFile:
    """`init` writes an AGENTS.md that tells coding agents where the Mojo guides are, so an agent that never heard of Mojo can still find them."""

    def test_it_is_written_and_points_at_the_guides_command(
        self, project: Path
    ) -> None:
        run_init()

        text = (project / "AGENTS.md").read_text(encoding="utf-8")
        assert text.startswith("# MuJoCo Mojo")
        assert "`mujoco-mojo docs path`" in text

    def test_every_guide_it_names_is_in_the_bundle(self, project: Path) -> None:
        """A guide renamed in the docs would leave every new project pointing at nothing."""
        run_init()

        named = re.findall(
            r"`([\w./-]+\.md)`", (project / "AGENTS.md").read_text(encoding="utf-8")
        )

        assert "workflow/getting-started.md" in named
        assert "reference/cli.md" in named
        for path in named:
            assert (USER_GUIDE_DIR / path).is_file(), path

    def test_the_scripts_it_names_are_the_ones_init_writes(self, project: Path) -> None:
        run_init()

        text = (project / "AGENTS.md").read_text(encoding="utf-8")
        for script in re.findall(r"`bash ([\w.]+)`", text):
            assert (project / script).is_file(), script

    def test_it_is_listed_with_the_other_files_init_wrote(self, project: Path) -> None:
        output = run_init()

        assert "AGENTS.md" in output
        assert "points coding agents at the guides" in output

    def test_an_agents_file_that_is_there_is_left_alone(self, project: Path) -> None:
        (project / "AGENTS.md").write_text("# Mine\n\nKeep this.\n", encoding="utf-8")

        output = run_init()

        assert (project / "AGENTS.md").read_text(
            encoding="utf-8"
        ) == "# Mine\n\nKeep this.\n"
        assert "points coding agents at the guides" not in output

    def test_and_the_text_to_add_is_shown_whole_for_copying(
        self, project: Path
    ) -> None:
        (project / "AGENTS.md").write_text("# Mine\n", encoding="utf-8")

        output = run_init()

        assert "AGENTS.md already exists, so it was left alone" in output
        # a line of it, unbroken: no wrapping of rich's own in text meant to be copied
        assert (
            "- Run the campaign with `bash run.sh` and open the interactive viewer with `bash reloaded.sh`."
            in output
        )

    def test_the_other_files_are_written_whether_or_not_it_was(
        self, project: Path
    ) -> None:
        (project / "AGENTS.md").write_text("# Mine\n", encoding="utf-8")

        run_init()

        for name in ("simulation.py", "run.sh", "reloaded.sh"):
            assert (project / name).is_file(), name

    def test_an_existing_script_still_stops_init_and_no_agents_file_is_written(
        self, project: Path
    ) -> None:
        (project / "simulation.py").write_text("# mine\n", encoding="utf-8")

        result = CliRunner().invoke(cli_app, ["init"])

        assert result.exit_code == 1
        assert "already exist" in result.output
        assert not (project / "AGENTS.md").exists()

    def test_a_second_run_does_not_rewrite_it(self, project: Path) -> None:
        run_init()
        (project / "AGENTS.md").write_text("# Edited by hand\n", encoding="utf-8")
        for name in ("simulation.py", "run.sh", "reloaded.sh"):
            (project / name).unlink()

        run_init()

        assert (project / "AGENTS.md").read_text(
            encoding="utf-8"
        ) == "# Edited by hand\n"

    def test_the_optimizer_project_gets_it_too(self, project: Path) -> None:
        result = CliRunner().invoke(cli_app, ["init", "--optimizer"])

        assert result.exit_code == 0, result.output
        assert (project / "AGENTS.md").is_file()


class TestWhenClaudeMdIsInTheWay:
    """Claude Code reads CLAUDE.md instead of AGENTS.md when both are there, so a project with one would never see the pointer."""

    HINT = "Add this line to it so it reads AGENTS.md too"

    @staticmethod
    def flat(output: str) -> str:
        """The output on one line, since rich wraps a sentence at the width of the terminal."""
        return " ".join(output.split())

    def test_a_claude_file_in_the_project_gets_a_hint_to_import_agents_md(
        self, project: Path
    ) -> None:
        (project / "CLAUDE.md").write_text("# Notes\n", encoding="utf-8")

        output = run_init()

        assert self.HINT in self.flat(output)
        assert "@AGENTS.md" in output

    def test_one_in_a_folder_above_counts_too(self, project: Path) -> None:
        (project.parent / "CLAUDE.md").write_text("# Notes\n", encoding="utf-8")

        assert self.HINT in self.flat(run_init())

    def test_one_that_already_imports_it_gets_no_hint(self, project: Path) -> None:
        (project / "CLAUDE.md").write_text("# Notes\n\n@AGENTS.md\n", encoding="utf-8")

        assert self.HINT not in self.flat(run_init())

    def test_no_claude_file_gets_no_hint(self, project: Path) -> None:
        output = run_init()

        assert self.HINT not in self.flat(output)
        assert "CLAUDE.md" not in output

    def test_the_hint_comes_with_an_existing_agents_file_too(
        self, project: Path
    ) -> None:
        (project / "AGENTS.md").write_text("# Mine\n", encoding="utf-8")
        (project / "CLAUDE.md").write_text("# Notes\n", encoding="utf-8")

        assert self.HINT in self.flat(run_init())
