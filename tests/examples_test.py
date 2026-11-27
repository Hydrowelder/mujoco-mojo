"""Tests for the examples that ship in `mujoco_mojo.examples`, and the `mujoco-mojo examples` commands that list and open them."""

import importlib
import inspect
import logging
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import mujoco
import pytest
from PIL import Image
from typer.testing import CliRunner

import mujoco_mojo as mojo
import mujoco_mojo.utils.layers.cli as cli_module
import mujoco_mojo.utils.layers.reloaded as reloaded_package
from mujoco_mojo.examples import EXAMPLES, ExampleName
from mujoco_mojo.utils.layers.cli import cli_app

EXAMPLES_DIR = Path(mojo.__file__).parent / "examples"


def build(example: ExampleName, folder: Path) -> tuple[bool, Path]:
    """Generates the example's model the way the runner does (seed 0, trial 0), bundles its file assets into `folder` and writes its XML there. Gives whether it had a file asset, and the XML's path."""
    module = importlib.import_module(EXAMPLES[example].module)
    generate: Callable[[mojo.MojoModel], mojo.MojoModel] = module.generate
    mojo_model = generate(mojo.MojoModel().with_seed(seed=0).with_trial_num(0))
    folder.mkdir(parents=True, exist_ok=True)
    bundled = mojo_model.mjcf.bundle_assets(
        target_dir=folder / "assets", rel_to_xml=Path("assets")
    )
    xml = folder / "model.xml"
    mojo_model.mjcf.write_xml(xml)
    return bundled, xml


def fake_reloaded(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Puts a stand-in for `MojoReloaded` in place, which only keeps what it was made with, and gives the list it keeps it in."""
    created: list[dict[str, Any]] = []

    def fake_session(**kwargs: Any) -> SimpleNamespace:
        created.append(kwargs)
        return SimpleNamespace(run=lambda: None)

    monkeypatch.setattr(reloaded_package, "MojoReloaded", fake_session)
    # the real one opens log files, and nothing here needs them
    monkeypatch.setattr(
        cli_module, "_setup_cli_logging", lambda **kwargs: logging.getLogger("test")
    )
    return created


def test_every_name_has_an_example() -> None:
    assert set(EXAMPLES) == set(ExampleName)


@pytest.mark.parametrize("example", list(ExampleName))
def test_an_example_is_a_module_of_the_package_with_a_generate_and_a_runtime(
    example: ExampleName,
) -> None:
    module = importlib.import_module(EXAMPLES[example].module)

    assert callable(module.generate)
    assert callable(module.runtime)
    assert module.__file__ is not None
    assert Path(module.__file__).is_relative_to(EXAMPLES_DIR)


@pytest.mark.parametrize("example", list(ExampleName))
def test_an_example_builds_from_an_empty_folder_without_a_file_asset(
    example: ExampleName, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mojo ships no asset files, so an example that read one (a mesh, an image) would only run where that file happened to be."""
    monkeypatch.chdir(tmp_path)

    bundled, xml = build(example, tmp_path / "model")

    assert not bundled, f"the {example} example reads a file asset"
    mujoco.MjModel.from_xml_path(str(xml))


def test_the_boxes_and_springs_skybox_is_used_when_its_images_are_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stars = tmp_path / "textures" / "stars"
    stars.mkdir(parents=True)
    for face in ("px", "nx", "py", "ny", "pz", "nz"):
        Image.new("RGB", (8, 8), "white").save(stars / f"{face}.png")
    monkeypatch.chdir(tmp_path)

    bundled, xml = build(ExampleName.BOXES_AND_SPRINGS, tmp_path / "model")

    assert bundled
    mujoco.MjModel.from_xml_path(str(xml))


def test_list_names_every_example() -> None:
    result = CliRunner().invoke(cli_app, ["examples", "list"])

    assert result.exit_code == 0, result.output
    for name in ExampleName:
        assert name.value in result.output


def test_run_opens_the_example_in_reloaded_and_logs_where_its_source_is_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = fake_reloaded(monkeypatch)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(cli_app, ["examples", "run", "tennis-racket"])

    assert result.exit_code == 0, result.output
    session = created[0]
    assert (
        session["generator"] == "mujoco_mojo.examples.tennis_racket.simulation.generate"
    )
    assert session["runtime"] == "mujoco_mojo.examples.tennis_racket.simulation.runtime"
    assert (
        session["workdir"] == (tmp_path / "mojo-examples" / "tennis-racket").resolve()
    )

    from mujoco_mojo.examples.tennis_racket import simulation as tennis_racket

    [intro] = session["intro"]
    path, line = intro.rsplit(" ", 1)[1].rsplit(":", 1)
    assert Path(path) == Path(inspect.getsourcefile(tennis_racket.generate) or "")
    assert int(line) == inspect.getsourcelines(tennis_racket.generate)[1]


def test_run_takes_another_workdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = fake_reloaded(monkeypatch)

    result = CliRunner().invoke(
        cli_app, ["examples", "run", "vlr", "--workdir", str(tmp_path / "mine")]
    )

    assert result.exit_code == 0, result.output
    assert created[0]["workdir"] == (tmp_path / "mine").resolve()


def test_run_says_how_to_install_a_dependency_the_example_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    created = fake_reloaded(monkeypatch)
    monkeypatch.chdir(tmp_path)
    import_module = importlib.import_module

    def without_mink(name: str, package: str | None = None) -> Any:
        if name == EXAMPLES[ExampleName.BERTHING].module:
            raise ModuleNotFoundError("No module named 'mink'", name="mink")
        return import_module(name, package)

    monkeypatch.setattr(cli_module.importlib, "import_module", without_mink)

    result = CliRunner().invoke(cli_app, ["examples", "run", "berthing"])

    assert result.exit_code == 1
    assert "mink" in result.output
    assert "mujoco-mojo[examples]" in result.output
    assert not created
