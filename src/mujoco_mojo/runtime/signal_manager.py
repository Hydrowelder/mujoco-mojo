from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import polars as pl

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.stochas import UnitSystem
from mujoco_mojo.typing import MatN
from mujoco_mojo.utils.column import Column
from mujoco_mojo.utils.defaults import TIME_COLUMN_NAME
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.signal_metadata import ColumnMetadata

logger = get_logger(__name__)

__all__ = ["SignalManager"]

_FLOAT64_BYTES = np.dtype(np.float64).itemsize

_COLUMN_METADATA_KEY = "column_metadata"
"""Key under which the per-column metadata JSON blob is stored in the parquet file's footer."""


def resolve_signal_manager(
    signal_manager: SignalManager | None,
) -> SignalManager | None:
    """
    Returns `signal_manager` if given, otherwise falls back to the `SignalManager` of the innermost enclosing `RuntimeManager` `with` block.

    The result may still be `None` if that `RuntimeManager` simply has no `SignalManager` configured (telemetry recording disabled for this trial). Callers should treat `None` as "nothing to record to" rather than an error. Raises only if there is no active `RuntimeManager` context at all.
    """
    if signal_manager is not None:
        return signal_manager

    from mujoco_mojo.runtime.runtime_manager import RuntimeManager

    return RuntimeManager.current().signal_manager


