"""
Builds the documentation site from the source that ships in the package (`DOCS_SOURCE_DIR`), keeps it under `~/.mujoco-mojo/docs/v<version>/`, and serves it.

Building needs the `docs` extra (Zensical and the API reference plugins). Serving does not: it is a static folder behind the web server that Mojo already has, so a version that was built once can be served without those packages.

The bundled source has no images (see `scripts/gen_docs_source.py`), so the build points every link to a file that is not there at the same file on GitHub, at the tag of the version being built.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from mujoco_mojo.__about__ import __url__
from mujoco_mojo.meta import DOCS_SOURCE_DIR, MUJOCO_MOJO_DIR

# the modules the build needs, from the `docs` extra, each with the package it is in. Zensical writes the site and hands the API reference to mkdocstrings and its Python handler, and stops with an error without either
DOCS_EXTRA_MODULES: dict[str, str] = {
    "zensical": "zensical",
    "mkdocstrings": "mkdocstrings",
    "mkdocstrings_handlers": "mkdocstrings-python",
}

# where the repo's files can be read from over HTTP, as `<base>/<ref>/<path>`
RAW_BASE_URL = __url__.replace(
    "https://github.com/", "https://raw.githubusercontent.com/"
)

# how many lines of a failed build's output the error carries
ERROR_TAIL_LINES = 30

# the two values in `mkdocs.yml` that name a path in the repo, which is not where the installed package is
_MODULES_SETTING = "modules: [src/mujoco_mojo]"
_PATHS_SETTING = "paths: [src]"

# the `watch:` list, folders of the repo that a live preview reloads on. a build watches nothing, and the builder refuses a folder that is not there (`src`)
_WATCH_SETTING = re.compile(r"^watch:[ \t]*\n(?:[ \t]+-[^\n]*\n?)+", re.MULTILINE)

# the address the online docs are published at. the site is served from `/` here, and the 404 page is the one page that links its styles and scripts by absolute path (from this address' path, `/mujoco-mojo/`), which are not found at that path
_SITE_URL_SETTING = re.compile(r"^site_url:.*$", re.MULTILINE)
_LOCAL_SITE_URL = "http://localhost/"

# an image in markdown (`![alt](url "title")`) and in HTML (`<img src="url">`)
_MD_IMAGE = re.compile(r"(?P<head>!\[[^\]]*\]\()(?P<url>[^)\s]+)")
_HTML_IMAGE = re.compile(r"""(?P<head><img\b[^>]*?\bsrc=["'])(?P<url>[^"']+)""")
_FENCE = re.compile(r"^\s*(```|~~~)")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


class DocsBuildError(RuntimeError):
    """The docs site could not be built. The message says why, including the end of the builder's output when it failed."""


def docs_site_dir(version: str) -> Path:
    """The folder the built site of `version` is kept in."""
    return MUJOCO_MOJO_DIR / "docs" / f"v{version}"


def is_built(site_dir: Path) -> bool:
    """Whether `site_dir` holds a built site."""
    return (site_dir / "index.html").is_file()


def _version_key(version: str) -> list[tuple[int, int | str]]:
    """A sort key that puts `2.9.0` before `2.10.0`: the runs of digits in a version compare as numbers and the rest as text."""
    return [
        (0, int(part)) if part.isdigit() else (1, part)
        for part in re.split(r"(\d+)", version)
        if part
    ]


def built_versions() -> list[str]:
    """The versions that have a built site, in version order, oldest first."""
    root = MUJOCO_MOJO_DIR / "docs"
    if not root.is_dir():
        return []
    return sorted(
        (
            folder.name.removeprefix("v")
            for folder in root.iterdir()
            if folder.name.startswith("v") and is_built(folder)
        ),
        key=_version_key,
    )


def github_ref(version: str) -> str:
    """The git ref the files of `version` are at: its release tag, or `master` for a version that has no tag (a development build, or the fallback version of a package that is not installed)."""
    if ".dev" in version or "+" in version or version.startswith("0.0.0"):
        return "master"
    return f"v{version}"


def require_docs_extra() -> None:
    """Raises `ModuleNotFoundError`, with how to install them, if a package the build needs is missing."""
    missing = [
        package
        for module, package in DOCS_EXTRA_MODULES.items()
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        raise ModuleNotFoundError(
            f"Building the docs needs the `docs` extra (missing: {', '.join(missing)}). "
            "Install with `uv add mujoco-mojo[docs]` or `pip install mujoco-mojo[docs]`"
        )


def _github_url(page: Path, url: str, docs_dir: Path, ref: str) -> str | None:
    """The GitHub address of the file `url` names on `page`, or `None` when `url` is to be left as it is: it is not relative, it is a page, it is not a file, or the file is there."""
    cut = min((i for i in (url.find("#"), url.find("?")) if i != -1), default=len(url))
    path, suffix = url[:cut], url[cut:]
    if not path or path.startswith("/") or _SCHEME.match(path):
        return None
    if Path(path).suffix in ("", ".md"):
        return None
    target = (page.parent / path).resolve()
    if target.exists() or not target.is_relative_to(docs_dir.resolve()):
        return None
    relative = target.relative_to(docs_dir.resolve()).as_posix()
    return f"{RAW_BASE_URL}/{ref}/docs/{quote(relative)}{suffix}"


def link_missing_assets(docs_dir: Path, ref: str) -> int:
    """
    Points each image in the pages of `docs_dir` that is not there at the same file on GitHub at `ref`, keeping the part after the file name (`#only-dark`). Anything inside a code block is left alone. Returns how many links it changed.

    This rule, a link to a file that is missing, is the whole of it: a build from a checkout that has the images changes nothing, and nothing has to list what the bundle leaves out.
    """
    changed = 0

    def rewriter(page: Path) -> Callable[[re.Match[str]], str]:
        def swap(match: re.Match[str]) -> str:
            nonlocal changed
            head: str = match["head"]
            url = _github_url(page, match["url"], docs_dir, ref)
            if url is None:
                return match.group(0)
            changed += 1
            return head + url

        return swap

    for page in sorted(docs_dir.rglob("*.md")):
        swap = rewriter(page)
        original = page.read_text(encoding="utf-8")
        in_fence = False
        lines: list[str] = []
        for line in original.splitlines(keepends=True):
            if _FENCE.match(line):
                in_fence = not in_fence
            elif not in_fence:
                line = _HTML_IMAGE.sub(swap, _MD_IMAGE.sub(swap, line))
            lines.append(line)
        text = "".join(lines)
        if text != original:
            page.write_text(text, encoding="utf-8", newline="")
    return changed


def patch_config(config: Path, package_dir: Path) -> None:
    """Points the two paths in `config` (`mkdocs.yml`) that name the package's source in the repo, the one the API reference is written from and the one the docstrings are read from, at the installed package at `package_dir`, removes the `watch:` list, and makes the site's address a local one. A text edit and not a YAML round trip, since the file has `!!python/name:` tags."""
    text = config.read_text(encoding="utf-8")
    for setting in (_MODULES_SETTING, _PATHS_SETTING):
        if setting not in text:
            raise DocsBuildError(
                f"The bundled mkdocs.yml has no `{setting}` line, so the build cannot find the package's source. Update `patch_config` in mujoco_mojo/utils/docs_site.py to match it."
            )
    text = text.replace(
        _MODULES_SETTING, f"modules: [{json.dumps(package_dir.as_posix())}]"
    )
    text = text.replace(
        _PATHS_SETTING, f"paths: [{json.dumps(package_dir.parent.as_posix())}]"
    )
    text = _WATCH_SETTING.sub("", text)
    text = _SITE_URL_SETTING.sub(f"site_url: {_LOCAL_SITE_URL}", text)
    config.write_text(text, encoding="utf-8", newline="")


def _copy_source(source_dir: Path, stage: Path) -> None:
    """Copies the files of `source_dir` into `stage`. The contents only, not the permissions: an install can be read-only (a package store), and the copy has to be written to and removed."""
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        out = stage / path.relative_to(source_dir)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, out)


def build_docs(
    version: str,
    *,
    rebuild: bool = False,
    source_dir: Path = DOCS_SOURCE_DIR,
    package_dir: Path | None = None,
) -> Path:
    """
    Builds the docs site of `version` and returns its folder (`docs_site_dir`). A site that is already built is returned as it is unless `rebuild` is set.

    The build runs in a scratch copy of the bundled source beside the result, since the builder writes next to its config and wants its output folder inside the config's folder, and the bundle is in the install, which may be read-only. The scratch copy is removed whether the build works or not, and the site only appears in its place once it is whole, so a failed build leaves nothing behind. `package_dir` is the package the API reference is written from (the installed one).
    """
    require_docs_extra()
    target = docs_site_dir(version)
    if is_built(target) and not rebuild:
        return target
    if package_dir is None:
        package_dir = Path(__file__).parents[1]

    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".build-v{version}-", dir=target.parent))
    try:
        _copy_source(source_dir, stage)
        link_missing_assets(stage / "docs", github_ref(version))
        patch_config(stage / "mkdocs.yml", package_dir)
        result = subprocess.run(
            [sys.executable, "-m", "zensical", "build", "--clean", "-f", "mkdocs.yml"],
            cwd=stage,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONUTF8": "1", "NO_COLOR": "1"},
        )
        if result.returncode != 0:
            output = (result.stdout + result.stderr).strip().splitlines()
            raise DocsBuildError(
                "The docs build failed:\n" + "\n".join(output[-ERROR_TAIL_LINES:])
            )
        if not is_built(stage / "site"):
            raise DocsBuildError("The docs build finished but made no site.")
        if target.exists():
            shutil.rmtree(target)
        os.replace(stage / "site", target)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return target


def docs_app_for(site_dir: Path) -> Starlette:
    """The web app that serves the built site in `site_dir`: `index.html` for a folder, a redirect to the folder's trailing slash, and the site's own `404.html`."""
    return Starlette(
        routes=[Mount("/", app=StaticFiles(directory=site_dir, html=True), name="docs")]
    )
