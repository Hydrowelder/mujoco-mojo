"""Tests that the Dojo screenshots in the docs and the shots `scripts/gen_dojo_screenshots.py` takes name the same images, so a page cannot point at a picture nothing makes and a shot cannot be taken for a picture no page shows. The script needs Playwright (a development dependency, with a browser installed separately), so it is read as text here and never imported."""

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts" / "gen_dojo_screenshots.py"
DOCS = ROOT / "docs"

SHOT = re.compile(r'^@shot\(\s*"([\w-]+)"', re.MULTILINE)
IMAGE = re.compile(r"assets/user-guides/(light|dark)-([\w-]+)\.jpg")


def shots() -> set[str]:
    """The names of the shots the script takes."""
    return set(SHOT.findall(SCRIPT.read_text(encoding="utf-8")))


def images() -> dict[str, set[str]]:
    """Each themed image the docs pages show, as its name with the themes it is shown in."""
    found: dict[str, set[str]] = {}
    for page in DOCS.rglob("*.md"):
        for theme, name in IMAGE.findall(page.read_text(encoding="utf-8")):
            found.setdefault(name, set()).add(theme)
    return found


def test_the_script_takes_shots() -> None:
    assert shots()


def test_every_themed_image_in_the_docs_has_a_shot() -> None:
    """A page that shows `light-versus.jpg` needs the `versus` shot to make it."""
    missing = sorted(images().keys() - shots())

    assert not missing, f"no shot takes: {missing}"


def test_every_shot_is_shown_in_the_docs() -> None:
    """A shot nothing shows is a picture taken for no reason, and is slow to take."""
    unused = sorted(shots() - images().keys())

    assert not unused, f"no page shows: {unused}"


def test_every_image_is_shown_in_both_themes() -> None:
    """The script takes each shot in both themes, and a page shows the one that matches the reader's."""
    one_sided = sorted(name for name, themes in images().items() if len(themes) != 2)

    assert not one_sided, f"shown in one theme only: {one_sided}"
