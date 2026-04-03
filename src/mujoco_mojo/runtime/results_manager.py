from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import duckdb
import mujoco
import polars as pl

from mujoco_mojo.process_manager import NamedValue, NamedValueDict, ValueName
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)


@dataclass
class ResultsManager:
    db_path: Path
    """Where the DuckDB file should be saved."""

    batch_size: int = 1000
    """Number of steps before flushing to disk."""

    record_decimation: int = 1
    """How many steps between each recording should be performed."""

    ledger: NamedValueDict[float] = field(
        default_factory=NamedValueDict[float], init=False
    )
    """Values to be recorded. This dictionary is flushed on every timestep."""

    _harvest_tasks: list[Callable[[mujoco.MjModel, mujoco.MjData], None]] = field(
        default_factory=list, init=False
    )

    _conn: duckdb.DuckDBPyConnection = field(init=False)
    _buffer: list[dict[str, float]] = field(default_factory=list, init=False)
    _step_count: int = -1

    @staticmethod
    def default_db_name() -> Literal["telemetry.duckdb"]:
        return "telemetry.duckdb"

    @property
    def db_name(self) -> str:
        return self.default_db_name()

    @staticmethod
    def default_table_name() -> Literal["result"]:
        return "result"

    @property
    def table_name(self) -> str:
        return self.default_table_name()

    def __post_init__(self):
        # Ensure directory exists and connect
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(self.db_path))

    def schedule_harvest_task(self, task: Callable):
        self._harvest_tasks.append(task)

    def flush_ledger(self):
        """Clear the ledger for a new timestep."""
        self.ledger = NamedValueDict[float]()

    def post(
        self,
        value: float | NamedValue[float],
        category: Literal["Bodies", "Sites", "Joints", "Sensors", "Loads", "Custom"],
        subgroup: str | None = None,
        attr: str | None = None,
    ):
        """
        Injects a value into the telemetry ledger using a hierarchical namespace.

        This method constructs a structured key that the dashboard uses to build a navigable tree view. The naming convention follows a folder-like structure to group related signals (e.g., all axes of a body's position).

        Format:
            Category/Subgroup:Attribute
            (e.g., "Bodies/Link_1:xpos_x")

        Args:
            value (float | NamedValue[float]): The numeric data to record. If a NamedValue is passed and 'subgroup' is not provided, the NamedValue's internal name is used as the subgroup.
            category (Literal["Bodies", "Joints", "Sensors", "Loads", "Custom"]): _description_
            subgroup (str | None, optional): The top-level organizational folder (e.g., "Bodies"). Defaults to None.
            attr (str | None, optional): The specific signal or component name (e.g., "qpos" or "x"). Defaults to None.

        Examples:
            >>> # Becomes "Bodies/Hand:xpos_x"
            >>> manager.post(1.2, "Bodies", "Hand", "xpos_x")

            >>> # Becomes "Sensors/IMU"
            >>> manager.post(9.81, "Sensors", "IMU")

            >>> # Using NamedValue (Becomes "Joints/Elbow:qpos")
            >>> nv = NamedValue(name="Elbow", value=0.4)
            >>> manager.post(nv, "Joints", attr="qpos")

        """
        # extract the base name and value
        if isinstance(value, NamedValue):
            stored_val = float(value.value)
            effective_name = subgroup or value.name
        else:
            stored_val = float(value)
            effective_name = subgroup

        # build the folder path ('/' for folders, ':' for components/attrs)
        path_parts = [category]
        if effective_name:
            path_parts.append(effective_name)

        full_key = "/".join(path_parts)

        if attr:
            full_key += f":{attr}"

        # inject to ledger for next flush
        self.ledger[full_key] = NamedValue[float](
            name=ValueName(full_key), stored_value=stored_val
        )

    def record(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        """Finalizes the ledger and sends to the buffer/results file."""
        self._step_count += 1
        if self._step_count % self.record_decimation != 0:
            return

        for task in self._harvest_tasks:
            task(mj_model, mj_data)

        self.log_step(timestamp=mj_data.time, data=self.ledger)

    def log_step(self, timestamp: float, data: NamedValueDict[float]):
        """Appends a row to the memory buffer."""
        row = {"time": timestamp}
        row.update({k: nv.value for k, nv in data.items()})

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
