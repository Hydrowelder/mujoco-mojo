import polars as pl
import pytest

from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.stochas import NamedValue, ValueName


@pytest.fixture
def rm(tmp_path):
    """Provides a SignalManager pointing to a temporary directory."""
    db_file = tmp_path / "test_telemetry.parquet"
    manager = SignalManager(export_path=db_file, batch_size=5)
    yield manager
    # Ensure connection is closed so the file isn't locked
    try:
        manager.close()
    except Exception:
        pass


def test_hierarchical_key_generation(rm: SignalManager):
    """Verify the 'Category/Subgroup:Attribute' naming logic."""
    # Test full path
    rm.post(1.0, "Bodies", "Hand", "xpos_x")
    assert "Bodies/Hand:xpos_x" in rm.ledger

    # Test simple path (no attr)
    rm.post(2.0, "Sensors", "IMU")
    assert "Sensors/IMU" in rm.ledger

    # Test NamedValue integration
    nv = NamedValue(name=ValueName("Elbow"), stored_value=0.4)
    rm.post(nv, "Joints", attr="qpos")
    assert "Joints/Elbow:qpos" in rm.ledger


def test_batching_and_persistence(rm: SignalManager):
    """Verify data is only committed to output after reaching batch_size."""
    # We need a mock MjModel/Data for the record call
    import mujoco

    m = mujoco.MjModel.from_xml_string("<mujoco/>")
    d = mujoco.MjData(m)

    # Post 4 steps (Batch size is 5)
    for i in range(4):
        rm.post(float(i), "Custom", "Signal")
        rm.record(m, d)
        rm.flush_ledger()

    # Buffer should have 4 rows, but output table shouldn't exist/be empty yet
    assert len(rm._buffer) == 4

    # 5th step triggers flush
    rm.post(4.0, "Custom", "Signal")
    rm.record(m, d)

    assert len(rm._buffer) == 0  # Buffer cleared

    # Verify output has the data
    df = pl.read_parquet(rm.export_path)
    assert df.height == 5
    assert "time" in df.columns


def test_record_decimation(rm: SignalManager):
    """Verify that decimation correctly skips steps."""
    import mujoco

    m = mujoco.MjModel.from_xml_string("<mujoco/>")
    d = mujoco.MjData(m)

    rm.record_decimation = 3  # Record every 3rd step

    # Step 0: Records (step_count starts at -1, becomes 0)
    rm.record(m, d)
    assert len(rm._buffer) == 1

    # Step 1 & 2: Skip
    rm.record(m, d)
    rm.record(m, d)
    assert len(rm._buffer) == 1

    # Step 3: Records
    rm.record(m, d)
    assert len(rm._buffer) == 2


def test_harvest_task_execution(rm: SignalManager):
    """Verify that scheduled harvest tasks fire during record()."""
    import mujoco

    m = mujoco.MjModel.from_xml_string("<mujoco/>")
    d = mujoco.MjData(m)

    was_called = False

    def mock_harvest(model, data):
        nonlocal was_called
        rm.post(99.0, "Custom", "Harvested")
        was_called = True

    rm.schedule_harvest_task(mock_harvest)
    rm.record(m, d)

    assert was_called
    assert "Custom/Harvested" in rm._buffer[0]