@dataclass
class SignalManager:
    export_path: Path
    """Where the output file should be saved."""

    target_buffer_bytes: int = 8 * 1024 * 1024
    """Approximate in-memory buffer size, in bytes, before flushing to a part file. The actual row capacity is derived from this and the current column count (see `_recompute_capacity`), so flush frequency stays roughly memory/file-size bounded as signals are registered, rather than fixed at a row count regardless of width. Defaults to 8 MB."""

    record_decimation: int = 1
    """How many steps between each recording should be performed."""

    unit_system: UnitSystem | None = None
    """When set, the time column's concrete unit is resolved from `unit_system.time` (e.g. `"second"`, `"millisecond"`). Always tagged with `dimension="[time]"` regardless."""

    # === BEGIN PRIVATE API ===
    _col_idx: dict[Column, int] = field(default_factory=dict, init=False)
    """Maps every `Column` object `post` has seen to its column index in the NumPy buffer. Equal columns share one entry."""

    _key_to_idx: dict[str, int] = field(default_factory=dict, init=False)
    """Maps signal strings to their specific column index in the NumPy buffer."""

    _data_buffer: MatN = field(init=False)
    """2D NumPy array (capacity, n_signals) for high-speed value insertion."""

    _capacity: int = field(init=False)
    """Row-count flush threshold derived from `target_buffer_bytes` and the current column count; shrinks as more signals are registered, never exceeding `_data_buffer`'s allocated rows."""

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

    _part_paths: list[Path] = field(default_factory=list, init=False)
    """Paths of per-flush part files written this run, in order, pending merge in `close()`."""

    _columns: dict[str, Column] = field(default_factory=dict, init=False)
    """Every registered column, keyed by its full name. Each column's metadata is written into the merged parquet file's footer on `close()`."""

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

    def _part_path(self, idx: int) -> Path:
        return self.export_path.with_name(f".{self.export_path.name}.part{idx:05d}")

    def __post_init__(self):
        # ensure directory exists and connect
        self.export_path.parent.mkdir(parents=True, exist_ok=True)

        # each SignalManager represents a brand new recording session: clear out
        # any telemetry left over from a prior run at this path (including
        # unmerged part files from a run that crashed before close()) so that
        # close()'s diagonal-concat (meant to merge batches *within* this run)
        # doesn't silently stitch stale rows from a previous, possibly longer,
        # run onto the front of the new file.
        if self.export_path.exists():
            self.export_path.unlink()
        for stale_part in self.export_path.parent.glob(
            f".{self.export_path.name}.part*"
        ):
            stale_part.unlink()

        # pre-allocate some columns as a starting guess, with row count sized to
        # hold about target_buffer_bytes at that guess; grow columns as needed
        # and shrink the capacity (see _recompute_capacity) as they do
        initial_col_guess = 100
        self._capacity = self._rows_for_cols(initial_col_guess)
        self._data_buffer = np.full(
            (self._capacity, initial_col_guess), np.nan, dtype=np.float64
        )

        # ensure time is always index 0
        self._key_to_idx[TIME_COLUMN_NAME] = 0
        time_meta = ColumnMetadata(dimension="[time]")
        if self.unit_system is not None and self.unit_system.time is not None:
            time_meta = ColumnMetadata(dimension="[time]", unit=self.unit_system.time)
        self._columns[TIME_COLUMN_NAME] = Column(
            category=TIME_COLUMN_NAME, metadata=time_meta
        )
        self._n_cols = 1
        logger.debug(
            f"SignalManager initialized: buffer capacity={self._capacity} rows, Path={self.export_path}"
        )

    def _rows_for_cols(self, n_cols: int) -> int:
        """Returns the number of float64 rows that fit in `target_buffer_bytes` given `n_cols` columns."""
        return max(1, self.target_buffer_bytes // (n_cols * _FLOAT64_BYTES))

    def _recompute_capacity(self) -> None:
        """Re-derives the flush threshold for the current column count, clamped to `_data_buffer`'s allocated rows."""
        self._capacity = min(
            self._rows_for_cols(self._n_cols), self._data_buffer.shape[0]
        )

    def register_sampler(self, task: Callable[[MjState], Any]):
        self._sample_tasks.append(task)
        logger.debug(
            f"Registered new sampler: {task.__name__ if hasattr(task, '__name__') else 'lambda'}"
        )

    def track(self, getter: Callable[[], float], column: Column):
        """
        Registers `getter` to be called and posted on every recorded step, under `column`.

        `getter` is called fresh on every recorded step, so it should look up a value that changes over the course of the simulation (e.g. a variable updated each step, an attribute, or an indexing operation) rather than a constant computed once. If the underlying value never changes after registration, `track` will simply keep posting that same value every step.

        Examples:
            >>> # Becomes "Custom/MyGroup:value", re-read from `obj.value` every step
            >>> column = Column(category="Custom", subgroups=("MyGroup",), attr="value")
            >>> manager.track(lambda: obj.value, column)

            >>> # Also works: `level` is a variable reassigned each step in the same scope
            >>> level = 0.0
            >>> manager.track(lambda: level, Column(category="Custom", subgroups=("MyGroup",), attr="level"))
            >>> for _ in range(n_steps):
            ...     level = compute_level(state)
            ...     rm.step(state)

        """

        def _sample(_: MjState):
            self.post(getter(), column)

        self.register_sampler(_sample)

    @property
    def _column_metadata(self) -> dict[str, ColumnMetadata]:
        """The metadata of every registered column that has any, keyed by full name."""
        return {name: c.metadata for name, c in self._columns.items() if c.metadata}

    def _register(self, column: Column) -> int:
        """Adds a new column to the buffer and returns its index."""
        full_key = str(column)
        idx = self._n_cols
        self._key_to_idx[full_key] = idx
        self._columns[full_key] = column
        self._n_cols += 1

        logger.debug(f"New signal registered: {full_key} at index {idx}")

        # grow buffer if exceeding the initial guess
        if self._n_cols > self._data_buffer.shape[1]:
            n_cols_to_add = 50
            new_width = self._data_buffer.shape[1] + n_cols_to_add
            logger.debug(f"Growing telemetry buffer width to {new_width} columns.")

            growth = np.full(
                (self._data_buffer.shape[0], n_cols_to_add),
                np.nan,
                dtype=np.float64,
            )
            self._data_buffer = np.hstack([self._data_buffer, growth])

        # more columns means more bytes per row, so the row budget shrinks
        self._recompute_capacity()
        return idx

    def post(self, value: float, column: Column):
        """
        Injects a value into the telemetry ledger under `column`.

        The column's name places the signal in a hierarchical namespace that the dashboard uses to build a navigable tree view. Its metadata is persisted into the telemetry file's footer, but only the first time a column with this name is registered (metadata on later columns with the same name is ignored).

        This is called for every column on every timestep, so build each `Column` once and reuse it rather than constructing one per call. A `Column` with the same parts as one already seen still works, but is looked up by comparing its fields instead of by identity.

        Args:
            value (float): The numeric data to record.
            column (Column): Where to record it: the category, subgroups, and attr that make up the column's name, plus its metadata. See `Column` for the naming grammar and `ColumnMetadata` for the metadata fields.

        Examples:
            >>> # Becomes "Bodies/Hand/xpos:x"
            >>> x = Column(category=SignalCategory.BODIES, subgroups=("Hand", "xpos"), attr="x")
            >>> manager.post(1.2, x)

            >>> # Tag a custom signal's physical quantity type without committing to a unit system
            >>> stiffness = Column(
            ...     category="Custom",
            ...     subgroups=("Spring",),
            ...     attr="stiffness",
            ...     metadata={"dimension": "[force] / [length]"},
            ... )
            >>> manager.post(0.4, stiffness)

        """
        idx = self._col_idx.get(column)
        if idx is None:
            # first time this column object is seen: a different column object with the
            # same name may already be registered, in which case it keeps its metadata
            registered = self._key_to_idx.get(str(column))
            idx = registered if registered is not None else self._register(column)
            self._col_idx[column] = idx

        # write value to buffer for next flush
        self._data_buffer[self._buffer_row_idx, idx] = value

    def record(self, state: MjState):
        """Executes all samplers and advances the buffer index. Flushes if due."""
        logger.debug(f"Recording telemetry at t={state.data.time:.6f}")

        self._step_count += 1
        if self._step_count % self.record_decimation != 0:
            return

        # record simulation time
        self._data_buffer[self._buffer_row_idx, 0] = state.data.time

        # run samplers
        for task in self._sample_tasks:
            task(state)

        self._buffer_row_idx += 1

        if self._buffer_row_idx >= self._capacity:
            self.flush()

    def flush(self):
        """Writes the memory buffer to a new part file; parts are merged into `export_path` on `close()`."""
        if self._buffer_row_idx == 0:
            return

        # build column names from mapping
        sorted_keys = sorted(self._key_to_idx.keys(), key=lambda x: self._key_to_idx[x])

        # slice only the used portion of the buffer
        new_df = pl.from_numpy(
            data=self._data_buffer[: self._buffer_row_idx, : self._n_cols],
            schema=sorted_keys,
        )

        part_path = self._part_path(len(self._part_paths))
        logger.info(f"Flushing {self._buffer_row_idx} steps to {part_path.name}")
        # each part is a brand new file, never read back until close()'s merge,
        # so flushing stays O(buffer capacity) instead of O(total rows written
        # so far) and never reads-then-rewrites a file (avoiding a Windows file lock)
        new_df.write_parquet(part_path, compression="zstd")
        self._part_paths.append(part_path)

        # reset buffer for next batch
        self._buffer_row_idx = 0
        self._data_buffer.fill(np.nan)

    def _file_metadata(self) -> dict[str, str] | None:
        """Builds the parquet file-level metadata dict, or None if no signal registered any."""
        if not self._column_metadata:
            return None
        return {
            _COLUMN_METADATA_KEY: json.dumps(
                {k: v.model_dump(mode="json") for k, v in self._column_metadata.items()}
            )
        }

    def _merge_parts(self):
        """Streams all part files written this run into `export_path`, then removes the parts."""
        if not self._part_paths:
            return

        file_metadata = self._file_metadata()

        # the raw rename is only safe when there's no footer metadata to embed --
        # a rename can't add a footer, so that case falls through to the
        # scan/sink path below (a single part is just a one-element scan)
        if len(self._part_paths) == 1 and file_metadata is None:
            self._part_paths[0].replace(self.export_path)
        else:
            # every part's columns are a subset of the full signal set
            # accumulated in _key_to_idx (columns are only ever added, never
            # removed mid-run), so this schema already covers every part
            # without needing to read any of them first
            sorted_keys = sorted(
                self._key_to_idx.keys(), key=lambda x: self._key_to_idx[x]
            )
            schema = dict.fromkeys(sorted_keys, pl.Float64)

            # missing_columns="insert" reproduces diagonal-concat (null-filling
            # columns a part doesn't have), and sink_parquet streams the merge
            # instead of reading every part into memory at once like
            # pl.concat(..., how="diagonal") would
            pl.scan_parquet(
                self._part_paths, schema=schema, missing_columns="insert"
            ).sink_parquet(self.export_path, metadata=file_metadata)

            for part_path in self._part_paths:
                part_path.unlink()

        self._part_paths.clear()

    def close(self):
        # captured before flush()/_merge_parts() reset this state, so the log below
        # doesn't claim data was saved when recording was disabled for this run
        had_data = self._buffer_row_idx > 0 or bool(self._part_paths)
        self.flush()
        self._merge_parts()
        if had_data:
            logger.info(f"Telemetry stream closed. Data saved to {self.export_path}")
