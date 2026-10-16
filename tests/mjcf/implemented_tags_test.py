import importlib
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS = Path(__file__).parents[2] / "scripts"
JOINER = "⁠"


@pytest.fixture
def generator(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The script that writes the checklist of implemented MJCF tags, which lives in `scripts/` and imports its sibling scripts."""
    monkeypatch.syspath_prepend(str(SCRIPTS))
    return importlib.import_module("gen_mjcf_tags")


def test_the_committed_checklist_is_current(generator: ModuleType) -> None:
    """The MJCF reference page includes this file, so it must match the classes. The `gen-mjcf-tags` pre-commit hook rewrites it."""
    committed = generator.OUTPUT.read_text(encoding="utf-8")

    assert generator.render() == committed, (
        "scripts/generated/implemented_mjcf_tags.md is out of date. "
        "Run: python scripts/gen_mjcf_tags.py"
    )


def test_rendering_is_deterministic(generator: ModuleType) -> None:
    """A generated file that reordered itself between runs would churn the diff on every commit."""
    assert generator.render() == generator.render()


def test_each_element_is_expanded_only_where_it_is_first_reached(
    generator: ModuleType,
) -> None:
    """A frame holds the same children as a body, but listing them under both would double the page."""
    lines = [line.strip() for line in generator.render().splitlines()]

    assert lines.count(f"- [x] body/{JOINER}inertial") == 1
    assert f"- [x] frame/{JOINER}body" in lines


def test_the_same_tag_in_different_places_keeps_its_own_children(
    generator: ModuleType,
) -> None:
    """`plugin` in a body is a different element from `plugin` in the extension, and only the latter holds instances."""
    lines = [line.strip() for line in generator.render().splitlines()]

    assert lines.count(f"- [x] plugin/{JOINER}instance") == 1
    assert lines.index(f"- [x] plugin/{JOINER}instance") == (
        lines.index(f"- [x] extension/{JOINER}plugin") + 1
    )


def test_what_mojo_leaves_out_is_listed_as_not_implemented(
    generator: ModuleType,
) -> None:
    lines = [line.strip() for line in generator.render().splitlines()]

    assert "- Not implemented" in lines
    assert "- [ ] default" in lines
    assert f"- [ ] custom/{JOINER}numeric" in lines
