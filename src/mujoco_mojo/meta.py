from pathlib import Path

from pydantic import HttpUrl

from mujoco_mojo.__about__ import __url__

REPO_URL = HttpUrl(url=__url__)
"""Link to the remote repo for use with reporting elements."""

MUJOCO_MOJO_DIR: Path = Path.home() / ".mujoco-mojo"
"""Canonical user-level directory for all mujoco-mojo data (settings, profiles, lab graphs, etc.)."""
