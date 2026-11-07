"""Tests for the model files the docs link to in MuJoCo Live, which `scripts/gen_docs_models.py` writes."""

import importlib
import re
from pathlib import Path
from types import ModuleType

import mujoco
import pytest

ROOT = Path(__file__).parents[2]
SCRIPTS = ROOT / "scripts"
DOCS = ROOT / "docs"
LIVE_LINK = re.compile(
    r"https://live\.mujoco\.org/\?model=github:Hydrowelder/mujoco-mojo/master/(\S+?\.xml)"
)


@pytest.fixture
def generator(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The script that writes the models, which lives in `scripts/`."""
    monkeypatch.syspath_prepend(str(SCRIPTS))
    return importlib.import_module("gen_docs_models")


def test_the_committed_models_are_current(generator: ModuleType) -> None:
    """The docs link to these files, so each must match what its example builds. The `gen-docs-models` pre-push hook rewrites them."""
    for name in generator.EXAMPLES:
        committed = generator.output_path(name).read_text(encoding="utf-8")

        assert generator.render(name) == committed, (
            f"docs/assets/models/{name}/model.xml is out of date. "
            "Run: python scripts/gen_docs_models.py"
        )


def test_rendering_is_deterministic(generator: ModuleType) -> None:
    """A model that changed between runs would make the staleness check fail on every push."""
    for name in generator.EXAMPLES:
        assert generator.render(name) == generator.render(name)


def test_the_models_stand_on_their_own(generator: ModuleType) -> None:
    """MuJoCo Live reads one XML file from GitHub, so it cannot reach a file asset or a path on the machine that wrote it."""
    for name in generator.EXAMPLES:
        text = generator.output_path(name).read_text(encoding="utf-8")

        assert not re.search(r'\bfile\w*="', text), f"{name} has a file asset"
        assert str(ROOT) not in text
        assert "/home/" not in text
        assert not re.search(r"[A-Za-z]:\\", text)


def test_the_models_compile(generator: ModuleType) -> None:
    """A committed model that MuJoCo rejects would open as an error in Live."""
    for name in generator.EXAMPLES:
        mujoco.MjModel.from_xml_path(str(generator.output_path(name)))


def test_every_model_is_linked_from_the_docs_and_every_link_has_a_model(
    generator: ModuleType,
) -> None:
    """The links name a path on the `master` branch, so a link to a file that is not there, or a model nothing links to, is a mistake."""
    linked: set[str] = set()
    for page in DOCS.rglob("*.md"):
        linked.update(LIVE_LINK.findall(page.read_text(encoding="utf-8")))
    committed = {
        generator.output_path(name).relative_to(ROOT).as_posix()
        for name in generator.EXAMPLES
    }

    assert linked == committed
