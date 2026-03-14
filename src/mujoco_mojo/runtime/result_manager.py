from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import mujoco
import polars as pl


@dataclass
class ResultsManager:
    db_path: Path
    table_name: str = "result"
    batch_size: int = 1000  # Number of steps before flushing to disk

    ledger: dict[str, Any] = field(default_factory=dict, init=False)

    _harvest_tasks: list[Callable[[mujoco.MjModel, mujoco.MjData], None]] = field(
        default_factory=list, init=False
    )

    _conn: duckdb.DuckDBPyConnection = field(init=False)
    _buffer: list[dict] = field(default_factory=list, init=False)

    def __post_init__(self):
        # Ensure directory exists and connect
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(self.db_path))

    def add_harvest_task(self, task: Callable):
        self._harvest_tasks.append(task)

    def start_step(self):
        """Clear the ledger for a new timestep."""
        self.ledger = {}

    def post(self, key: str, value: Any):
        """Allows an object to inject a value into the ledger to be recorded in the results file."""
        self.ledger[key] = value

    def record(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """Finalizes the ledger and sends to the buffer/results file."""
        self.start_step()

        for task in self._harvest_tasks:
            task(mj_model, mj_data)

        self.log_step(timestamp=mj_data.time, data=self.ledger)

    def log_step(self, timestamp: float, data: dict[str, Any]):
        """Appends a row to the memory buffer."""
        row = {"time": timestamp}
        row.update(data)
        self._buffer.append(row)

        if len(self._buffer) >= self.batch_size:
            self.flush()

    def flush(self):
        """Commits the memory buffer to the DuckDB file."""
        if not self._buffer:
            return

        # convert buffer to Polars DataFrame for instant DuckDB ingestion
        _df = pl.DataFrame(self._buffer)

        # create table if it doesn't exist, otherwise append
        try:
            self._conn.execute(f"INSERT INTO {self.table_name} SELECT * FROM _df")
        except duckdb.CatalogException:
            self._conn.execute(f"CREATE TABLE {self.table_name} AS SELECT * FROM _df")

        self._buffer = []

    def close(self):
        self.flush()
        self._conn.close()
