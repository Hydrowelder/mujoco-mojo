"""Tests for the `mujoco-mojo docs` commands: `path`, which tells a script or a coding assistant where the docs that ship with the package are, and `build` and `serve`, which build the docs site and browse it."""

import importlib
import inspect
from pathlib import Path

import pytest
import uvicorn
from rich.console import Console
from starlette.applications import Starlette
from starlette.testclient import TestClient
from typer.testing import CliRunner

import mujoco_mojo.utils.docs_site as docs_site
import mujoco_mojo.utils.layers.cli as cli_module
from mujoco_mojo.meta import DOCS_SOURCE_DIR
from mujoco_mojo.utils.docs_site import DocsBuildError
from mujoco_mojo.utils.layers.cli import cli_app

SCRIPTS = Path(__file__).parents[2] / "scripts"


def test_it_prints_the_folder_of_the_guides_and_nothing_else() -> None:
    result = CliRunner().invoke(cli_app, ["docs", "path"])

    assert result.exit_code == 0, result.output
    assert result.output == f"{DOCS_SOURCE_DIR}\n"


def test_the_folder_it_prints_holds_the_docs_source() -> None:
    """The guides, the command line reference, and the config that has their order."""
    assert (DOCS_SOURCE_DIR / "mkdocs.yml").is_file()
    guides = DOCS_SOURCE_DIR / "docs" / "user-guides"
    assert (guides / "workflow" / "getting-started.md").is_file()
    assert (DOCS_SOURCE_DIR / "docs" / "reference" / "cli.md").is_file()


def test_a_long_path_is_not_wrapped_or_styled(monkeypatch: pytest.MonkeyPatch) -> None:
    """A script reads this as one line. The command line's own console is made narrow here, because it is the one that would wrap the path if the command went through it."""
    monkeypatch.setattr(cli_module, "console", Console(width=20, force_terminal=True))

    result = CliRunner().invoke(cli_app, ["docs", "path"])

    assert result.output.splitlines() == [str(DOCS_SOURCE_DIR)]
    assert "\x1b" not in result.output


def test_it_is_in_the_help_of_the_docs_group() -> None:
    result = CliRunner().invoke(cli_app, ["docs", "--help"])

    assert result.exit_code == 0
    assert "path" in result.output
    assert "build" in result.output
    assert "serve" in result.output
    assert "list" in result.output


def test_it_is_a_command_of_the_program() -> None:
    result = CliRunner().invoke(cli_app, ["--help"])

    assert "docs" in result.output


