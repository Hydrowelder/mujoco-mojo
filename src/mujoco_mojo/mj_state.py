from __future__ import annotations

from dataclasses import dataclass

import mujoco

__all__ = ["MjState"]


@dataclass
class MjState:
    """Pairs MjModel and MjData for passing through runtime methods."""

    model: mujoco.MjModel
    data: mujoco.MjData
