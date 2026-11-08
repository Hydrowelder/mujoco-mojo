"""
Writes the source of the documentation site into `src/mujoco_mojo/docs_source/`, so the package can build the site itself (`mujoco-mojo docs build`) and ship the pages for people, programs and SensAI to read.

The site is built from `mkdocs.yml` and the pages in `docs/`, none of which ship in a wheel. This script copies what the build needs and leaves the weight behind:

- `mkdocs.yml` is copied as it is
- everything in `docs/` with an extension in `KEEP` is copied (pages, the site's scripts and styles, the SVG logos), and every other file is left out: the screenshots, animations and meshes are several megabytes and are what makes up almost all of `docs/`
- in each page, each `--8<-- "file.py:name"` line is replaced by the lines of that section of the file, and `--8<-- "file.py"` by the whole file, as the docs site does when it builds (a section is dedented, section markers are dropped). So the pages hold their code, and the example scripts, the changelog and the MJCF tags checklist that they include do not have to ship. A page includes a file by a path from the repo root, and a path that is not there is an error here, not an empty code block.

Nothing else in a page is rewritten here, because the build needs it as written (the figures, the attribute lists, the icons). `mujoco-mojo docs build` points a link at a file that was left out (an image) to the same file on GitHub when it builds, since that needs the version, and SensAI's reader strips the markup that a plain-text reader cannot use (`utils/docs_text.py`).

Anything inside a Mojo working directory (a folder whose `.gitignore` is just `*`, as running an example in the guides folder leaves behind) is output of a run and not a page, so it is skipped. A copied `.md` has the characters the `fix-smart-quotes` hook rewrites already rewritten, since that hook runs over `src/` and would otherwise change the bundle after every commit.

Usage:
    python scripts/gen_docs_source.py           # rewrite the bundled source
    python scripts/gen_docs_source.py --check   # exit 1 if the bundled source is out of date, changing nothing

The pre-commit hook `gen-docs-source` runs it when a page, an example script, `mkdocs.yml` or the changelog changes, and a test fails if the bundle is stale. It uses only the standard library.
"""

from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

# the characters the `fix-smart-quotes` hook rewrites under src/, where the bundle is
from fix_smart_quotes import REPLACEMENTS as _SMART_PUNCTUATION

ROOT = Path(__file__).parents[1]
DOCS_DIR = ROOT / "docs"
OUTPUT_DIR = ROOT / "src" / "mujoco_mojo" / "docs_source"

# files outside `docs/` that the build needs, as paths from the repo root and from the bundle
ROOT_FILES: tuple[str, ...] = ("mkdocs.yml",)

# the extensions copied from `docs/`. an allowlist, so a new kind of heavy file (a video, a mesh) stays out without anyone remembering to exclude it. the example scripts are not here: a page holds the part of one that it includes
KEEP: frozenset[str] = frozenset({".md", ".js", ".css", ".svg"})

# `--8<-- "path"` or `--8<-- "path:section"`, alone on a line (the docs site's snippet include)
_INCLUDE = re.compile(
    r'^(?P<indent>\s*)--8<--\s+"(?P<path>[^":]+)(?::(?P<section>[^"]+))?"\s*$'
)
# `# --8<-- [start:name]` and `# --8<-- [end:name]` in an example script
_MARKER = re.compile(
    r"^\s*(?:#\s*)?--8<--\s*\[(?P<kind>start|end):(?P<name>[^\]]+)\]\s*$"
)


class DocsSourceError(Exception):
    """A page that cannot be written, such as an include of a file or section that is not there."""


def in_working_directory(path: Path) -> bool:
    """Whether `path` is inside a Mojo working directory, which is output of a run and not part of the docs. Mojo writes a `.gitignore` holding just `*` into every working directory it makes, so a folder with one is ignored by git whole and exists only on the machine that ran it."""
    for folder in path.parents:
        if folder == DOCS_DIR:
            return False
        marker = folder / ".gitignore"
        if marker.is_file() and marker.read_text(encoding="utf-8").strip() == "*":
            return True
    return False


