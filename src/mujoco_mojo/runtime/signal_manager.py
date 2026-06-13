from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import polars as pl

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.typing import SignalCategory, VecN
from mujoco_mojo.utils.defaults import TIME_COLUMN_NAME
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)


@dataclass
class SignalManager:
    export_path: Path
    """Where the output file should be saved."""

    batch_size: int = 1000
    """Number of steps before flushing to disk."""

    record_decimation: int = 1
    """How many steps between each recording should be performed."""

    # === BEGIN PRIVATE API ===
    _key_cache: dict[tuple[str, tuple[str, ...], str], str] = field(
        default_factory=dict, init=False
    )
    """Caches (category, subgroups, attr) tuples to their joined string keys."""

    _key_to_idx: dict[str, int] = field(default_factory=dict, init=False)
    """Maps signal strings to their specific column index in the NumPy buffer."""

    _data_buffer: VecN = field(init=False)
    """2D NumPy array (batch_size, n_signals) for high-speed value insertion."""

    _sample_tasks: list[Callable[[MjState], Any]] = field(
        default_factory=list, init=False
    )
    """Functions to be called to sample values to be recorded."""

    _buffer_row_idx: int = 0
    """Current row position in the pre-allocated data buffer."""

    _step_count: int = -1
    """Global counter of physics steps to handle decimation."""

    _n_cols: int = 0
    """Current number of unique signals registered."""

    @staticmethod
    def default_output_name() -> Literal["telemetry.parquet"]:
        return "telemetry.parquet"

    @property
    def db_name(self) -> str:
        return self.default_output_name()

    @staticmethod
    def default_table_name() -> Literal["result"]:
        return "result"

    @property
    def table_name(self) -> str:
        return self.default_table_name()

    def __post_init__(self):
        # ensure directory exists and connect
        self.export_path.parent.mkdir(parents=True, exist_ok=True)

        # each SignalManager represents a brand new recording session: clear out
        # any telemetry left over from a prior run at this path so that flush()'s
        # diagonal-concat (meant to merge batches *within* this run) doesn't
        # silently stitch stale rows from a previous, possibly longer, run onto
        # the front of the new file.
        if self.export_path.exists():
            self.export_path.unlink()

        # pre-allocate some columns as a starting guess; grow as needed
        self._data_buffer = np.zeros((self.batch_size, 100), dtype=np.float64)

        # ensure time is always index 0
        self._key_to_idx[TIME_COLUMN_NAME] = 0
        self._n_cols = 1
        logger.debug(
            f"SignalManager initialized: Batch size={self.batch_size}, Path={self.export_path}"
        )

    def register_sampler(self, task: Callable[[MjState], Any]):
        self._sample_tasks.append(task)
        logger.debug(
            f"Registered new sampler: {task.__name__ if hasattr(task, '__name__') else 'lambda'}"
        )

    def track(
        self,
        getter: Callable[[], float],
        category: SignalCategory | str,
        subgroups: tuple[str, ...] = (),
        *,
        attr: str | None = None,
    ):
        """
        Registers `getter` to be called and posted on every recorded step, under the same `category`/`subgroups`/`attr` namespace as `post`.

        `getter` is called fresh on every recorded step, so it should look up a value that changes over the course of the simulation (e.g. a variable updated each step, an attribute, or an indexing operation) rather than a constant computed once. If the underlying value never changes after registration, `track` will simply keep posting that same value every step.

        Examples:
            >>> # Becomes "Custom/MyGroup:value", re-read from `obj.value` every step
            >>> manager.track(lambda: obj.value, "Custom", ("MyGroup",), attr="value")

            >>> # Also works: `level` is a variable reassigned each step in the same scope
            >>> level = 0.0
            >>> manager.track(lambda: level, "Custom", ("MyGroup",), attr="level")
            >>> for _ in range(n_steps):
            ...     level = compute_level(state)
            ...     rm.step(state)

        """

        def _sample(_: MjState):
            self.post(getter(), category, subgroups, attr=attr)

        self.register_sampler(_sample)

    def post(
        self,
        value: float,
        category: SignalCategory | str,
        subgroups: tuple[str, ...] = (),
        *,
        attr: str | None = None,
    ):
        """
        Injects a value into the telemetry ledger using a hierarchical namespace.

        This method constructs a structured key that the dashboard uses to build a navigable tree view. The naming convention follows a folder-like structure to group related signals (e.g., all axes of a body's position).

        Format:
            Category/Subgroup:Attribute
            (e.g., "Bodies/Link_1:xpos_x")

        Args:
            value (float): The numeric data to record.
            category (SignalCategory | str): Top level category (e.g., "Bodies")
            subgroups (tuple[str, ...], optional): The second-level organizational folders. Defaults to an empty tuple.
            attr (str | None, optional): The specific signal or component name (e.g., "qpos" or "x"). Defaults to None.

        Examples:
            >>> # Becomes "Bodies/Hand/xpos:x"
            >>> manager.post(1.2, SignalCategory.BODIES, ("Hand", "xpos"), "x")

            >>> # Becomes "Sensors/IMU/Accel:z"
            >>> manager.post(9.81, "Sensors", ("IMU", "Accel"), attr="z")

        """
        # use tuple as cache key to avoid string construction
        cache_lookup = (str(category), subgroups, attr if attr is not None else "")

        if cache_lookup in self._key_cache:
            # fast path for cached signal
            full_key = self._key_cache[cache_lookup]
        else:
            # slow path for a new signal
            path_parts = [str(category)] + [str(s) for s in subgroups if s]
            full_key = "/".join(path_parts)
            if attr:
                full_key += f":{attr}"

            self._key_cache[cache_lookup] = full_key

        # get column index
        if full_key in self._key_to_idx:
            idx = self._key_to_idx[full_key]
        else:
            # register a new signal column
            idx = self._n_cols
            self._key_to_idx[full_key] = idx
            self._n_cols += 1

            logger.debug(f"New signal registered: {full_key} at index {idx}")

            # grow buffer if exceeding the initial guess
            if self._n_cols > self._data_buffer.shape[1]:
                n_cols_to_add = 50
                new_width = self._data_buffer.shape[1] + n_cols_to_add
                logger.debug(f"Growing telemetry buffer width to {new_width} columns.")

                growth = np.zeros((self.batch_size, n_cols_to_add), dtype=np.float64)
                self._data_buffer = np.hstack([self._data_buffer, growth])

        # write value to buffer for next flush
        self._data_buffer[self._buffer_row_idx, idx] = value

    def record(self, state: MjState):
        """Executes all samplers and advances the buffer index. Flushes if due."""
        self._step_count += 1
        if self._step_count % self.record_decimation != 0:
            return

        # record simulation time
        self._data_buffer[self._buffer_row_idx, 0] = state.data.time

        # run samplers
        for task in self._sample_tasks:
            task(state)

        self._buffer_row_idx += 1

        if self._buffer_row_idx >= self.batch_size:
            self.flush()

    def flush(self):
        """Commits the memory buffer to the output file."""
        if self._buffer_row_idx == 0:
            return

        # build column names from mapping
        sorted_keys = sorted(self._key_to_idx.keys(), key=lambda x: self._key_to_idx[x])

        # slice only the used portion of the buffer
        new_df = pl.from_numpy(
            data=self._data_buffer[: self._buffer_row_idx, : self._n_cols],
            schema=sorted_keys,
        )

        logger.debug(
            f"Flushing {self._buffer_row_idx} steps to {self.export_path.name}"
        )

        if self.export_path.exists():
            try:
                # Use diagonal concat to safely handle signals added mid-simulation
                existing_df = pl.read_parquet(self.export_path)
                combined_df = pl.concat([existing_df, new_df], how="diagonal")
                combined_df.write_parquet(self.export_path, compression="zstd")
            except Exception as e:
                logger.error(f"Failed to append telemetry: {e}")
        else:
            new_df.write_parquet(self.export_path, compression="zstd")

        # reset buffer for next batch
        self._buffer_row_idx = 0
        self._data_buffer.fill(0.0)

    def close(self):
        self.flush()
        logger.info(f"Telemetry stream closed. Data saved to {self.export_path}")
