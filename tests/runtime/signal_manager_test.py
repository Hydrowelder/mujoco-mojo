from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import mujoco
import polars as pl
import pytest

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.utils.defaults import TIME_COLUMN_NAME


@pytest.fixture
def sm(tmp_path: Path) -> Generator[SignalManager, None, None]:
    """Provides a SignalManager pointing to a temporary directory."""
    db_file = tmp_path / "test_telemetry.parquet"
    manager = SignalManager(export_path=db_file, batch_size=5)
    yield manager
    # Ensure connection is closed so the file isn't locked
    try:
        manager.close()
    except Exception:
        pass


def test_hierarchical_key_generation(sm: SignalManager) -> None:
    """Verify the 'Category/Subgroup:Attribute' naming logic."""
    # Test full path
    sm.post(1.0, "Bodies", ("Hand",), attr="xpos_x")
    assert "Bodies/Hand:xpos_x" in sm._key_to_idx

    # Test simple path (no attr)
    sm.post(2.0, "Sensors", ("IMU",))
    assert "Sensors/IMU" in sm._key_to_idx

    # Test another signal
    sm.post(3.0, "Joints", ("Elbow",), attr="qpos")
    assert "Joints/Elbow:qpos" in sm._key_to_idx


def test_batching_and_persistence(sm: SignalManager) -> None:
    """Verify data is only committed to output after reaching batch_size."""
    # We need a mock MjModel/Data for the record call
    m: mujoco.MjModel = mujoco.MjModel.from_xml_string("<mujoco/>")
    d: mujoco.MjData = mujoco.MjData(m)

    # Post 4 steps (Batch size is 5)
    for i in range(4):
        sm.post(float(i), "Custom", ("Signal",))
        sm.record(MjState(m, d))

    # Buffer row index should have 4 rows (batch_size is 5, so no flush yet)
    assert sm._buffer_row_idx == 4

    # 5th step triggers flush
    sm.post(4.0, "Custom", ("Signal",))
    sm.record(MjState(m, d))

    assert sm._buffer_row_idx == 0  # Buffer cleared after flush

    # Verify output has the data
    df: pl.DataFrame = pl.read_parquet(sm.export_path)
    assert df.height == 5
    assert TIME_COLUMN_NAME in df.columns


def test_record_decimation(sm: SignalManager) -> None:
    """Verify that decimation correctly skips steps."""
    m: mujoco.MjModel = mujoco.MjModel.from_xml_string("<mujoco/>")
    d: mujoco.MjData = mujoco.MjData(m)

    sm.record_decimation = 3  # Record every 3rd step

    # Step 0: Records (step_count starts at -1, becomes 0)
    sm.record(MjState(m, d))
    assert sm._buffer_row_idx == 1

    # Step 1 & 2: Skip
    sm.record(MjState(m, d))
    sm.record(MjState(m, d))
    assert sm._buffer_row_idx == 1

    # Step 3: Records
    sm.record(MjState(m, d))
    assert sm._buffer_row_idx == 2


def test_sample_task_execution(sm: SignalManager) -> None:
    """Verify that scheduled sample tasks fire during record()."""
    m: mujoco.MjModel = mujoco.MjModel.from_xml_string("<mujoco/>")
    d: mujoco.MjData = mujoco.MjData(m)

    was_called: bool = False

    def mock_sample(state: MjState) -> None:
        nonlocal was_called
        sm.post(99.0, "Custom", ("Sampled",))
        was_called = True

    sm.register_sampler(mock_sample)
    sm.record(MjState(m, d))

    assert was_called
    assert "Custom/Sampled" in sm._key_to_idx


def test_multiple_samplers_execution_order(sm: SignalManager) -> None:
    """Verify that multiple samplers execute in registration order."""
    m: mujoco.MjModel = mujoco.MjModel.from_xml_string("<mujoco/>")
    d: mujoco.MjData = mujoco.MjData(m)

    execution_order: list[int] = []

    def sampler_1(state: MjState) -> None:
        execution_order.append(1)
        sm.post(1.0, "Sampler", ("One",))

    def sampler_2(state: MjState) -> None:
        execution_order.append(2)
        sm.post(2.0, "Sampler", ("Two",))

    def sampler_3(state: MjState) -> None:
        execution_order.append(3)
        sm.post(3.0, "Sampler", ("Three",))

    sm.register_sampler(sampler_1)
    sm.register_sampler(sampler_2)
    sm.register_sampler(sampler_3)
    sm.record(MjState(m, d))

    assert execution_order == [1, 2, 3]
    assert "Sampler/One" in sm._key_to_idx
    assert "Sampler/Two" in sm._key_to_idx
    assert "Sampler/Three" in sm._key_to_idx


