from pathlib import Path

from pydantic import HttpUrl

from mujoco_mojo.__about__ import __url__

REPO_URL = HttpUrl(url=__url__)
"""Link to the remote repo for use with reporting elements."""

USER_GUIDE_DIR: Path = Path(__file__).parent / "user_guide"
"""The user guides that ship with the package, as plain markdown. `scripts/gen_user_guide.py` writes them from the docs, `mujoco-mojo docs path` prints this folder, and SensAI reads them from it."""

MUJOCO_MOJO_DIR: Path = Path.home() / ".mujoco-mojo"
"""Canonical user-level directory for all mujoco-mojo data (settings, profiles, lab graphs, etc.)."""
