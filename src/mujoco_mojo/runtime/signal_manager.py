from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pint
import polars as pl

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.typing import MatN, SignalCategory
from mujoco_mojo.utils.defaults import TIME_COLUMN_NAME
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.unit_system import ureg

logger = get_logger(__name__)

__all__ = ["SignalManager"]

_FLOAT64_BYTES = np.dtype(np.float64).itemsize

_COLUMN_METADATA_KEY = "column_metadata"
"""Key under which the per-column metadata JSON blob is stored in the parquet file's footer."""


def _validate_signal_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Validates the well-known `dimension`/`units` metadata keys via Pint, leaving any other user-defined keys untouched.

    `dimension` (e.g. "[length] / [time]") tags the physical quantity type without committing to a concrete unit -- the right choice for built-in signals where the user's modeling unit system isn't knowable. `units` (e.g. "meter / second") is for the rarer case where the concrete unit truly is known. If both are given, they must describe the same dimensionality.
    """
    dimension = metadata.get("dimension")
    units = metadata.get("units")

    dimensionality = None
    if dimension is not None:
        try:
            dimensionality = ureg.get_dimensionality(dimension)
        except (pint.UndefinedUnitError, pint.DefinitionSyntaxError) as e:
            raise ValueError(f"Invalid signal metadata dimension {dimension!r}: {e}")

    if units is not None:
        try:
            parsed_units = ureg.parse_units(units)
        except pint.UndefinedUnitError as e:
            raise ValueError(f"Invalid signal metadata units {units!r}: {e}")
        if dimensionality is not None and parsed_units.dimensionality != dimensionality:
            raise ValueError(
                f"Signal metadata units {units!r} ({parsed_units.dimensionality}) do not "
                f"match dimension {dimension!r} ({dimensionality})"
            )

    return metadata


def resolve_signal_manager(
    signal_manager: SignalManager | None,
) -> SignalManager | None:
    """
    Returns `signal_manager` if given, otherwise falls back to the `SignalManager` of the innermost enclosing `RuntimeManager` `with` block.

    The result may still be `None` if that `RuntimeManager` simply has no `SignalManager` configured (telemetry recording disabled for this trial) -- callers should treat `None` as "nothing to record to" rather than an error. Raises only if there is no active `RuntimeManager` context at all.
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

    # === BEGIN PRIVATE API ===
    _key_cache: dict[tuple[str, tuple[str, ...], str], str] = field(
        default_factory=dict, init=False
    )
    """Caches (category, subgroups, attr) tuples to their joined string keys."""

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

    _column_metadata: dict[str, dict[str, Any]] = field(
        default_factory=dict, init=False
    )
    """User-supplied metadata (e.g. `dimension`/`units`) for columns that registered any, keyed by full signal key. Written into the merged parquet file's footer on `close()`."""

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
        self._data_buffer = np.zeros(
            (self._capacity, initial_col_guess), dtype=np.float64
        )

        # ensure time is always index 0
        self._key_to_idx[TIME_COLUMN_NAME] = 0
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

    def track(
        self,
        getter: Callable[[], float],
        category: SignalCategory | str,
        subgroups: tuple[str, ...] = (),
        *,
        attr: str | None = None,
        metadata: dict[str, Any] | None = None,
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
            self.post(getter(), category, subgroups, attr=attr, metadata=metadata)

        self.register_sampler(_sample)

    def post(
        self,
        value: float,
        category: SignalCategory | str,
        subgroups: tuple[str, ...] = (),
        *,
        attr: str | None = None,
        metadata: dict[str, Any] | None = None,
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
            metadata (dict[str, Any] | None, optional): Arbitrary metadata for this signal, persisted into the telemetry file's footer. Only consulted the first time this signal is registered (ignored on later calls for the same signal). Two keys are validated via Pint if present: `dimension` (e.g. `"[length] / [time]"`), for tagging the physical quantity type when the concrete unit isn't knowable (the right choice for built-in signals, since the user's modeling unit system isn't known here), and `units` (e.g. `"meter / second"`), for the rarer case the concrete unit truly is known. Any other keys (e.g. `display_name`, `comment`) pass through unvalidated. Defaults to None.

        Examples:
            >>> # Becomes "Bodies/Hand/xpos:x"
            >>> manager.post(1.2, SignalCategory.BODIES, ("Hand", "xpos"), "x")

            >>> # Becomes "Sensors/IMU/Accel:z"
            >>> manager.post(9.81, "Sensors", ("IMU", "Accel"), attr="z")

            >>> # Tag a custom signal's physical quantity type without committing to a unit system
            >>> manager.post(0.4, "Custom", ("Spring",), attr="stiffness", metadata={"dimension": "[force] / [length]"})

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

            if metadata:
                self._column_metadata[full_key] = _validate_signal_metadata(metadata)

            logger.debug(f"New signal registered: {full_key} at index {idx}")

            # grow buffer if exceeding the initial guess
            if self._n_cols > self._data_buffer.shape[1]:
                n_cols_to_add = 50
                new_width = self._data_buffer.shape[1] + n_cols_to_add
                logger.debug(f"Growing telemetry buffer width to {new_width} columns.")

                growth = np.zeros(
                    (self._data_buffer.shape[0], n_cols_to_add), dtype=np.float64
                )
                self._data_buffer = np.hstack([self._data_buffer, growth])

            # more columns means more bytes per row, so the row budget shrinks
            self._recompute_capacity()

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
        self._data_buffer.fill(0.0)

    def _file_metadata(self) -> dict[str, str] | None:
        """Builds the parquet file-level metadata dict, or None if no signal registered any."""
        if not self._column_metadata:
            return None
        return {_COLUMN_METADATA_KEY: json.dumps(self._column_metadata)}

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
        self.flush()
        self._merge_parts()
        logger.info(f"Telemetry stream closed. Data saved to {self.export_path}")
