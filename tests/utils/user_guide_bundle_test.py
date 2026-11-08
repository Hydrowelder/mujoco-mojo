"""Tests for the user guides bundled in the package, which `scripts/gen_user_guide.py` writes as plain markdown."""

import importlib
import re
from pathlib import Path
from types import ModuleType

import pytest

import mujoco_mojo

ROOT = Path(__file__).parents[2]
SCRIPTS = ROOT / "scripts"
BUNDLE = Path(mujoco_mojo.__file__).parent / "user_guide"


@pytest.fixture
def generator(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The script that writes the bundle, which lives in `scripts/`."""
    monkeypatch.syspath_prepend(str(SCRIPTS))
    return importlib.import_module("gen_user_guide")


def bundled() -> list[Path]:
    return sorted(BUNDLE.rglob("*.md"))


def test_the_bundled_guides_are_current(generator: ModuleType) -> None:
    """The package ships these files, so each must match its guide. The `gen-user-guide` pre-commit hook rewrites them."""
    assert generator.stale() == [], (
        "a bundled guide is out of date. Run: python scripts/gen_user_guide.py"
    )


def test_every_guide_is_bundled_and_nothing_else(generator: ModuleType) -> None:
    wanted = {generator.output_path(source) for source in generator.sources()}

    assert set(bundled()) == wanted
    assert len(wanted) >= 20


def test_a_markdown_file_in_a_mojo_working_directory_is_not_a_guide(
    generator: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Running an example in the guides folder leaves a working directory there, with a report in it. Mojo writes a `.gitignore` of `*` into a working directory, so git ignores it whole: it is on the machine that ran it and not on any other, and bundling it made the check fail anywhere but there."""
    guides = tmp_path / "guides"

    def write(relative: str, text: str = "text\n") -> None:
        path = guides / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    write("intro.md")
    write("run/.gitignore", "*")
    write("run/MOJO_RUNTIME_REPORT.md")
    write("run/trials/trial_0/notes.md")
    write("shared/.gitignore", "*.pyc\n")
    write("shared/page.md")
    write("shared/keep.md")
    write("shared/out/.gitignore", "*\n")
    write("shared/out/report.md")
    # a `.gitignore` of `*` above the guides folder is not one of theirs
    (tmp_path / ".gitignore").write_text("*", encoding="utf-8")
    monkeypatch.setattr(generator, "SOURCE_DIR", guides)

    found = [
        path.relative_to(guides).as_posix()
        for path in generator.sources()
        if path.is_relative_to(guides)
    ]

    assert found == ["intro.md", "shared/keep.md", "shared/page.md"]


def test_rendering_is_deterministic(generator: ModuleType) -> None:
    """A guide that rendered differently from one run to the next would make the staleness check fail on every commit."""
    for source in generator.sources():
        assert generator.render(source) == generator.render(source)


def test_no_site_markup_is_left_for_a_plain_reader() -> None:
    """Read as plain text, an include line is not the code, an image is a file that does not ship, and a comment is a note for the maintainers."""
    for path in bundled():
        text = path.read_text(encoding="utf-8")
        where = path.relative_to(BUNDLE)

        assert "--8<--" not in text, f"{where} has an include left"
        assert not re.search(r"!\[[^\]]*\]\(", text), f"{where} has an image"
        assert not re.search(r"<(?:figure|figcaption|img)\b", text), (
            f"{where} has image HTML"
        )
        assert "<!--" not in text, f"{where} has an HTML comment"
        assert not re.search(r"\)\{[^}]*\}", text), f"{where} has link attributes"
        assert not re.search(r":(?:material|fontawesome|octicons)-[a-z0-9-]+:", text), (
            f"{where} has an icon code"
        )


def test_the_code_of_an_include_is_in_the_guide() -> None:
    """The generate guide includes sections of the Monte Carlo example, so its code has to be there."""
    text = (BUNDLE / "workflow" / "generate-script.md").read_text(encoding="utf-8")

    assert "def generate(" in text


def test_a_figure_keeps_its_caption() -> None:
    text = (BUNDLE / "features" / "dojo" / "mosaic.md").read_text(encoding="utf-8")

    assert "Figure: A preview of the **Mosaic** page" in text


def test_each_guide_opens_with_its_title() -> None:
    """The title is how a reader, and SensAI's table of contents, names the guide."""
    for path in bundled():
        first = path.read_text(encoding="utf-8").lstrip().splitlines()[0]

        assert first.startswith("# "), (
            f"{path.relative_to(BUNDLE)} starts with {first!r}"
        )


class TestRendering:
    """The rules of the generator on small inputs, so a change to one shows up here and not only as a diff of 23 guides."""

    def test_a_section_of_a_file_is_dedented_and_reindented_where_it_was_included(
        self, generator: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        example = tmp_path / "example.py"
        example.write_text(
            "def f():\n"
            "    # --8<-- [start:body]\n"
            "    x = 1\n"
            "    if x:\n"
            "        y = 2\n"
            "    # --8<-- [end:body]\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(generator, "ROOT", tmp_path)

        text = generator.expand_includes('    --8<-- "example.py:body"')

        assert text == "    x = 1\n    if x:\n        y = 2"

    def test_a_whole_file_loses_its_section_markers(
        self, generator: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "all.py").write_text(
            "# --8<-- [start:a]\nx = 1\n# --8<-- [end:a]\ny = 2\n", encoding="utf-8"
        )
        monkeypatch.setattr(generator, "ROOT", tmp_path)

        assert generator.expand_includes('--8<-- "all.py"') == "x = 1\ny = 2"

    def test_markers_of_another_section_inside_a_section_are_dropped(
        self, generator: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "nest.py").write_text(
            "# --8<-- [start:outer]\na = 1\n# --8<-- [start:inner]\nb = 2\n# --8<-- [end:inner]\nc = 3\n# --8<-- [end:outer]\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(generator, "ROOT", tmp_path)

        assert (
            generator.expand_includes('--8<-- "nest.py:outer"') == "a = 1\nb = 2\nc = 3"
        )

    def test_a_missing_file_or_section_is_an_error_not_an_empty_block(
        self, generator: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "there.py").write_text("x = 1\n", encoding="utf-8")
        monkeypatch.setattr(generator, "ROOT", tmp_path)

        with pytest.raises(generator.GuideError, match="does not exist"):
            generator.expand_includes('--8<-- "gone.py"')
        with pytest.raises(generator.GuideError, match='no section "nope"'):
            generator.expand_includes('--8<-- "there.py:nope"')

    def test_code_blocks_are_left_as_they_are(self, generator: ModuleType) -> None:
        text = "Prose <!-- note --> here.\n\n```html\n<!-- kept -->\n![not an image](x.png)\n```\n"

        assert (
            generator.clean(text)
            == "Prose  here.\n\n```html\n<!-- kept -->\n![not an image](x.png)\n```\n"
        )

    def test_a_multi_line_comment_goes_and_leaves_one_blank_line(
        self, generator: ModuleType
    ) -> None:
        text = "before\n\n<!-- one\ntwo -->\n\nafter\n"

        assert generator.clean(text) == "before\n\nafter\n"

    def test_a_figure_becomes_its_caption_with_inline_markup_as_markdown(
        self, generator: ModuleType
    ) -> None:
        text = (
            '    <figure markdown="span">\n'
            '        ![alt](./a.jpg){ width="50%" }\n'
            "        <figcaption>The <b>body</b> and <code>legs</code>.</figcaption>\n"
            "    </figure>\n"
        )

        assert generator.clean(text) == "    Figure: The **body** and `legs`.\n"

    def test_smart_punctuation_is_bundled_the_way_the_pre_commit_hook_writes_it(
        self, generator: ModuleType, tmp_path: Path
    ) -> None:
        """The hook rewrites these under `src/`, where the bundle is. A bundle that kept them would be rewritten by it and written back by the generator on every commit."""
        source = tmp_path / "g.md"
        source.write_text(
            "# G\n\nIt\u2019s a \u201cquote\u201d \u2013 and\u2026 done.\n",
            encoding="utf-8",
        )

        assert generator.render(source) == '# G\n\nIt\'s a "quote" - and... done.\n'

    def test_a_figure_without_a_caption_disappears(self, generator: ModuleType) -> None:
        text = "a\n\n<figure>\n![alt](./a.jpg)\n</figure>\n\nb\n"

        assert generator.clean(text) == "a\n\nb\n"

    def test_an_image_line_goes_and_an_inline_image_keeps_its_alt_text(
        self, generator: ModuleType
    ) -> None:
        text = "![Alone](a.png){ width=1 }\nSee ![the icon](b.png) here.\n"

        assert generator.clean(text) == "See the icon here.\n"

    def test_link_attributes_and_icon_codes_are_removed(
        self, generator: ModuleType
    ) -> None:
        text = "[Open :material-open-in-new:](https://x.test/a){ .md-button target=_blank }\n"

        assert generator.clean(text) == "[Open](https://x.test/a)\n"

    def test_runs_of_blank_lines_outside_code_become_one(
        self, generator: ModuleType
    ) -> None:
        text = "a\n\n\n\nb\n\n```\nx\n\n\ny\n```\n"

        assert generator.clean(text) == "a\n\nb\n\n```\nx\n\n\ny\n```\n"


class TestTheBundleOnASmallTree:
    """Writing the bundle, on a small tree made for it so each rule can be seen alone."""

    @pytest.fixture
    def tree(
        self, generator: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> Path:
        guides = tmp_path / "docs" / "user-guides"
        (guides / "workflow").mkdir(parents=True)
        (guides / "workflow" / "a.md").write_text("# A\n\nGuide a.\n", encoding="utf-8")
        (tmp_path / "docs" / "reference").mkdir(parents=True)
        cli = tmp_path / "docs" / "reference" / "cli.md"
        cli.write_text("# Commands\n\nThe commands.\n", encoding="utf-8")
        monkeypatch.setattr(generator, "ROOT", tmp_path)
        monkeypatch.setattr(generator, "SOURCE_DIR", guides)
        monkeypatch.setattr(generator, "OUTPUT_DIR", tmp_path / "bundle")
        monkeypatch.setattr(generator, "REFERENCE_PAGES", {cli: "reference/cli.md"})
        return tmp_path

    def test_a_page_from_the_reference_folder_is_bundled_with_the_guides(
        self, generator: ModuleType, tree: Path
    ) -> None:
        generator.write()

        assert (tree / "bundle" / "workflow" / "a.md").is_file()
        assert (tree / "bundle" / "reference" / "cli.md").read_text(
            encoding="utf-8"
        ) == ("# Commands\n\nThe commands.\n")

    def test_a_page_from_another_folder_is_not_removed_as_a_leftover(
        self, generator: ModuleType, tree: Path
    ) -> None:
        """It is not under `user-guides`, which an earlier clean-up took to mean no guide gives it, so it wrote the file and removed it in the same run."""
        written, removed = generator.write()

        assert removed == []
        assert (tree / "bundle" / "reference" / "cli.md").is_file()
        assert tree / "bundle" / "reference" / "cli.md" in written

    def test_writing_again_changes_nothing(
        self, generator: ModuleType, tree: Path
    ) -> None:
        generator.write()

        assert generator.write() == ([], [])
        assert generator.stale() == []

    def test_a_bundled_file_with_no_source_is_removed(
        self, generator: ModuleType, tree: Path
    ) -> None:
        generator.write()
        old = tree / "bundle" / "workflow" / "gone.md"
        old.write_text("# Gone\n", encoding="utf-8")

        assert generator.stale() == [old]
        written, removed = generator.write()

        assert removed == [old]
        assert written == []
        assert not old.exists()

    def test_a_changed_guide_is_written_again_and_only_that_one(
        self, generator: ModuleType, tree: Path
    ) -> None:
        generator.write()
        (tree / "docs" / "user-guides" / "workflow" / "a.md").write_text(
            "# A\n\nChanged.\n", encoding="utf-8"
        )

        written, removed = generator.write()

        assert written == [tree / "bundle" / "workflow" / "a.md"]
        assert removed == []

    def test_a_bundled_file_that_differs_is_stale(
        self, generator: ModuleType, tree: Path
    ) -> None:
        generator.write()
        path = tree / "bundle" / "reference" / "cli.md"
        path.write_text("edited by hand\n", encoding="utf-8")

        assert generator.stale() == [path]

    def test_the_sources_are_the_guides_then_the_reference_pages(
        self, generator: ModuleType, tree: Path
    ) -> None:
        assert [p.name for p in generator.sources()] == ["a.md", "cli.md"]


def test_the_bundle_has_nothing_the_pre_commit_hook_would_rewrite(
    generator: ModuleType,
) -> None:
    """The hook runs on everything under `src/`, the bundle included, so a file in it that the hook would change is a commit that never settles."""
    hook = importlib.import_module("fix_smart_quotes")
    for path in bundled():
        text = path.read_text(encoding="utf-8")
        for char in hook.REPLACEMENTS:
            assert char not in text, f"{path.relative_to(BUNDLE)} has U+{ord(char):04X}"
