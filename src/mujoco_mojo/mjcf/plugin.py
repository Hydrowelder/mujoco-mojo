from __future__ import annotations

from typing import Optional

from mujoco_mojo.base import XMLModel

__all__ = ["Plugin"]


class Plugin(XMLModel):
    """Associate this mesh with an engine plugin. Either plugin or instance are required."""

    tag = "plugin"

    attributes = ("plugin", "instance")

    plugin: Optional[str] = None
    """Plugin identifier, used for implicit plugin instantiation."""

    instance: Optional[str] = None  # TODO I think this was implemented poorly
    """Instance name, used for explicit plugin instantiation."""
