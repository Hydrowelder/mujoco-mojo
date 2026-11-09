"""Tests for reading a page of the docs source as plain markdown, which is how SensAI's docs agent reads the docs. The code of the guides is already in the pages (the docs source generator fills in each include), so this only removes the site's markup."""

import re
from pathlib import Path

from mujoco_mojo.meta import DOCS_SOURCE_DIR
from mujoco_mojo.utils.docs_text import clean, plain_text

DOCS = DOCS_SOURCE_DIR / "docs"

# an include left as written: a line that starts with it. a sentence that mentions one, as the help of `docs path` does, is prose
_INCLUDE_LINE = re.compile(r'^\s*--8<--\s+"', re.MULTILINE)


def docs_pages() -> list[Path]:
    """The pages SensAI reads: every page of the docs source."""
    return sorted(DOCS.rglob("*.md"))


class TestCleaning:
    """The rules on small inputs, so a change to one shows up here and not only as a different answer from SensAI."""

    def test_code_blocks_are_left_as_they_are(self) -> None:
        text = "Prose <!-- note --> here.\n\n```html\n<!-- kept -->\n![not an image](x.png)\n```\n"

        assert (
            clean(text)
            == "Prose  here.\n\n```html\n<!-- kept -->\n![not an image](x.png)\n```\n"
        )

    def test_a_multi_line_comment_goes_and_leaves_one_blank_line(self) -> None:
        assert clean("before\n\n<!-- one\ntwo -->\n\nafter\n") == "before\n\nafter\n"

    def test_a_figure_becomes_its_caption_with_inline_markup_as_markdown(self) -> None:
        text = (
            '    <figure markdown="span">\n'
            '        ![alt](./a.jpg){ width="50%" }\n'
            "        <figcaption>The <b>body</b> and <code>legs</code>.</figcaption>\n"
            "    </figure>\n"
        )

        assert clean(text) == "    Figure: The **body** and `legs`.\n"

    def test_a_figure_without_a_caption_disappears(self) -> None:
        assert clean("a\n\n<figure>\n![alt](./a.jpg)\n</figure>\n\nb\n") == "a\n\nb\n"

    def test_an_image_line_goes_and_an_inline_image_keeps_its_alt_text(self) -> None:
        text = "![Alone](a.png){ width=1 }\nSee ![the icon](b.png) here.\n"

        assert clean(text) == "See the icon here.\n"

    def test_link_attributes_and_icon_codes_are_removed(self) -> None:
        text = "[Open :material-open-in-new:](https://x.test/a){ .md-button target=_blank }\n"

        assert clean(text) == "[Open](https://x.test/a)\n"

    def test_front_matter_is_removed_from_the_top_of_a_page_only(self) -> None:
        assert clean("---\nhide:\n  - navigation\n---\n# Home\n") == "# Home\n"
        assert clean("a\n\n---\n\nb\n") == "a\n\n---\n\nb\n"

    def test_style_and_script_blocks_are_removed(self) -> None:
        text = (
            "a\n<style>\n.x { color: red; }\n</style>\nb\n<script>run()</script>\nc\n"
        )

        assert clean(text) == "a\n\nb\n\nc\n"

    def test_a_row_of_linked_images_is_removed(self) -> None:
        badges = (
            '<p align="center">\n'
            '  <a href="https://x.test" class="badge-link">\n'
            '    <img src="https://x.test/a.svg" alt="A">\n'
            "  </a>\n"
            '  <a href="https://y.test">\n'
            '    <img src="https://y.test/b.svg" alt="B">\n'
            "  </a>\n"
            "</p>\n"
        )

        assert clean(f"# Home\n\n{badges}\nText.\n") == "# Home\n\nText.\n"

    def test_a_paragraph_with_words_in_it_is_not_a_badge_row(self) -> None:
        text = '<p align="center">Read <a href="https://x.test">this</a></p>\n'

        assert clean(text) == text

    def test_runs_of_blank_lines_outside_code_become_one(self) -> None:
        text = "a\n\n\n\nb\n\n```\nx\n\n\ny\n```\n"

        assert clean(text) == "a\n\nb\n\n```\nx\n\n\ny\n```\n"


class TestTheRealDocs:
    """The docs in the package, so a page that a rule cannot read shows up here and not as a bad answer."""

    def test_there_are_pages_to_read(self) -> None:
        assert len(docs_pages()) >= 20
        assert all(page.is_file() for page in docs_pages())

    def test_no_page_has_an_include_left(self) -> None:
        """An include that does not resolve, because a file or a section was renamed, would be read as text."""
        for page in docs_pages():
            text = plain_text(page)

            assert not _INCLUDE_LINE.search(text), page.relative_to(DOCS)

    def test_no_site_markup_is_left_for_a_plain_reader(self) -> None:
        """Read as plain text, an image is a file that does not ship and a comment is a note for the maintainers."""
        for page in docs_pages():
            text = plain_text(page)
            where = page.relative_to(DOCS)

            assert not re.search(r"!\[[^\]]*\]\(", text), f"{where} has an image"
            assert not re.search(r"<(?:figure|figcaption|img)\b", text), (
                f"{where} has image HTML"
            )
            assert "<!--" not in text, f"{where} has an HTML comment"
            assert not re.search(r"\)\{[^}]*\}", text), f"{where} has link attributes"
            assert not re.search(
                r":(?:material|fontawesome|octicons)-[a-z0-9-]+:", text
            ), f"{where} has an icon code"

    def test_the_code_of_an_include_is_in_the_guide(self) -> None:
        """The generate guide includes sections of the Monte Carlo example, so its code has to be there."""
        page = DOCS / "user-guides" / "workflow" / "generate-script.md"

        assert "def generate(" in plain_text(page)

    def test_a_figure_keeps_its_caption(self) -> None:
        page = DOCS / "user-guides" / "features" / "dojo" / "mosaic.md"

        assert "Figure: A preview of the **Mosaic** page" in plain_text(page)

    def test_each_page_opens_with_its_title(self) -> None:
        """The title is how a reader, and SensAI's table of contents, names the page. `about.md` is a short note with no heading."""
        for page in docs_pages():
            if page.name == "about.md":
                continue
            first = plain_text(page).lstrip().splitlines()[0]

            assert first.startswith("# "), (
                f"{page.relative_to(DOCS)} starts with {first!r}"
            )
