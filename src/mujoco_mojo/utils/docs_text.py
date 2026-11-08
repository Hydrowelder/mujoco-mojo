"""
A page of the docs source as plain markdown, for a reader that is not the docs site (SensAI's guide agent reads the guides this way).

The pages in `DOCS_SOURCE_DIR` are written for the docs site, and read as plain text a few lines would mislead: the pictures are image files that do not ship, and some lines are site markup. This removes it:

- a `<figure>` keeps its caption, as a line starting `Figure:`, and loses the image; any other image line is removed
- HTML comments (notes for the people who maintain the docs) are removed
- attribute lists after a link (`{ .md-button }`) and icon codes (`:material-open-in-new:`) are removed

Code blocks are left alone. The code the guides show is already in them: `scripts/gen_docs_source.py` replaces each `--8<--` include with the lines it names when it writes the docs source. It uses only the standard library.
"""

from __future__ import annotations

import re
from pathlib import Path

__all__ = ["clean", "plain_text"]

_FENCE = re.compile(r"^\s*(```|~~~)")
_FIGURE_OPEN = re.compile(r"^(?P<indent>\s*)<figure\b[^>]*>\s*$")
_FIGURE_CLOSE = re.compile(r"^\s*</figure>\s*$")
_CAPTION = re.compile(r"<figcaption>(?P<text>.*?)</figcaption>", re.DOTALL)
_IMAGE_LINE = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)(?:\{[^}]*\})?\s*$")
_IMAGE_INLINE = re.compile(r"!\[(?P<alt>[^\]]*)\]\([^)]*\)(?:\{[^}]*\})?")
_LINK_ATTRS = re.compile(r"(\]\([^)]*\))\{[^}]*\}")
_ICON = re.compile(r"\s*:(?:material|fontawesome|octicons|simple)-[a-z0-9-]+:")


def _caption_text(html: str) -> str:
    """A figure caption as markdown: the few inline tags the guides use become their markdown, any others are dropped, and the lines become one."""
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", html, flags=re.DOTALL)
    text = re.sub(r"<(?:i|em)>(.*?)</(?:i|em)>", r"*\1*", text, flags=re.DOTALL)
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    return " ".join(text.split())


def _clean_prose(lines: list[str]) -> list[str]:
    """The lines outside code blocks with the site markup taken out: comments, figures, images, link attributes and icons."""
    text = "\n".join(lines)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    out: list[str] = []
    in_figure: list[str] | None = None
    indent = ""
    # split, not splitlines: a blank line at the end of the lines (just before a code block) has to survive
    for line in text.split("\n"):
        if in_figure is not None:
            if _FIGURE_CLOSE.match(line):
                caption = _CAPTION.search("\n".join(in_figure))
                if caption is not None:
                    out.append(f"{indent}Figure: {_caption_text(caption['text'])}")
                in_figure = None
            else:
                in_figure.append(line)
            continue
        opened = _FIGURE_OPEN.match(line)
        if opened is not None:
            in_figure, indent = [], opened["indent"]
            continue
        if _IMAGE_LINE.match(line):
            continue
        line = _IMAGE_INLINE.sub(lambda m: m["alt"], line)
        line = _LINK_ATTRS.sub(r"\1", line)
        out.append(_ICON.sub("", line))
    return out


def clean(text: str) -> str:
    """The text with the site markup removed outside its code blocks, and the blank lines left behind collapsed."""
    prose: list[str] = []
    result: list[str] = []
    in_code = False

    def flush() -> None:
        result.extend(_clean_prose(prose))
        prose.clear()

    for line in text.splitlines():
        if _FENCE.match(line):
            if not in_code:
                flush()
            result.append(line)
            in_code = not in_code
        elif in_code:
            result.append(line)
        else:
            prose.append(line)
    flush()

    # a removed comment or image leaves its blank lines behind: keep one, outside code
    collapsed: list[str] = []
    in_code = False
    for line in result:
        if _FENCE.match(line):
            in_code = not in_code
        if not in_code and not line.strip() and collapsed and not collapsed[-1].strip():
            continue
        collapsed.append(line.rstrip() if not in_code else line)
    return "\n".join(collapsed).strip("\n") + "\n"


def plain_text(page: Path) -> str:
    """The page at `page` as plain markdown."""
    return clean(page.read_text(encoding="utf-8"))