def sources() -> dict[Path, Path]:
    """Every file the bundle holds, as its path in the bundle mapped to the file it is made from, in a fixed order."""
    found: dict[Path, Path] = {}
    for name in ROOT_FILES:
        found[OUTPUT_DIR / name] = ROOT / name
    for path in sorted(DOCS_DIR.rglob("*")):
        if path.suffix not in KEEP or not path.is_file():
            continue
        if in_working_directory(path):
            continue
        found[OUTPUT_DIR / path.relative_to(ROOT)] = path
    return found


def _section_lines(path: Path, section: str | None) -> list[str]:
    """The lines an include of `path` brings in: the whole file, or the lines between a section's markers. Marker lines never come through."""
    if not path.is_file():
        raise DocsSourceError(f"The include {path.relative_to(ROOT)} does not exist.")
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
        raise DocsSourceError(f'{path.relative_to(ROOT)} has no section "{section}".')
    # split on newlines and not `splitlines()`, which would drop a blank line at the end of the section (just before its end marker), as the docs site does not
    return textwrap.dedent("\n".join(taken)).split("\n") if taken else []


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
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def plain_punctuation(text: str) -> str:
    """The text with each character the `fix-smart-quotes` hook rewrites already written the way it writes it (a curly quote as a straight one, an ellipsis as three dots)."""
    for old, new in _SMART_PUNCTUATION.items():
        text = text.replace(old, new)
    return text


def render(source: Path) -> bytes:
    """The bytes the bundled copy of `source` holds."""
    if source.suffix != ".md":
        return source.read_bytes()
    text = expand_includes(source.read_text(encoding="utf-8"))
    return plain_punctuation(text).encode("utf-8")


def _wanted() -> dict[Path, bytes]:
    """Each file the bundle should hold, with its content."""
    return {out: render(source) for out, source in sources().items()}


def _out_of_date(wanted: dict[Path, bytes]) -> list[Path]:
    return [
        path
        for path, data in wanted.items()
        if not path.is_file() or path.read_bytes() != data
    ]


def _leftovers(wanted: dict[Path, bytes]) -> list[Path]:
    """Bundled files that nothing gives any more."""
    if not OUTPUT_DIR.is_dir():
        return []
    return [
        p
        for p in sorted(OUTPUT_DIR.rglob("*"))
        if p.is_file() and p not in wanted and "__pycache__" not in p.parts
    ]


def stale() -> list[Path]:
    """The bundled files that are missing or differ from their source, and the ones nothing gives any more."""
    wanted = _wanted()
    return _out_of_date(wanted) + _leftovers(wanted)


def write() -> tuple[list[Path], list[Path]]:
    """Writes the bundled files that changed and removes the ones nothing gives any more. Returns the files it wrote and the files it removed."""
    wanted = _wanted()
    written = _out_of_date(wanted)
    for path in written:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(wanted[path])
    removed = _leftovers(wanted)
    for path in removed:
        path.unlink()
    # a folder every file of which was removed is not left behind
    if OUTPUT_DIR.is_dir():
        for folder in sorted(OUTPUT_DIR.rglob("*"), reverse=True):
            if folder.is_dir() and not any(folder.iterdir()):
                folder.rmdir()
    return written, removed


def main(argv: list[str]) -> int:
    try:
        if "--check" in argv:
            out_of_date = stale()
            for path in out_of_date:
                print(f"out of date: {path.relative_to(ROOT)}")
            if out_of_date:
                print("Run: python scripts/gen_docs_source.py")
            return 1 if out_of_date else 0
        written, removed = write()
    except DocsSourceError as error:
        print(f"error: {error}")
        return 1
    for path in written:
        print(f"Written -> {path.relative_to(ROOT)}")
    for path in removed:
        print(f"Removed -> {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
