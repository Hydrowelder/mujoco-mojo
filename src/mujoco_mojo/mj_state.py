from __future__ import annotations

from dataclasses import dataclass, field

import mujoco

__all__ = ["MjState"]


@dataclass
class MjState:
    """Pairs MjModel and MjData for passing through runtime methods."""

    model: mujoco.MjModel
    data: mujoco.MjData

    _rne_post_constraint_fresh: bool = field(
        default=False, init=False, repr=False, compare=False
    )

    def invalidate_rne_post_constraint(self) -> None:
        """
        Marks `data.cfrc_int`/`cfrc_ext`/`cacc` as stale, so the next `ensure_rne_post_constraint()` call recomputes them.

        Call this whenever `qpos`/`qvel`/`qacc` change (e.g. before `mj_forward`/`mj_step`), since those quantities are otherwise left holding values computed against the previous state.
        """
        self._rne_post_constraint_fresh = False

    def ensure_rne_post_constraint(self) -> None:
        """
        Calls `mujoco.mj_rnePostConstraint` if it hasn't already run since the last `invalidate_rne_post_constraint()`, refreshing `data.cfrc_int`/`cfrc_ext`/`cacc`.

        MuJoCo does not populate these via `mj_forward`/`mj_step` alone, only as a side effect of certain sensor types. Accessors that read them (e.g. `Joint.rt_cfrc_int`, `Site.rt_acc`, `Geom.rt_xacc`) call this themselves, and the freshness flag means repeated reads within the same step only pay for the call once.
        """
        if not self._rne_post_constraint_fresh:
            mujoco.mj_rnePostConstraint(self.model, self.data)
            self._rne_post_constraint_fresh = True
