"""
Type-checked source for the code examples in `docs/user-guides/workflow/runtime-script.md`.

The documentation embeds these snippets directly via `pymdownx.snippets` section markers (`--8<-- [start:name]` / `--8<-- [end:name]`), so the examples shown to users are exactly the code that ruff and the type checkers validate. If an API change breaks an example, the checkers fail on this file instead of the documentation silently rotting.
"""

from __future__ import annotations

from enum import IntEnum
from typing import cast

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

signal_manager = cast(rt.SignalManager, None)
"""Stands in for `rm.signal_manager`, which a runtime function reaches through its `RuntimeManager`. Nothing here is run; the checkers only read the types."""


def compute_nutation(state: mojo.MjState) -> float:
    """Stands in for the calculation a user would write."""
    raise NotImplementedError


# --8<-- [start:custom_signal]
nutation = mojo.utils.Column(
    category=mojo.SignalCategory.BODIES,
    subgroups=("racket",),
    attr="nutation_deg",
)


def sample_nutation(state: mojo.MjState) -> None:
    signal_manager.post(compute_nutation(state), nutation)


# --8<-- [end:custom_signal]


# --8<-- [start:enum_signal]
class Mode(IntEnum):
    IDLE = 0
    RUNNING = 1


mode = mojo.utils.Column(
    category=mojo.SignalCategory.CUSTOM,
    subgroups=("controller",),
    attr="mode",
    metadata=mojo.utils.ColumnMetadata.from_enum(Mode),
)
# --8<-- [end:enum_signal]