def test_buffer_growth_on_signal_overflow(sm: SignalManager) -> None:
    """Verify buffer grows when exceeding initial column count."""
    m: mujoco.MjModel = mujoco.MjModel.from_xml_string("<mujoco/>")
    _d: mujoco.MjData = mujoco.MjData(m)

    initial_buffer_width: int = sm._data_buffer.shape[1]
    assert initial_buffer_width == 100

    # Register 120 unique signals (exceeds initial 100)
    for i in range(120):
        sm.post(float(i), "Signal", (f"S{i}",))

    # Buffer should have grown
    assert sm._data_buffer.shape[1] > initial_buffer_width
    assert sm._n_cols == 121  # 120 signals + 1 for TIME_COLUMN_NAME


def test_signal_value_correctness_in_output(sm: SignalManager) -> None:
    """Verify that signal values are correctly written to output file."""
    m: mujoco.MjModel = mujoco.MjModel.from_xml_string("<mujoco/>")
    d: mujoco.MjData = mujoco.MjData(m)

    test_values: dict[str, float] = {
        "Temperature": 25.5,
        "Pressure": 101.3,
        "Velocity": 42.0,
    }

    for signal_name, value in test_values.items():
        sm.post(value, "Sensors", (signal_name,))

    sm.record(MjState(m, d))
    sm.flush()

    df: pl.DataFrame = pl.read_parquet(sm.export_path)

    for signal_name, expected_value in test_values.items():
        signal_key = f"Sensors/{signal_name}"
        assert signal_key in df.columns
        actual_value = df[signal_key][0]
        assert abs(float(actual_value) - expected_value) < 1e-10


def test_cache_hit_performance(sm: SignalManager) -> None:
    """Verify that repeated signal names use cache instead of recomputing."""
    # Post same signal 3 times
    sm.post(1.0, "Category", ("Sub",), attr="attr")
    initial_cache_size: int = len(sm._key_cache)

    sm.post(2.0, "Category", ("Sub",), attr="attr")
    sm.post(3.0, "Category", ("Sub",), attr="attr")

    # Cache should not have grown
    assert len(sm._key_cache) == initial_cache_size
    # But all values should be in key_to_idx
    assert "Category/Sub:attr" in sm._key_to_idx


def test_append_to_existing_file(sm: SignalManager) -> None:
    """Verify diagonal concat when appending to existing parquet file."""
    m: mujoco.MjModel = mujoco.MjModel.from_xml_string("<mujoco/>")
    d: mujoco.MjData = mujoco.MjData(m)

    # Write first batch
    sm.post(1.0, "Signal", ("A",))
    sm.record(MjState(m, d))
    sm.post(2.0, "Signal", ("A",))
    sm.record(MjState(m, d))
    sm.post(3.0, "Signal", ("A",))
    sm.record(MjState(m, d))
    sm.post(4.0, "Signal", ("A",))
    sm.record(MjState(m, d))
    sm.post(5.0, "Signal", ("A",))
    sm.record(MjState(m, d))
    sm.flush()

    initial_df: pl.DataFrame = pl.read_parquet(sm.export_path)
    assert initial_df.height == 5

    # Add a new signal and write another batch (should append to existing file)
    sm.post(10.0, "Signal", ("A",))
    sm.post(20.0, "Signal", ("B",))  # New signal
    sm.record(MjState(m, d))
    sm.post(11.0, "Signal", ("A",))
    sm.post(21.0, "Signal", ("B",))
    sm.record(MjState(m, d))
    sm.post(12.0, "Signal", ("A",))
    sm.post(22.0, "Signal", ("B",))
    sm.record(MjState(m, d))
    sm.flush()

    # Verify file was appended to
    appended_df: pl.DataFrame = pl.read_parquet(sm.export_path)
    assert appended_df.height == 8  # 5 + 3 new rows
    assert "Signal/B" in appended_df.columns


def test_empty_flush_early_return(sm: SignalManager) -> None:
    """Verify that flush returns early when buffer is empty."""
    # Don't post or record anything, just try to flush
    assert sm._buffer_row_idx == 0
    sm.flush()

    # File should not be created
    assert not sm.export_path.exists()


def test_properties_and_static_methods(sm: SignalManager) -> None:
    """Verify property and static method correctness."""
    assert sm.db_name == "telemetry.parquet"
    assert sm.table_name == "result"
    assert SignalManager.default_output_name() == "telemetry.parquet"
    assert SignalManager.default_table_name() == "result"
