from unittest.mock import MagicMock, patch

import mujoco
import numpy as np

from mujoco_mojo.runtime.load import Load
from mujoco_mojo.runtime.results_manager import ResultsManager
from mujoco_mojo.runtime.runtime_manager import RuntimeManager


class MockLoad(Load):
    """Minimal implementation of the abstract Load class for testing."""

    def calculate(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        # Apply a constant 10N force in world X
        return np.array([10.0, 0, 0]), np.zeros(3)


def test_runtime_manager_lifecycle(rm: ResultsManager):
    """Verify that __enter__ and __exit__ handle cleanup correctly."""
    # Patch close to ensure it's called
    with patch.object(rm, "close") as mock_close:
        with RuntimeManager(results_manager=rm) as mgr:
            assert mgr._resolved is False

        # Verify close was called on exit
        mock_close.assert_called_once()


def test_resolution_on_first_step(
    mj_setup: tuple[mujoco.MjModel, mujoco.MjData], rm: ResultsManager
):
    """Verify that resolve() is automatically called during the first step."""
    model, data = mj_setup
    mgr = RuntimeManager(results_manager=rm)

    # Add a mock load
    load: Load = MagicMock(spec=Load)
    mgr.add_load(load)

    # First step
    mgr.step(model, data)

    assert mgr._resolved is True
    load.resolve_ids.assert_called_once_with(model, data)


def test_buffer_clearing_hygiene(
    mj_setup: tuple[mujoco.MjModel, mujoco.MjData], rm: ResultsManager
):
    """CRITICAL: Verify that step() clears the applied force buffers."""
    model, data = mj_setup
    mgr = RuntimeManager(results_manager=rm)

    # Manually dirty the buffers
    data.qfrc_applied[0] = 50.0
    data.xfrc_applied[1, 0] = 50.0  # Index 1 is 'body1' (Index 0 is world)
    data.ctrl[0] = 1.0

    mgr.step(model, data)

    # Assertions
    assert np.all(data.qfrc_applied == 0), "qfrc_applied was not cleared"
    assert np.all(data.xfrc_applied == 0), "xfrc_applied was not cleared"
    assert np.all(data.ctrl == 0), "ctrl was not cleared"


def test_video_capture_with_arrows(mj_setup: tuple[mujoco.MjModel, mujoco.MjData]):
    """Verify that recorder captures frames and requests visuals from loads."""
    model, data = mj_setup

    # Mock a recorder and a load
    mock_recorder = MagicMock()
    mock_load: Load = MagicMock(spec=Load)
    mock_load.get_visuals.return_value = [{"pos": [0, 0, 0], "vec": [1, 1, 1]}]

    mgr = RuntimeManager()
    mgr.add_load(mock_load)
    mgr.add_video_recorder(mock_recorder)

    mgr.step(model, data)

    # Ensure capture_frame was called with the arrows from the load
    mock_recorder.capture_frame.assert_called_once()
    _args, kwargs = mock_recorder.capture_frame.call_args
    assert "custom_arrows" in kwargs
    assert len(kwargs["custom_arrows"]) == 1


@patch("mujoco_mojo.runtime.runtime_manager.ThreadPoolExecutor")
def test_parallel_video_save(mock_executor_cls, rm: ResultsManager):
    """Verify that save_recordings uses parallel execution."""
    mock_recorder = MagicMock()
    mgr = RuntimeManager(video_recorders=[mock_recorder])

    mgr.save_recordings()

    # Verify ThreadPoolExecutor was used
    mock_executor = mock_executor_cls.return_value.__enter__.return_value
    assert mock_executor.submit.called
