from pathlib import Path

from pydantic import HttpUrl

from mujoco_mojo.__about__ import __url__

REPO_URL = HttpUrl(url=__url__)
"""Link to the remote repo for use with reporting elements."""

DOCS_SOURCE_DIR: Path = Path(__file__).parent / "docs_source"
"""The source of the documentation site that ships with the package: a copy of `mkdocs.yml` and the pages (`docs/`), without the images, and with each page's code includes already filled in. `scripts/gen_docs_source.py` writes it, `mujoco-mojo docs build` builds the site from it, `mujoco-mojo docs path` prints this folder, and SensAI reads the guides from it."""

DOCS_ASSETS_DIR: Path = DOCS_SOURCE_DIR / "docs" / "assets"
"""The logos of the docs site, in the bundled docs source. The Dojo serves its light and dark logo from here, and makes its favicons from the light one, so the package carries one copy of each."""

MUJOCO_MOJO_DIR: Path = Path.home() / ".mujoco-mojo"
"""Canonical user-level directory for all mujoco-mojo data (settings, profiles, lab graphs, etc.)."""