def test_there_is_one_definition_of_where_the_docs_are(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The folder the command prints, the folder SensAI reads its docs from and the folder the generator writes have to be the same one."""
    from mujoco_mojo.utils.layers.dojo.sensai import docs_catalog

    monkeypatch.syspath_prepend(str(SCRIPTS))
    generator = importlib.import_module("gen_docs_source")

    default = inspect.signature(docs_catalog.docs_pages).parameters["directory"].default
    assert default == DOCS_SOURCE_DIR
    assert generator.OUTPUT_DIR == DOCS_SOURCE_DIR


INSTALLED = "1.2.3"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `~/.mujoco-mojo` that is not the real one, an installed version that is not the real one, and a console wide enough not to wrap what the commands print."""
    folder = tmp_path / "mojo-home"
    monkeypatch.setattr(docs_site, "MUJOCO_MOJO_DIR", folder)
    monkeypatch.setattr(cli_module, "VERSION", INSTALLED)
    monkeypatch.setattr(cli_module, "console", Console(width=300))
    return folder


def make_site(home: Path, version: str, text: str = "docs") -> Path:
    site = home / "docs" / f"v{version}"
    site.mkdir(parents=True)
    (site / "index.html").write_text(text)
    return site


def fake_build(
    monkeypatch: pytest.MonkeyPatch,
    home: Path,
    *,
    error: Exception | None = None,
) -> list[dict[str, object]]:
    """Replaces the build with one that makes a site (or fails with `error`), and records what it was asked."""
    calls: list[dict[str, object]] = []

    def build(version: str, *, rebuild: bool = False) -> Path:
        calls.append({"version": version, "rebuild": rebuild})
        if error is not None:
            raise error
        return make_site(home, version, "just built")

    monkeypatch.setattr(docs_site, "build_docs", build)
    return calls


def fake_serve(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Replaces the web server, which would not return, with a function that records what it was asked to serve."""
    calls: list[dict[str, object]] = []

    def run(app: object, **kwargs: object) -> None:
        calls.append({"app": app, **kwargs})

    monkeypatch.setattr(uvicorn, "run", run)
    return calls


def served_text(call: dict[str, object]) -> str:
    app = call["app"]
    assert isinstance(app, Starlette)
    with TestClient(app) as client:
        return client.get("/").text


def test_a_built_site_is_served_without_building_it(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_site(home, INSTALLED, "already built")
    builds = fake_build(monkeypatch, home)
    serves = fake_serve(monkeypatch)

    result = CliRunner().invoke(cli_app, ["docs", "serve"])

    assert result.exit_code == 0, result.output
    assert builds == []
    (served,) = serves
    assert served_text(served) == "already built"
    assert served["host"] == cli_module._SETTINGS.general.default_host
    assert isinstance(served["port"], int)
    assert f"v{INSTALLED}" in result.output


def test_a_site_that_is_not_built_is_built_and_then_served(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builds = fake_build(monkeypatch, home)
    serves = fake_serve(monkeypatch)

    result = CliRunner().invoke(cli_app, ["docs", "serve"])

    assert result.exit_code == 0, result.output
    assert builds == [{"version": INSTALLED, "rebuild": False}]
    assert "not built yet" in result.output
    assert served_text(serves[0]) == "just built"


def test_nothing_is_served_when_the_build_cannot_run(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_build(
        monkeypatch,
        home,
        error=ModuleNotFoundError("Install with `pip install mujoco-mojo[docs]`"),
    )
    serves = fake_serve(monkeypatch)

    result = CliRunner().invoke(cli_app, ["docs", "serve"])

    assert result.exit_code == 1
    assert "Error" in result.output
    assert "pip install mujoco-mojo[docs]" in result.output
    assert serves == []


def test_another_version_that_is_not_built_is_not_built_for_you(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_site(home, "1.0.0")
    builds = fake_build(monkeypatch, home)
    serves = fake_serve(monkeypatch)

    result = CliRunner().invoke(cli_app, ["docs", "serve", "--version", "9.9.9"])

    assert result.exit_code == 1
    assert builds == []
    assert serves == []
    assert "v9.9.9 are not built" in result.output
    assert f"v{INSTALLED}" in result.output
    assert "1.0.0" in result.output


def test_a_site_an_older_install_built_can_be_served(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_site(home, "1.0.0", "the old docs")
    builds = fake_build(monkeypatch, home)
    serves = fake_serve(monkeypatch)

    result = CliRunner().invoke(cli_app, ["docs", "serve", "--version", "v1.0.0"])

    assert result.exit_code == 0, result.output
    assert builds == []
    assert served_text(serves[0]) == "the old docs"


def test_the_host_and_port_are_the_ones_asked_for(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_site(home, INSTALLED)
    serves = fake_serve(monkeypatch)

    result = CliRunner().invoke(
        cli_app, ["docs", "serve", "--host", "0.0.0.0", "--port", "8123"]
    )

    assert result.exit_code == 0, result.output
    assert serves[0]["host"] == "0.0.0.0"
    assert serves[0]["port"] == 8123
    assert "Mobile:" in result.output


def test_build_builds_the_installed_version_and_prints_where_it_is(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builds = fake_build(monkeypatch, home)

    result = CliRunner().invoke(cli_app, ["docs", "build"])

    assert result.exit_code == 0, result.output
    assert builds == [{"version": INSTALLED, "rebuild": False}]
    assert result.output.strip().endswith(str(home / "docs" / f"v{INSTALLED}"))


def test_build_can_be_told_to_build_again(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builds = fake_build(monkeypatch, home)

    result = CliRunner().invoke(cli_app, ["docs", "build", "--rebuild"])

    assert result.exit_code == 0, result.output
    assert builds == [{"version": INSTALLED, "rebuild": True}]


@pytest.mark.parametrize(
    "error",
    [
        ModuleNotFoundError("needs the docs extra: pip install mujoco-mojo[docs]"),
        DocsBuildError("The docs build failed:\nit broke"),
    ],
)
def test_build_reports_a_failure_as_an_error(
    home: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    fake_build(monkeypatch, home, error=error)

    result = CliRunner().invoke(cli_app, ["docs", "build"])

    assert result.exit_code == 1
    assert "Error" in result.output
    assert str(error).splitlines()[-1] in result.output


def test_list_shows_each_built_version_and_where_it_is(home: Path) -> None:
    make_site(home, "2.0.0")
    make_site(home, INSTALLED)
    make_site(home, "1.0.0")
    # a folder with no site in it, and a build that did not finish, are not built docs
    (home / "docs" / "v3.0.0").mkdir()
    (home / "docs" / ".build-v4.0.0-abc").mkdir()

    result = CliRunner().invoke(cli_app, ["docs", "list"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        f"  1.0.0  {home / 'docs' / 'v1.0.0'}",
        f"* {INSTALLED}  {home / 'docs' / f'v{INSTALLED}'}",
        f"  2.0.0  {home / 'docs' / 'v2.0.0'}",
    ]


def test_list_orders_versions_as_numbers_and_lines_the_paths_up(home: Path) -> None:
    for version in ("2.10.0", "2.9.0", "2.7.1"):
        make_site(home, version)

    result = CliRunner().invoke(cli_app, ["docs", "list"])

    assert [line.split()[0] for line in result.output.splitlines()] == [
        "2.7.1",
        "2.9.0",
        "2.10.0",
    ]
    # the folders start in the same column, whatever the length of the version
    assert len({line.index(str(home)) for line in result.output.splitlines()}) == 1


def test_list_marks_only_the_installed_version(home: Path) -> None:
    make_site(home, "1.0.0")

    result = CliRunner().invoke(cli_app, ["docs", "list"])

    assert "*" not in result.output


def test_list_says_so_when_nothing_is_built(home: Path) -> None:
    result = CliRunner().invoke(cli_app, ["docs", "list"])

    assert result.exit_code == 0, result.output
    assert "No docs are built yet" in result.output
    assert "docs build" in result.output


def test_a_long_path_in_the_list_is_not_wrapped_or_styled(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A script reads each line as a version and a path."""
    make_site(home, INSTALLED)
    monkeypatch.setattr(cli_module, "console", Console(width=20, force_terminal=True))

    result = CliRunner().invoke(cli_app, ["docs", "list"])

    assert result.output.splitlines() == [
        f"* {INSTALLED}  {home / 'docs' / f'v{INSTALLED}'}"
    ]
    assert "\x1b" not in result.output
