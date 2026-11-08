"""
Writes the user guides as plain markdown into `src/mujoco_mojo/user_guide/`, so they ship inside the package.

The guides in `docs/user-guides/` are written for the docs site, and read as plain text they would mislead a reader that is not that site: the code blocks are `--8<--` includes of the example scripts, the pictures are image files that do not ship, and a few lines are site markup. This script writes a copy a person, a program or an AI assistant (SensAI reads it) can read as it stands:

- each `--8<-- "file.py:name"` line is replaced by the lines of that section of the file, and `--8<-- "file.py"` by the whole file, as the docs site does (a section is dedented, section markers are dropped)
- a `<figure>` keeps its caption, as a line starting `Figure:`, and loses the image; any other image line is removed
- HTML comments (notes for the people who maintain the docs) are removed
- attribute lists after a link (`{ .md-button }`) and icon codes (`:material-open-in-new:`) are removed

Code blocks are left alone apart from the includes. The output mirrors the folder layout of `docs/user-guides/`, one file per guide, and the generated command line reference (`docs/reference/cli.md`) is bundled with them as `reference/cli.md`.

Usage:
    python scripts/gen_user_guide.py           # rewrite the bundled guides
    python scripts/gen_user_guide.py --check   # exit 1 if a bundled guide is out of date, changing nothing

The pre-commit hook `gen-user-guide` runs it when a guide or an example script changes, and a test fails if a bundled guide is stale. It uses only the standard library.
"""

from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).parents[1]
SOURCE_DIR = ROOT / "docs" / "user-guides"
OUTPUT_DIR = ROOT / "src" / "mujoco_mojo" / "user_guide"

# pages from outside `docs/user-guides/` that are bundled with the guides, each with the path it is bundled under. a path starting `reference/` is a page of the docs site's Reference section, which SensAI links to there and not under user-guides
REFERENCE_PAGES: dict[Path, str] = {
    ROOT / "docs" / "reference" / "cli.md": "reference/cli.md",
}

# `--8<-- "path"` or `--8<-- "path:section"`, alone on a line (the docs site's snippet include)
_INCLUDE = re.compile(
    r'^(?P<indent>\s*)--8<--\s+"(?P<path>[^":]+)(?::(?P<section>[^"]+))?"\s*$'
)
# `# --8<-- [start:name]` and `# --8<-- [end:name]` in an example script
_MARKER = re.compile(
    r"^\s*(?:#\s*)?--8<--\s*\[(?P<kind>start|end):(?P<name>[^\]]+)\]\s*$"
)
_FENCE = re.compile(r"^\s*(```|~~~)")
_FIGURE_OPEN = re.compile(r"^(?P<indent>\s*)<figure\b[^>]*>\s*$")
_FIGURE_CLOSE = re.compile(r"^\s*</figure>\s*$")
_CAPTION = re.compile(r"<figcaption>(?P<text>.*?)</figcaption>", re.DOTALL)
_IMAGE_LINE = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)(?:\{[^}]*\})?\s*$")
_IMAGE_INLINE = re.compile(r"!\[(?P<alt>[^\]]*)\]\([^)]*\)(?:\{[^}]*\})?")
_LINK_ATTRS = re.compile(r"(\]\([^)]*\))\{[^}]*\}")
_ICON = re.compile(r"\s*:(?:material|fontawesome|octicons|simple)-[a-z0-9-]+:")


class GuideError(Exception):
    """A guide that cannot be written as plain markdown, such as an include of a file or section that is not there."""


def sources() -> list[Path]:
    """Every guide, in a fixed order, then the reference pages bundled with them."""
    return [*sorted(SOURCE_DIR.rglob("*.md")), *REFERENCE_PAGES]


def output_path(source: Path) -> Path:
    """Where the bundled copy of the guide `source` is written."""
    if source in REFERENCE_PAGES:
        return OUTPUT_DIR / REFERENCE_PAGES[source]
    return OUTPUT_DIR / source.relative_to(SOURCE_DIR)


def _section_lines(path: Path, section: str | None) -> list[str]:
    """The lines an include of `path` brings in: the whole file, or the lines between a section's markers. Marker lines never come through."""
    if not path.is_file():
        raise GuideError(f"The include {path.relative_to(ROOT)} does not exist.")
    lines = path.read_text(encoding="utf-8").splitlines()
    if section is None:
        return [line for line in lines if not _MARKER.match(line)]
    inside = False
    found = False
    taken: list[str] = []
    for line in lines:
        marker = _MARKER.match(line)
        if marker and marker["name"] == section:
            inside = marker["kind"] == "start"
            found = found or inside
            continue
        if marker or not inside:
            continue
        taken.append(line)
    if not found:
        raise GuideError(f'{path.relative_to(ROOT)} has no section "{section}".')
    return textwrap.dedent("\n".join(taken)).splitlines()


def expand_includes(text: str) -> str:
    """The text with each include line replaced by the lines it names, indented as the include was."""
    out: list[str] = []
    for line in text.splitlines():
        include = _INCLUDE.match(line)
        if include is None:
            out.append(line)
            continue
        lines = _section_lines(ROOT / include["path"], include["section"])
        indent = include["indent"]
        out += [f"{indent}{body}" if body.strip() else "" for body in lines]
    return "\n".join(out)


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


def render(source: Path) -> str:
    """The bundled text of the guide `source`."""
    return clean(expand_includes(source.read_text(encoding="utf-8")))


def _wanted() -> dict[Path, str]:
    """Each file the bundle should hold, with its text."""
    return {output_path(source): render(source) for source in sources()}


def _out_of_date(wanted: dict[Path, str]) -> list[Path]:
    return [
        path
        for path, text in wanted.items()
        if not path.is_file() or path.read_text(encoding="utf-8") != text
    ]


def _leftovers(wanted: dict[Path, str]) -> list[Path]:
    """Bundled files that no guide gives any more."""
    return [p for p in sorted(OUTPUT_DIR.rglob("*.md")) if p not in wanted]


def stale() -> list[Path]:
    """The bundled files that are missing or differ from what the guides give, and the ones no guide gives any more."""
    wanted = _wanted()
    return _out_of_date(wanted) + _leftovers(wanted)


def write() -> tuple[list[Path], list[Path]]:
    """Writes the bundled guides that changed and removes the ones no guide gives any more. Returns the files it wrote and the files it removed."""
    wanted = _wanted()
    written = _out_of_date(wanted)
    for path in written:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(wanted[path], encoding="utf-8", newline="\n")
    removed = _leftovers(wanted)
    for path in removed:
        path.unlink()
    return written, removed


def main(argv: list[str]) -> int:
    if "--check" in argv:
        out_of_date = stale()
        for path in out_of_date:
            print(f"out of date: {path.relative_to(ROOT)}")
        if out_of_date:
            print("Run: python scripts/gen_user_guide.py")
        return 1 if out_of_date else 0
    written, removed = write()
    for path in written:
        print(f"Written -> {path.relative_to(ROOT)}")
    for path in removed:
        print(f"Removed -> {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
