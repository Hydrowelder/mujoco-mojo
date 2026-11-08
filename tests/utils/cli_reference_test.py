"""Tests for the command line reference page, which `scripts/gen_cli_reference.py` writes from the `mujoco-mojo` command line."""

import enum
import importlib
import os
import re
from pathlib import Path
from types import ModuleType
from typing import Annotated

import pytest
import typer
from typer.main import get_command

from mujoco_mojo.utils.layers.cli import cli_app

ROOT = Path(__file__).parents[2]
SCRIPTS = ROOT / "scripts"


@pytest.fixture
def generator(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The script that writes the page, which lives in `scripts/`."""
    monkeypatch.syspath_prepend(str(SCRIPTS))
    return importlib.import_module("gen_cli_reference")


class Mode(enum.StrEnum):
    FAST = "fast"
    SLOW = "slow"


class Plain(enum.Enum):
    """An enum that is not a `StrEnum`, whose `str()` is not its value."""

    FIRST = "first"
    SECOND = "second"


def small_app() -> typer.Typer:
    """A command line with one of each kind of parameter, so the page's rules can be checked on it."""
    app = typer.Typer(rich_markup_mode="rich", help="[bold cyan]Demo[/bold cyan] tool.")
    sub = typer.Typer(rich_markup_mode="rich", help="Things to [bold]do[/bold].")

    @app.command()
    def build(
        target: Annotated[
            Path,
            typer.Argument(help="Where to build, as a [bold cyan]path[/bold cyan]."),
        ],
        needed: Annotated[str, typer.Option(help="Must be given.")],
        label: Annotated[str, typer.Argument(help="A label.")] = "none-given",
        name: Annotated[
            str, typer.Option("--name", "-n", help="A name | with a pipe.")
        ] = "x",
        size: Annotated[int, typer.Option(min=1, max=9, help="How big.")] = 3,
        ratio: Annotated[float, typer.Option(min=0.5, help="A ratio.")] = 1.5,
        mode: Annotated[Mode, typer.Option(help="Which mode.")] = Mode.SLOW,
        plain: Annotated[Plain, typer.Option(help="Which one.")] = Plain.SECOND,
        out: Annotated[Path, typer.Option(help="Output folder.")] = Path("out-dir"),
        cache: Annotated[bool, typer.Option(help="Use the cache.")] = True,
        force: Annotated[bool, typer.Option("--force", "-f", help="Force it.")] = False,
        tag: Annotated[
            list[str] | None, typer.Option("--tag", "-t", help="A tag.")
        ] = None,
        step: Annotated[list[int], typer.Option(help="Steps.")] = [],
        verbose: Annotated[
            int, typer.Option("--verbose", "-v", count=True, help="Louder.")
        ] = 0,
        secret: Annotated[str, typer.Option(hidden=True, help="Not shown.")] = "s",
    ) -> None:
        """
        Build the [bold yellow]thing[/bold yellow].

        Takes a [bold cyan]target[/bold cyan]
        over two lines, and use [OPTIONS] as written.
        """

    @sub.command()
    def deploy() -> None:
        """Ship it."""

    @sub.command(hidden=True)
    def internal() -> None:
        """Not for users."""

    app.add_typer(sub, name="ops")
    return app


@pytest.fixture
def page(generator: ModuleType) -> str:
    text = generator.render(small_app(), program="demo")
    assert isinstance(text, str)
    return text


def section(page: str, heading: str) -> str:
    """The text of the section under `heading`, up to the next heading."""
    start = page.index(heading + "\n")
    rest = page[start + len(heading) :]
    end = re.search(r"\n#{1,6} ", rest)
    return rest[: end.start()] if end else rest


class TestTheRealCommandLine:
    def test_the_committed_page_is_current(self, generator: ModuleType) -> None:
        """The docs show this page and the package bundles it, so it has to match the command line. The `gen-cli-reference` pre-commit hook rewrites it."""
        assert not generator.stale(), (
            "docs/reference/cli.md is out of date. "
            "Run: python scripts/gen_cli_reference.py"
        )

    def test_the_page_is_the_same_whatever_settings_the_machine_has(
        self,
        generator: ModuleType,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Many defaults on the command line come from the user's settings, so a page written on a machine with settings of its own would fail the check anywhere else. A global settings file, a project one and `MUJOCO_MOJO_*` variables are all set here, and the page does not show them."""
        home = tmp_path / "home"
        (home / ".mujoco-mojo").mkdir(parents=True)
        (home / ".mujoco-mojo" / "settings.toml").write_text(
            '[general]\nn_proc = 7\n\n[reloaded]\nui = "studio"\n', encoding="utf-8"
        )
        project = tmp_path / "project"
        (project / ".mujoco-mojo").mkdir(parents=True)
        (project / ".mujoco-mojo" / "settings.toml").write_text(
            '[general]\nxml_name = "mine.xml"\n', encoding="utf-8"
        )
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setenv("USERPROFILE", str(home))
        monkeypatch.chdir(project)
        monkeypatch.setenv("MUJOCO_MOJO_GENERAL__MODEL_CONFIG_NAME", "mine")
        monkeypatch.setenv("MUJOCO_MOJO_RUN__MONTE_CARLO__RESUME", "false")

        page = generator.render()

        assert page == generator.OUTPUT.read_text(encoding="utf-8")
        assert (
            "| `--user-interface`, `-ui` | one of `opengl`, `studio`, `web` | `web` |"
            in page
        )

    def test_the_clean_environment_has_none_of_the_machines_settings(
        self, generator: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MUJOCO_MOJO_GENERAL__N_PROC", "5")
        monkeypatch.setenv("MUJOCO_MOJO_RELOADED__UI", "studio")
        monkeypatch.setenv("SOME_OTHER_VARIABLE", "kept")

        environment = generator.clean_environment("/empty/home")

        assert environment["HOME"] == "/empty/home"
        assert environment["USERPROFILE"] == "/empty/home"
        # the machine's own variables are gone, and the viewer is the one pinned value
        assert {name for name in environment if name.startswith("MUJOCO_MOJO_")} == {
            "MUJOCO_MOJO_RELOADED__UI"
        }
        assert environment["MUJOCO_MOJO_RELOADED__UI"] == "web"
        # everything else is left as it is, since the child needs its PATH and the like
        assert environment["SOME_OTHER_VARIABLE"] == "kept"

    def test_a_command_line_that_cannot_be_read_fails_with_what_the_child_said(
        self, generator: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A viewer that is not one makes the settings invalid, so the child cannot import the command line, and the page is not written from nothing."""
        monkeypatch.setattr(
            generator,
            "clean_environment",
            lambda home: {
                **os.environ,
                "HOME": home,
                "MUJOCO_MOJO_RELOADED__UI": "not-a-viewer",
            },
        )

        with pytest.raises(RuntimeError, match="reading the command line failed"):
            generator.render()

    def test_every_command_has_a_section_and_every_option_is_in_it(
        self, generator: ModuleType
    ) -> None:
        page = generator.OUTPUT.read_text(encoding="utf-8")
        commands = list(generator.walk(get_command(cli_app), ["mujoco-mojo"]))

        assert len(commands) >= 10
        for path, command in commands[1:]:
            text = section(page, f"{'#' * len(path)} `{' '.join(path)}`")
            for param in command.params:
                if getattr(param, "hidden", False):
                    continue
                assert param.opts[0] in text or param.name.upper() in text, (
                    path,
                    param.opts,
                )

    def test_a_command_with_sub_commands_lists_them_with_links(
        self, generator: ModuleType
    ) -> None:
        page = generator.OUTPUT.read_text(encoding="utf-8")
        text = section(page, "## `mujoco-mojo run`")

        for name in ("monte-carlo", "single", "optimization", "watch-workdir"):
            assert f"[`mujoco-mojo run {name}`](#mujoco-mojo-run-{name})" in text

    def test_no_rich_markup_or_terminal_codes_are_left(
        self, generator: ModuleType
    ) -> None:
        page = generator.OUTPUT.read_text(encoding="utf-8")

        assert not re.search(
            r"\[/?(?:bold|dim|italic|underline|link|red|green|yellow|cyan|white)\b",
            page,
        )
        assert "\x1b" not in page

    def test_a_real_default_and_a_real_choice_are_on_the_page(
        self, generator: ModuleType
    ) -> None:
        page = generator.OUTPUT.read_text(encoding="utf-8")
        text = section(page, "### `mujoco-mojo run monte-carlo`")

        assert (
            "| `--execution-mode`, `-em` | one of `local`, `slurm` | `local` |" in text
        )
        assert "| `--workdir`, `-w` | path | `mojo-models` |" in text
        assert "| `--resume` / `--no-resume` | flag | `--resume` |" in text


class TestRules:
    """What the page says about each kind of parameter, on a small command line made for it."""

    def test_the_page_names_the_commands_in_a_table_with_links(self, page: str) -> None:
        assert "| [`demo build`](#demo-build) | Build the **thing**. |" in page or (
            "| [`demo build`](#demo-build) | Build the thing. |" in page
        )
        assert "[`demo ops`](#demo-ops)" in page

    def test_a_command_is_a_heading_and_a_sub_command_one_level_deeper(
        self, page: str
    ) -> None:
        assert "\n## `demo build`\n" in page
        assert "\n## `demo ops`\n" in page
        assert "\n### `demo ops deploy`\n" in page

    def test_a_hidden_command_and_a_hidden_option_are_left_out(self, page: str) -> None:
        assert "internal" not in page
        assert "--secret" not in page

    def test_a_help_text_loses_its_markup_the_way_help_does(self, page: str) -> None:
        text = section(page, "## `demo build`")

        assert "Build the thing." in text
        assert "[bold" not in text
        # joined into one paragraph, and `[OPTIONS]` is kept as written
        assert "Takes a `target` over two lines, and use [OPTIONS] as written." in text

    def test_cyan_markup_becomes_code_and_bold_becomes_bold(self, page: str) -> None:
        assert "Where to build, as a `path`." in page
        assert "Things to **do**." in page

    def test_the_usage_line_has_the_arguments_in_capitals_and_optional_ones_in_brackets(
        self, page: str
    ) -> None:
        assert "demo build [OPTIONS] TARGET [LABEL]" in page

    def test_a_group_s_usage_line_ends_with_command_and_args(self, page: str) -> None:
        assert "demo ops [OPTIONS] COMMAND [ARGS]..." in page

    def test_an_argument_has_a_table_with_its_type_and_help(self, page: str) -> None:
        text = section(page, "## `demo build`")

        assert "| `TARGET` | path | Where to build, as a `path`. |" in text
        assert "| `LABEL` | text | A label. |" in text

    def test_a_default_is_shown_as_the_command_line_takes_it(self, page: str) -> None:
        text = section(page, "## `demo build`")

        assert "| `--name`, `-n` | text | `x` |" in text
        assert "| `--size` | integer, between 1 and 9 | `3` |" in text
        assert "| `--out` | path | `out-dir` |" in text

    def test_an_enum_shows_its_value_and_its_choices(self, page: str) -> None:
        text = section(page, "## `demo build`")

        assert "| `--mode` | one of `fast`, `slow` | `slow` |" in text

    def test_an_enum_that_is_not_a_string_enum_shows_its_value_too(
        self, page: str
    ) -> None:
        text = section(page, "## `demo build`")

        assert "| `--plain` | one of `first`, `second` | `second` |" in text

    @pytest.mark.parametrize("name", ["int range", "integer range"])
    def test_the_name_click_gives_a_range_does_not_matter(
        self, generator: ModuleType, name: str
    ) -> None:
        """Typer's bundled click calls it `int range` and click 8.3 `integer range`, and the page has to read the same under both."""

        class Kind:
            min = 1
            max = None

            def __init__(self, name: str) -> None:
                self.name = name

        class Param:
            type = Kind(name)
            count = False
            is_flag = False
            multiple = False

        assert generator.type_text(Param()) == "integer, at least 1"

    def test_a_range_with_only_an_upper_bound_says_at_most(
        self, generator: ModuleType
    ) -> None:
        class Upper:
            name = "int range"
            min = None
            max = 5

        class Param:
            type = Upper()
            count = False
            is_flag = False
            multiple = False

        assert generator.type_text(Param()) == "integer, at most 5"

    def test_a_range_says_what_it_is_bounded_by(self, page: str) -> None:
        text = section(page, "## `demo build`")

        assert "| `--ratio` | number, at least 0.5 | `1.5` |" in text

    def test_a_flag_that_can_be_turned_off_shows_both_ways_and_which_is_the_default(
        self, page: str
    ) -> None:
        text = section(page, "## `demo build`")

        assert "| `--cache` / `--no-cache` | flag | `--cache` |" in text

    def test_a_plain_flag_shows_whether_it_is_on(self, page: str) -> None:
        assert "| `--force`, `-f` | flag | off |" in section(page, "## `demo build`")

    def test_a_counter_is_a_count(self, page: str) -> None:
        assert "| `--verbose`, `-v` | count | `0` |" in section(page, "## `demo build`")

    def test_a_repeatable_option_says_so_and_defaults_to_none(self, page: str) -> None:
        text = section(page, "## `demo build`")

        assert "| `--tag`, `-t` | text, repeatable | none |" in text
        assert "| `--step` | integer, repeatable | none |" in text

    def test_a_required_option_says_required(self, page: str) -> None:
        assert "| `--needed` | text | required |" in section(page, "## `demo build`")

    def test_a_pipe_in_a_help_text_does_not_break_the_table(self, page: str) -> None:
        assert "A name \\| with a pipe." in page

    def test_a_command_with_nothing_to_set_has_no_empty_tables(self, page: str) -> None:
        text = section(page, "### `demo ops deploy`")

        assert "Ship it." in text
        assert "**Options**" not in text
        assert "**Arguments**" not in text

    def test_the_page_starts_with_a_note_that_it_is_written_by_the_script(
        self, page: str
    ) -> None:
        assert page.startswith("<!-- Written by scripts/gen_cli_reference.py")

    def test_rendering_is_deterministic(self, generator: ModuleType) -> None:
        assert generator.render(small_app(), program="demo") == generator.render(
            small_app(), program="demo"
        )
