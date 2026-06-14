from unittest.mock import MagicMock, patch

import mujoco
import numpy as np

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import GeomMesh
from mujoco_mojo.runtime.load import Load
from mujoco_mojo.runtime.runtime_manager import RuntimeManager
from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.typing import GeomName, MeshName
from mujoco_mojo.utils.proximity import Proximity


class MockLoad(Load):
    """Minimal concrete Load for testing the abstract base."""

    def resolve_ids(self, state: MjState) -> None:
        pass

    def apply_load(self, state: MjState) -> None:
        pass


def test_runtime_manager_lifecycle(rm: SignalManager):
    """Verify that __enter__ and __exit__ handle cleanup correctly."""
    # Patch close to ensure it's called
    with patch.object(rm, "close") as mock_close:
        with RuntimeManager(signal_manager=rm) as mgr:
            assert mgr._resolved is False

        # Verify close was called on exit
        mock_close.assert_called_once()


def test_resolution_on_first_step(mj_setup, rm: SignalManager):
    """Verify that resolve() is automatically called during the first step."""
    model, data = mj_setup
    state = MjState(model, data)
    mgr = RuntimeManager(signal_manager=rm)

    # Add a mock load
    load: Load = MagicMock(spec=Load)
    mgr.add_load(load)

    # First step
    mgr.step(state)

    assert mgr._resolved is True
    load.resolve_ids.assert_called_once_with(state)


def test_buffer_clearing_hygiene(mj_setup):
    """CRITICAL: Verify that step() clears the applied force buffers."""
    model, data = mj_setup
    state = MjState(model, data)
    mgr = RuntimeManager(signal_manager=None)

    # Manually dirty the buffers
    data.qfrc_applied[0] = 50.0
    data.xfrc_applied[1, 0] = 50.0  # Index 1 is 'body1' (Index 0 is world)
    data.ctrl[0] = 1.0

    mgr.step(state)

    # Assertions
    assert np.all(data.qfrc_applied == 0), "qfrc_applied was not cleared"
    assert np.all(data.xfrc_applied == 0), "xfrc_applied was not cleared"
    assert np.all(data.ctrl == 0), "ctrl was not cleared"


def test_video_capture_with_arrows(mj_setup):
    """Verify that recorder captures frames and requests visuals from loads."""
    model, data = mj_setup
    state = MjState(model, data)

    # Mock a recorder and a load
    mock_recorder = MagicMock()
    mock_load: Load = MagicMock(spec=Load)
    mock_load.get_visuals.return_value = [{"pos": [0, 0, 0], "vec": [1, 1, 1]}]

    mgr = RuntimeManager()
    mgr.add_load(mock_load)
    mgr.add_video_recorder(mock_recorder)

    mgr.step(state)

    # Ensure capture_frame was called with the arrows from the load
    mock_recorder.capture_frame.assert_called_once()
    _args, kwargs = mock_recorder.capture_frame.call_args
    assert "custom_arrows" in kwargs
    assert len(kwargs["custom_arrows"]) == 1


@patch("mujoco_mojo.runtime.runtime_manager.ThreadPoolExecutor")
def test_parallel_video_save(mock_executor_cls, rm: SignalManager):
    """Verify that save_recordings uses parallel execution."""
    mock_recorder = MagicMock()
    mgr = RuntimeManager(video_recorders=[mock_recorder])

    mgr.save_recordings()

    # Verify ThreadPoolExecutor was used
    mock_executor = mock_executor_cls.return_value.__enter__.return_value
    assert mock_executor.submit.called


def test_add_load_warns_on_duplicate_name(caplog):
    """add_load logs a warning when the same load name is registered twice."""
    mgr = RuntimeManager()
    load_a: Load = MagicMock(spec=Load)
    load_a.name = "my_force"
    load_b: Load = MagicMock(spec=Load)
    load_b.name = "my_force"

    mgr.add_load(load_a)
    with caplog.at_level("WARNING"):
        mgr.add_load(load_b)

    assert any("my_force" in r.message for r in caplog.records)
    assert len(mgr.loads) == 2


def test_add_proximity_warns_on_duplicate_pair(caplog):
    """add_proximity logs a warning when the same geom pair is registered twice."""
    mgr = RuntimeManager()
    g1 = GeomMesh(name=GeomName("geom_a"), mesh=MeshName("mesh_a"))
    g2 = GeomMesh(name=GeomName("geom_b"), mesh=MeshName("mesh_b"))

    p1 = Proximity(geom_1=g1, geom_2=g2, dist_max=1.0)
    p2 = Proximity(geom_1=g1, geom_2=g2, dist_max=1.0)

    mgr.add_proximity(p1)
    with caplog.at_level("WARNING"):
        mgr.add_proximity(p2)

    assert any("geom_a" in r.message or "geom_b" in r.message for r in caplog.records)
    assert len(mgr.proximities) == 2


def test_exit_closes_signal_manager(rm: SignalManager):
    """__exit__ calls close() on the signal_manager."""
    with patch.object(rm, "close") as mock_close:
        with RuntimeManager(signal_manager=rm):
            pass
        mock_close.assert_called_once()


def test_step_records_via_signal_manager(mj_setup, rm: SignalManager):
    """step() calls signal_manager.record() when a signal_manager is attached."""
    model, data = mj_setup
    state = MjState(model, data)

    with patch.object(rm, "record") as mock_record:
        mgr = RuntimeManager(signal_manager=rm)
        mgr.step(state)
        mock_record.assert_called_once_with(state)


def test_step_calls_sync_hook(mj_setup: tuple[mujoco.MjModel, mujoco.MjData]) -> None:
    """step() invokes _sync_hook with (state, arrows, lines) after physics integration."""
    model, data = mj_setup
    state = MjState(model, data)

    hook = MagicMock()
    mgr = RuntimeManager(_sync_hook=hook, playback_speed=0)
    mgr.step(state)

    hook.assert_called_once()
    call_args = hook.call_args[0]
    assert call_args[0] is state
    assert isinstance(call_args[1], list)  # arrows
    assert isinstance(call_args[2], list)  # lines


@patch("mujoco_mojo.runtime.runtime_manager.ThreadPoolExecutor")
def test_exit_saves_recordings_when_present(
    mock_executor_cls: MagicMock, rm: SignalManager
) -> None:
    """__exit__ calls save_recordings() when video_recorders is non-empty."""
    mock_recorder = MagicMock()
    with RuntimeManager(signal_manager=rm, video_recorders=[mock_recorder]):
        pass

    mock_executor = mock_executor_cls.return_value.__enter__.return_value
    assert mock_executor.submit.called


def test_step_calls_proximity_get_visuals(
    mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
) -> None:
    """step() calls get_visuals on registered proximities when a sync_hook is set."""
    model, data = mj_setup
    state = MjState(model, data)

    mock_proximity = MagicMock()
    mock_proximity.get_visuals.return_value = None  # no line returned

    hook = MagicMock()
    mgr = RuntimeManager(_sync_hook=hook, playback_speed=0)
    mgr.proximities.append(mock_proximity)
    mgr.step(state)

    mock_proximity.get_visuals.assert_called_once_with(state, mgr.signal_manager)
