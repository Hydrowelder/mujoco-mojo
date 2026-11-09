"""Tests for the docs source bundled in the package, which `scripts/gen_docs_source.py` writes and `mujoco-mojo docs build` builds the site from."""

import importlib
import re
from pathlib import Path
from types import ModuleType

import pytest

from mujoco_mojo.meta import DOCS_SOURCE_DIR

ROOT = Path(__file__).parents[2]
SCRIPTS = ROOT / "scripts"

# the largest file the repo's `check-added-large-files` hook lets in
LARGEST_FILE = 500 * 1024

# a curly apostrophe, which the `fix-smart-quotes` hook turns into a straight one. built here, not typed, since a literal one in the source is what that hook (and ruff) exist to catch
CURLY = chr(0x2019)

_NAV_PAGE = re.compile(r"^\s*-\s+(?:[^:\n]+:\s+)?([\w./-]+\.md)\s*$", re.MULTILINE)
_INCLUDE = re.compile(r'^\s*--8<--\s+"', re.MULTILINE)


@pytest.fixture
def generator(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The script that writes the bundle, which lives in `scripts/`."""
    monkeypatch.syspath_prepend(str(SCRIPTS))
    return importlib.import_module("gen_docs_source")


def bundled() -> list[Path]:
    return sorted(p for p in DOCS_SOURCE_DIR.rglob("*") if p.is_file())


def test_the_bundled_source_is_current(generator: ModuleType) -> None:
    """The package ships these files, so each must match its source. The `gen-docs-source` pre-commit hook rewrites them."""
    assert generator.stale() == [], (
        "the bundled docs source is out of date. Run: python scripts/gen_docs_source.py"
    )


def test_there_is_one_definition_of_where_the_source_is(
    generator: ModuleType,
) -> None:
    assert generator.OUTPUT_DIR == DOCS_SOURCE_DIR


def test_it_holds_no_images_scripts_and_nothing_too_large_to_commit(
    generator: ModuleType,
) -> None:
    """The example scripts are not in it: a page holds the part of one that it includes."""
    allowed = generator.KEEP | {".yml"}

    assert {p.suffix for p in bundled()} <= allowed
    assert ".py" not in {p.suffix for p in bundled()}
    assert [p for p in bundled() if p.stat().st_size > LARGEST_FILE] == []


def test_the_config_is_a_copy_of_the_one_in_the_repo() -> None:
    assert (DOCS_SOURCE_DIR / "mkdocs.yml").read_bytes() == (
        ROOT / "mkdocs.yml"
    ).read_bytes()


def test_every_page_of_the_nav_is_in_the_bundle() -> None:
    config = (DOCS_SOURCE_DIR / "mkdocs.yml").read_text(encoding="utf-8")
    pages = _NAV_PAGE.findall(config)

    assert len(pages) >= 20
    assert [p for p in pages if not (DOCS_SOURCE_DIR / "docs" / p).is_file()] == []


def test_no_page_has_an_include_left() -> None:
    """The example scripts, the changelog and the MJCF tags checklist are not in the bundle, so a page that still named one would build with the file missing."""
    left = [
        page.relative_to(DOCS_SOURCE_DIR).as_posix()
        for page in DOCS_SOURCE_DIR.rglob("*.md")
        if _INCLUDE.search(page.read_text(encoding="utf-8"))
    ]

    assert left == []


def test_a_page_holds_the_code_it_includes() -> None:
    """The generate guide includes sections of the Monte Carlo example, so its code has to be in the page, inside the code block that held the include."""
    page = DOCS_SOURCE_DIR / "docs" / "user-guides" / "workflow" / "generate-script.md"
    text = page.read_text(encoding="utf-8")

    assert "def generate(" in text
    assert "# --8<--" not in text


def test_the_changelog_page_holds_the_changelog() -> None:
    text = (DOCS_SOURCE_DIR / "docs" / "changelog.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    newest = next(line for line in changelog.splitlines() if line.startswith("## "))

    assert newest in text


@pytest.fixture
def tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, generator: ModuleType
) -> Path:
    """A small repo with a docs folder, and the generator pointed at it."""
    root = tmp_path / "repo"
    docs = root / "docs"
    (docs / "assets").mkdir(parents=True)
    (docs / "run").mkdir()
    (root / "mkdocs.yml").write_text(f"site_name: Test\ncopyright: {CURLY}\n")
    (docs / "index.md").write_text(f"It{CURLY}s a page\n")
    (docs / "example.py").write_text(f"x = 'it{CURLY}s'\n")
    (docs / "assets" / "logo.svg").write_text(f"<svg>{CURLY}</svg>\n")
    (docs / "assets" / "shot.jpg").write_bytes(b"\xff\xd8")
    (docs / "assets" / "anim.gif").write_bytes(b"GIF")
    (docs / "run" / ".gitignore").write_text("*\n")
    (docs / "run" / "report.md").write_text("output of a run\n")
    (docs / "run" / "script.py").write_text("print('run')\n")
    monkeypatch.setattr(generator, "ROOT", root)
    monkeypatch.setattr(generator, "DOCS_DIR", docs)
    monkeypatch.setattr(generator, "OUTPUT_DIR", root / "out")
    return root


def test_it_copies_pages_and_logos_and_leaves_the_images_and_scripts_out(
    generator: ModuleType, tree: Path
) -> None:
    out = tree / "out"

    assert sorted(p.relative_to(out).as_posix() for p in generator.sources()) == [
        "docs/assets/logo.svg",
        "docs/index.md",
        "mkdocs.yml",
    ]


def test_it_leaves_out_a_working_directory(generator: ModuleType, tree: Path) -> None:
    names = {p.name for p in generator.sources()}

    assert "report.md" not in names
    assert "script.py" not in names


def test_pages_get_the_punctuation_the_src_hook_would_give_them(
    generator: ModuleType, tree: Path
) -> None:
    """The `fix-smart-quotes` hook rewrites `.md` under `src/`, so the bundle holds the pages already rewritten, and so the code that was included in them. A file of another kind is copied as it is."""
    (tree / "docs" / "code.md").write_text('```python\n--8<-- "docs/example.py"\n```\n')
    generator.write()
    out = tree / "out"

    assert (out / "docs" / "index.md").read_text() == "It's a page\n"
    assert (out / "docs" / "code.md").read_text() == "```python\nx = 'it's'\n```\n"
    assert (out / "docs" / "assets" / "logo.svg").read_text() == f"<svg>{CURLY}</svg>\n"
    assert (out / "mkdocs.yml").read_text() == f"site_name: Test\ncopyright: {CURLY}\n"


def test_it_reports_a_stale_bundle_and_a_file_nothing_gives_any_more(
    generator: ModuleType, tree: Path
) -> None:
    generator.write()
    assert generator.stale() == []

    (tree / "docs" / "index.md").write_text("changed\n")
    (tree / "out" / "docs" / "old.md").write_text("gone from the docs\n")

    assert sorted(p.name for p in generator.stale()) == ["index.md", "old.md"]

    written, removed = generator.write()

    assert [p.name for p in written] == ["index.md"]
    assert [p.name for p in removed] == ["old.md"]
    assert generator.stale() == []


class TestIncludes:
    """What replaces an include line, on small files, so a change shows up here and not only as a different page. The docs site is the reference: its output for each of these is what is written."""

    @pytest.fixture
    def page(self, generator: ModuleType, tree: Path) -> Path:
        return tree / "docs" / "page.md"

    def test_a_section_of_a_file_is_dedented_and_reindented_where_it_was_included(
        self, generator: ModuleType, tree: Path
    ) -> None:
        (tree / "example.py").write_text(
            "def f():\n"
            "    # --8<-- [start:body]\n"
            "    x = 1\n"
            "    if x:\n"
            "        y = 2\n"
            "    # --8<-- [end:body]\n",
            encoding="utf-8",
        )

        text = generator.expand_includes('    --8<-- "example.py:body"\n')

        assert text == "    x = 1\n    if x:\n        y = 2\n"

    def test_a_whole_file_loses_its_section_markers(
        self, generator: ModuleType, tree: Path
    ) -> None:
        (tree / "all.py").write_text(
            "# --8<-- [start:a]\nx = 1\n# --8<-- [end:a]\ny = 2\n", encoding="utf-8"
        )

        assert generator.expand_includes('--8<-- "all.py"') == "x = 1\ny = 2"

    def test_markers_of_another_section_inside_a_section_are_dropped(
        self, generator: ModuleType, tree: Path
    ) -> None:
        (tree / "nest.py").write_text(
            "# --8<-- [start:outer]\na = 1\n# --8<-- [start:inner]\nb = 2\n# --8<-- [end:inner]\nc = 3\n# --8<-- [end:outer]\n",
            encoding="utf-8",
        )

        assert (
            generator.expand_includes('--8<-- "nest.py:outer"') == "a = 1\nb = 2\nc = 3"
        )

    def test_a_blank_line_at_the_end_of_a_section_is_kept(
        self, generator: ModuleType, tree: Path
    ) -> None:
        """The docs site keeps it, and a guide that puts two sections one under the other with a blank line between them shows two blank lines there (the PEP 8 gap before `if __name__`). Losing it changed the code on the page."""
        (tree / "gap.py").write_text(
            "# --8<-- [start:imports]\nimport os\n\n# --8<-- [end:imports]\n"
            "# --8<-- [start:main]\nrun()\n# --8<-- [end:main]\n",
            encoding="utf-8",
        )
        text = '--8<-- "gap.py:imports"\n\n--8<-- "gap.py:main"\n'

        assert generator.expand_includes(text) == "import os\n\n\nrun()\n"

    def test_an_include_inside_a_code_block_is_expanded(
        self, generator: ModuleType, tree: Path
    ) -> None:
        (tree / "x.py").write_text("x = 1\n", encoding="utf-8")

        text = generator.expand_includes('```python\n--8<-- "x.py"\n```\n')

        assert text == "```python\nx = 1\n```\n"

    def test_a_markdown_file_can_be_included_too(
        self, generator: ModuleType, tree: Path
    ) -> None:
        (tree / "CHANGELOG.md").write_text("# Changelog\n\n- A change\n")

        assert generator.expand_includes('--8<-- "CHANGELOG.md"\n') == (
            "# Changelog\n\n- A change\n"
        )

    def test_a_missing_file_or_section_is_an_error_not_an_empty_block(
        self, generator: ModuleType, tree: Path
    ) -> None:
        (tree / "there.py").write_text("x = 1\n", encoding="utf-8")

        with pytest.raises(generator.DocsSourceError, match="does not exist"):
            generator.expand_includes('--8<-- "gone.py"')
        with pytest.raises(generator.DocsSourceError, match='no section "nope"'):
            generator.expand_includes('--8<-- "there.py:nope"')

    def test_the_error_stops_the_script_with_a_message_and_a_failing_status(
        self,
        generator: ModuleType,
        tree: Path,
        page: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        page.write_text('--8<-- "gone.py"\n')

        assert generator.main([]) == 1
        assert generator.main(["--check"]) == 1
        assert "gone.py" in capsys.readouterr().out

    def test_a_sentence_that_mentions_an_include_is_not_one(
        self, generator: ModuleType, tree: Path
    ) -> None:
        text = 'Write `--8<-- "a.py"` to include it.\n'

        assert generator.expand_includes(text) == text

    def test_a_page_is_written_with_the_code_and_not_the_include(
        self, generator: ModuleType, tree: Path, page: Path
    ) -> None:
        (tree / "x.py").write_text("x = 1\n", encoding="utf-8")
        page.write_text('# Page\n\n```python\n--8<-- "x.py"\n```\n')

        generator.write()

        assert (tree / "out" / "docs" / "page.md").read_text() == (
            "# Page\n\n```python\nx = 1\n```\n"
        )
        assert not (tree / "out" / "x.py").exists()

    def test_a_change_to_an_included_file_makes_the_bundle_stale(
        self, generator: ModuleType, tree: Path, page: Path
    ) -> None:
        (tree / "x.py").write_text("x = 1\n", encoding="utf-8")
        page.write_text('--8<-- "x.py"\n')
        generator.write()
        assert generator.stale() == []

        (tree / "x.py").write_text("x = 2\n", encoding="utf-8")

        assert [p.name for p in generator.stale()] == ["page.md"]
