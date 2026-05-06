import polars as pl
import pytest

from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.stochas import NamedValue, ValueName
from mujoco_mojo.utils.defaults import TIME_COLUMN_NAME


@pytest.fixture
def sm(tmp_path):
    """Provides a SignalManager pointing to a temporary directory."""
    db_file = tmp_path / "test_telemetry.parquet"
    manager = SignalManager(export_path=db_file, batch_size=5)
    yield manager
    # Ensure connection is closed so the file isn't locked
    try:
        manager.close()
    except Exception:
        pass


def test_hierarchical_key_generation(sm: SignalManager):
    """Verify the 'Category/Subgroup:Attribute' naming logic."""
    # Test full path
    sm.post(1.0, "Bodies", ("Hand",), attr="xpos_x")
    assert "Bodies/Hand:xpos_x" in sm.ledger

    # Test simple path (no attr)
    sm.post(2.0, "Sensors", ("IMU",))
    assert "Sensors/IMU" in sm.ledger

    # Test NamedValue integration
    nv = NamedValue(name=ValueName("Elbow"), stored_value=0.4)
    sm.post(nv, "Joints", attr="qpos")
    assert "Joints/Elbow:qpos" in sm.ledger


def test_batching_and_persistence(sm: SignalManager):
    """Verify data is only committed to output after reaching batch_size."""
    # We need a mock MjModel/Data for the record call
    import mujoco

    m = mujoco.MjModel.from_xml_string("<mujoco/>")
    d = mujoco.MjData(m)

    # Post 4 steps (Batch size is 5)
    for i in range(4):
        sm.post(float(i), "Custom", ("Signal",))
        sm.record(m, d)
        sm.flush_ledger()

    # Buffer should have 4 rows, but output table shouldn't exist/be empty yet
    assert len(sm._buffer) == 4

    # 5th step triggers flush
    sm.post(4.0, "Custom", ("Signal",))
    sm.record(m, d)

    assert len(sm._buffer) == 0  # Buffer cleared

    # Verify output has the data
    df = pl.read_parquet(sm.export_path)
    assert df.height == 5
    assert TIME_COLUMN_NAME in df.columns


def test_record_decimation(sm: SignalManager):
    """Verify that decimation correctly skips steps."""
    import mujoco

    m = mujoco.MjModel.from_xml_string("<mujoco/>")
    d = mujoco.MjData(m)

    sm.record_decimation = 3  # Record every 3rd step

    # Step 0: Records (step_count starts at -1, becomes 0)
    sm.record(m, d)
    assert len(sm._buffer) == 1

    # Step 1 & 2: Skip
    sm.record(m, d)
    sm.record(m, d)
    assert len(sm._buffer) == 1

    # Step 3: Records
    sm.record(m, d)
    assert len(sm._buffer) == 2


def test_sample_task_execution(sm: SignalManager):
    """Verify that scheduled sample tasks fire during record()."""
    import mujoco

    m = mujoco.MjModel.from_xml_string("<mujoco/>")
    d = mujoco.MjData(m)

    was_called = False

    def mock_sample(model, data):
        nonlocal was_called
        sm.post(99.0, "Custom", ("Sampled",))
        was_called = True

    sm.register_sampler(mock_sample)
    sm.record(m, d)

    assert was_called
    assert "Custom/Sampled" in sm._buffer[0]
