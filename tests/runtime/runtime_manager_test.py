import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import mujoco
import numpy as np
import polars as pl
import pytest

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.body_attr.geom import GeomMesh
from mujoco_mojo.mjcf.mujoco_attr.body_attr.joint import Joint
from mujoco_mojo.runtime.load import JointFriction, Load
from mujoco_mojo.runtime.runtime_manager import RuntimeManager
from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.typing import GeomName, JointName, MeshName
from mujoco_mojo.utils.proximity import Proximity
from mujoco_mojo.utils.statusing import RequirementResult, TrialStatus


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


def test_buffer_clearing_is_individually_disableable(mj_setup):
    """Each buffer's clearing can be disabled independently via step() arguments."""
    model, data = mj_setup
    state = MjState(model, data)
    mgr = RuntimeManager(signal_manager=None)

    data.qfrc_applied[0] = 50.0
    data.xfrc_applied[1, 0] = 50.0
    data.ctrl[0] = 1.0

    mgr.step(
        state,
        clear_xfrc_applied=False,
        clear_qfrc_applied=False,
        clear_ctrl=False,
    )

    assert data.qfrc_applied[0] == pytest.approx(50.0), "qfrc_applied was cleared"
    assert data.xfrc_applied[1, 0] == pytest.approx(50.0), "xfrc_applied was cleared"
    assert data.ctrl[0] == pytest.approx(1.0), "ctrl was cleared"


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


def _karnopp_load() -> JointFriction:
    return JointFriction.karnopp(
        name="k",
        joint=Joint(name=JointName("joint1")),
        mu_kinetic=0.3,
        mu_static=0.5,
        velocity_threshold=0.01,
    )


def test_rne_post_constraint_not_called_when_nothing_reads_it(
    mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
) -> None:
    """step() never calls mj_rnePostConstraint on its own; it's only triggered lazily by an accessor that reads cfrc_int/cacc."""
    model, data = mj_setup
    state = MjState(model, data)
    mgr = RuntimeManager()

    with patch(
        "mujoco_mojo.runtime.runtime_manager.mujoco.mj_rnePostConstraint"
    ) as mock_rne:
        mgr.step(state)
    mock_rne.assert_not_called()


def test_rne_post_constraint_called_once_when_karnopp_applies_load(
    mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
) -> None:
    """A karnopp friction load reads Joint.rt_bearing_load during apply_load, which lazily triggers mj_rnePostConstraint exactly once per step."""
    model, data = mj_setup
    state = MjState(model, data)
    mgr = RuntimeManager()
    mgr.add_load(_karnopp_load())

    with patch(
        "mujoco_mojo.runtime.runtime_manager.mujoco.mj_rnePostConstraint",
        wraps=mujoco.mj_rnePostConstraint,
    ) as mock_rne:
        mgr.step(state)
    mock_rne.assert_called_once_with(state.model, state.data)


def test_rne_post_constraint_invalidated_for_next_step(
    mj_setup: tuple[mujoco.MjModel, mujoco.MjData],
) -> None:
    """The freshness flag is invalidated by step()'s mj_forward/mj_step calls, so a second step() re-triggers mj_rnePostConstraint rather than reusing stale data."""
    model, data = mj_setup
    state = MjState(model, data)
    mgr = RuntimeManager()
    mgr.add_load(_karnopp_load())

    with patch(
        "mujoco_mojo.runtime.runtime_manager.mujoco.mj_rnePostConstraint",
        wraps=mujoco.mj_rnePostConstraint,
    ) as mock_rne:
        mgr.step(state)
        mgr.step(state)
    assert mock_rne.call_count == 2


# --- Requirements checker ---


def test_requirements_passed_none_when_empty() -> None:
    """requirements_passed is None when no requirements were registered."""
    status = TrialStatus(trial_num=0)
    assert status.requirements_passed is None


def test_requirements_passed_true_when_all_pass() -> None:
    """requirements_passed is True when every result has passed=True."""
    status = TrialStatus(
        trial_num=0,
        requirements=[
            RequirementResult(name="a", passed=True, message="ok"),
            RequirementResult(name="b", passed=True, message="also ok"),
        ],
    )
    assert status.requirements_passed is True


def test_requirements_passed_false_when_any_fail() -> None:
    """requirements_passed is False when at least one result has passed=False."""
    status = TrialStatus(
        trial_num=0,
        requirements=[
            RequirementResult(name="a", passed=True, message="ok"),
            RequirementResult(name="b", passed=False, message="nope"),
        ],
    )
    assert status.requirements_passed is False


def test_requirements_round_trip_through_json(tmp_path: Path) -> None:
    """Requirements survive a model_dump_json/model_validate_json round-trip."""
    status = TrialStatus(
        trial_num=0,
        requirements=[RequirementResult(name="q", passed=True, message="good")],
    )
    restored = TrialStatus.model_validate_json(status.model_dump_json())
    assert len(restored.requirements) == 1
    assert restored.requirements[0].name == "q"
    assert restored.requirements_passed is True


def test_add_requirement_registers_fn() -> None:
    """add_requirement registers fn under its name in _requirements."""
    mgr = RuntimeManager()

    def fn(m, s, df):
        return True, "ok"

    mgr.add_requirement(fn, name="my_check")

    assert len(mgr._requirements) == 1
    assert mgr._requirements["my_check"].name == "my_check"
    assert mgr._requirements["my_check"].fn is fn


def test_add_requirement_rejects_duplicate_name() -> None:
    """Registering two requirements under the same name raises ValueError instead of silently overwriting or duplicating."""
    mgr = RuntimeManager()

    mgr.add_requirement(lambda m, s, df: (True, "ok"), name="dup")
    with pytest.raises(ValueError, match="dup"):
        mgr.add_requirement(lambda m, s, df: (True, "ok again"), name="dup")

    assert len(mgr._requirements) == 1


def test_requirement_decorator_registers_and_returns_fn() -> None:
    """@rm.requirement() registers the function and returns it unchanged."""
    mgr = RuntimeManager()

    @mgr.requirement("decorated")
    def check(model, state, df):
        return True, "decorated ok"

    assert len(mgr._requirements) == 1
    assert mgr._requirements["decorated"].name == "decorated"
    # the decorator must return the original function unchanged (not a wrapper)
    assert mgr._requirements["decorated"].fn is check


def test_evaluate_requirements_stores_results_and_writes_json(tmp_path: Path) -> None:
    """_evaluate_requirements reads the parquet, calls each fn, stores results, and writes requirements.json."""
    parquet_path = tmp_path / "telemetry.parquet"
    pl.DataFrame({"time": [0.0, 1.0], "Signal/A": [1.0, 2.0]}).write_parquet(
        parquet_path
    )

    sm = MagicMock(spec=SignalManager)
    sm.export_path = parquet_path
    mgr = RuntimeManager(signal_manager=sm)
    mgr._mojo_model = MagicMock()
    mgr._last_state = MagicMock()
    mgr.add_requirement(lambda m, s, df: (True, "height ok"), name="height_check")
    mgr.add_requirement(lambda m, s, df: (False, "speed too low"), name="speed_check")

    mgr._evaluate_requirements()

    assert len(mgr.requirement_results) == 2
    r0, r1 = mgr.requirement_results
    assert r0.name == "height_check" and r0.passed is True and r0.message == "height ok"
    assert (
        r1.name == "speed_check"
        and r1.passed is False
        and r1.message == "speed too low"
    )

    saved = json.loads((tmp_path / "requirements.json").read_text())
    assert [
        {"name": r["name"], "passed": r["passed"], "message": r["message"]}
        for r in saved
    ] == [
        {"name": "height_check", "passed": True, "message": "height ok"},
        {"name": "speed_check", "passed": False, "message": "speed too low"},
    ]
    # config metadata (every/terminate/latch) and decided_at are also persisted
    assert all(
        {
            "decided_at",
            "every",
            "terminate_on_fail",
            "terminate_on_pass",
            "latch_on_fail",
            "latch_on_pass",
        }
        <= r.keys()
        for r in saved
    )


def test_requirement_fn_receives_model_and_dataframe(tmp_path: Path) -> None:
    """_evaluate_requirements passes _mojo_model and a MojoDataFrame to each fn."""
    parquet_path = tmp_path / "telemetry.parquet"
    pl.DataFrame({"time": [0.0], "Signal/A": [42.0]}).write_parquet(parquet_path)

    sm = MagicMock(spec=SignalManager)
    sm.export_path = parquet_path
    fake_model = MagicMock()
    captured: list[tuple] = []

    mgr = RuntimeManager(signal_manager=sm)
    mgr._mojo_model = fake_model
    mgr._last_state = MagicMock()
    mgr.add_requirement(
        lambda m, s, df: captured.append((m, df)) or (True, "ok"), name="capture"
    )

    mgr._evaluate_requirements()

    assert len(captured) == 1
    assert captured[0][0] is fake_model
    # df should contain the column we wrote
    received_df = captured[0][1]
    assert "Signal/A" in received_df.columns
    assert received_df["Signal/A"][0] == pytest.approx(42.0)


def test_requirement_exception_recorded_as_failure(tmp_path: Path) -> None:
    """When a requirement fn raises, the exception is caught and recorded as passed=False."""
    parquet_path = tmp_path / "telemetry.parquet"
    pl.DataFrame({"time": [0.0]}).write_parquet(parquet_path)

    sm = MagicMock(spec=SignalManager)
    sm.export_path = parquet_path
    mgr = RuntimeManager(signal_manager=sm)
    mgr._mojo_model = MagicMock()
    mgr._last_state = MagicMock()

    def bad_check(model, state, df):
        raise ValueError("boom")

    mgr.add_requirement(bad_check, name="bad")
    mgr._evaluate_requirements()

    assert len(mgr.requirement_results) == 1
    result = mgr.requirement_results[0]
    assert result.passed is False
    assert "ValueError" in result.message
    assert "boom" in result.message


def test_exit_evaluates_requirements_on_success(tmp_path: Path) -> None:
    """__exit__ evaluates requirements when the simulation completes without an exception."""
    parquet_path = tmp_path / "telemetry.parquet"
    pl.DataFrame({"time": [0.0]}).write_parquet(parquet_path)

    sm = MagicMock(spec=SignalManager)
    sm.export_path = parquet_path
    check_called: list[bool] = []

    with RuntimeManager(signal_manager=sm) as mgr:
        mgr._mojo_model = MagicMock()
        mgr._last_state = MagicMock()
        mgr.add_requirement(
            lambda m, s, df: check_called.append(True) or (True, "ok"), name="check"
        )

    assert check_called
    assert len(mgr.requirement_results) == 1


def test_exit_skips_requirements_on_simulation_exception(rm: SignalManager) -> None:
    """__exit__ does not evaluate requirements when the simulation raised an exception."""
    check_called: list[bool] = []

    mgr = RuntimeManager(signal_manager=rm)
    mgr.__enter__()
    mgr._mojo_model = MagicMock()
    mgr.add_requirement(
        lambda m, s, df: check_called.append(True) or (True, "ok"), name="check"
    )
    mgr.__exit__(RuntimeError, RuntimeError("sim failed"), None)

    assert not check_called
    assert len(mgr.requirement_results) == 0


def test_exit_skips_requirements_without_mojo_model(rm: SignalManager) -> None:
    """__exit__ does not evaluate requirements when _mojo_model was never set."""
    check_called: list[bool] = []

    with RuntimeManager(signal_manager=rm) as mgr:
        mgr.add_requirement(
            lambda m, s, df: check_called.append(True) or (True, "ok"), name="check"
        )
        # _mojo_model intentionally left as None

    assert not check_called
    assert len(mgr.requirement_results) == 0


def test_live_failure_marks_requirement_failed_at_end_of_trial(tmp_path: Path) -> None:
    """A live requirement that fails at any point during the run is failed for the trial, even if its end-of-trial evaluation passes."""
    parquet_path = tmp_path / "telemetry.parquet"
    pl.DataFrame({"time": [0.0]}).write_parquet(parquet_path)

    sm = MagicMock(spec=SignalManager)
    sm.export_path = parquet_path
    mgr = RuntimeManager(signal_manager=sm)
    mgr._mojo_model = MagicMock()

    live_results = iter([True, False, True])

    def flaky(model, state, df):
        if df is None:
            return next(live_results), "live check"
        return True, "recovered by end of trial"

    mgr.add_requirement(flaky, name="flaky", every=1)

    for sim_time in (0.1, 0.2, 0.3):
        state = MagicMock()
        state.data.time = sim_time
        mgr.requirements.step(state, signal_manager=None, mojo_model=mgr._mojo_model)

    mgr._last_state = state
    mgr._evaluate_requirements()

    result = mgr.requirement_results[0]
    assert result.passed is False
    assert "1/3 live checks" in result.message
    assert "t=0.200000" in result.message
    assert "end-of-trial evaluation passed" in result.message


def test_live_passes_keep_end_of_trial_result(tmp_path: Path) -> None:
    """A live requirement that never fails during the run keeps its end-of-trial result."""
    parquet_path = tmp_path / "telemetry.parquet"
    pl.DataFrame({"time": [0.0]}).write_parquet(parquet_path)

    sm = MagicMock(spec=SignalManager)
    sm.export_path = parquet_path
    mgr = RuntimeManager(signal_manager=sm)
    mgr._mojo_model = MagicMock()

    mgr.add_requirement(lambda m, s, df: (True, "always ok"), name="steady", every=1)

    state = MagicMock()
    state.data.time = 0.1
    mgr.requirements.step(state, signal_manager=None, mojo_model=mgr._mojo_model)

    mgr._last_state = state
    mgr._evaluate_requirements()

    result = mgr.requirement_results[0]
    assert result.passed is True
    assert result.message == "always ok"


def test_undetermined_live_results_excluded_from_failure_count(tmp_path: Path) -> None:
    """None verdicts are cached but excluded from the failed-live-checks count and denominator in the end-of-trial message, even though they sit in _live_cache alongside True/False entries."""
    parquet_path = tmp_path / "telemetry.parquet"
    pl.DataFrame({"time": [0.0]}).write_parquet(parquet_path)

    sm = MagicMock(spec=SignalManager)
    sm.export_path = parquet_path
    mgr = RuntimeManager(signal_manager=sm)
    mgr._mojo_model = MagicMock()

    # 5 live evaluations: None, True, False, None, True -- only the 3
    # determinate ones (True, False, True) should count as "live checks"
    live_results = iter([None, True, False, None, True])

    def flaky(model, state, df):
        if df is None:
            return next(live_results), "live check"
        return True, "recovered by end of trial"

    mgr.add_requirement(flaky, name="flaky", every=1)

    for sim_time in (0.1, 0.2, 0.3, 0.4, 0.5):
        state = MagicMock()
        state.data.time = sim_time
        mgr.requirements.step(state, signal_manager=None, mojo_model=mgr._mojo_model)

    # all 5 evaluations are cached, including the undetermined ones
    assert len(mgr.requirements._live_cache) == 5
    assert mgr.requirements._live_cache[("flaky", 0.1)] is None
    assert mgr.requirements._live_cache[("flaky", 0.4)] is None

    mgr._last_state = state
    mgr._evaluate_requirements()

    result = mgr.requirement_results[0]
    assert result.passed is False
    # 1 failure out of 3 determinate checks, not 1/5
    assert "1/3 live checks" in result.message


def test_last_passed_accepts_function_handle() -> None:
    """last_passed resolves a registered function object to its name, matching what passing the name directly would return."""
    mgr = RuntimeManager()
    mgr._mojo_model = MagicMock()

    @mgr.requirement(every=1)
    def upright(model, state, df):
        return state.data.time > 0.05, "ok"

    state = MagicMock()
    state.data.time = 0.1
    mgr.requirements.step(state, signal_manager=None, mojo_model=mgr._mojo_model)

    assert mgr.last_passed(upright, state) is True
    assert mgr.last_passed(upright, state) == mgr.last_passed("upright", state)


def test_last_passed_rejects_unregistered_function() -> None:
    """last_passed raises ValueError for a function that was never registered, rather than silently returning None."""
    mgr = RuntimeManager()

    def never_registered(model, state, df):
        return True, "ok"

    with pytest.raises(ValueError, match="never_registered"):
        mgr.last_passed(never_registered, MagicMock())


def test_undetermined_live_result_is_cached_but_otherwise_a_no_op() -> None:
    """A live check returning None is recorded in _live_cache (so a lookup at this sim time is a hit), but never latches a failure or posts telemetry."""
    mgr = RuntimeManager()
    mgr._mojo_model = MagicMock()

    mgr.add_requirement(
        lambda m, s, df: (None, "no verdict yet"), name="pending_goal", every=1
    )

    state = MagicMock()
    state.data.time = 0.1
    sm = MagicMock(spec=SignalManager)
    mgr.requirements.step(state, signal_manager=sm, mojo_model=mgr._mojo_model)

    assert mgr.last_passed("pending_goal", state) is None
    assert mgr.requirements._live_cache[("pending_goal", 0.1)] is None
    assert mgr.requirements._first_live_failure == {}
    sm.post.assert_not_called()


def test_undetermined_at_end_of_trial_is_a_failure(tmp_path: Path) -> None:
    """A requirement still returning None at end of trial is recorded as failed."""
    parquet_path = tmp_path / "telemetry.parquet"
    pl.DataFrame({"time": [0.0]}).write_parquet(parquet_path)

    sm = MagicMock(spec=SignalManager)
    sm.export_path = parquet_path
    mgr = RuntimeManager(signal_manager=sm)
    mgr._mojo_model = MagicMock()
    mgr._last_state = MagicMock()
    mgr.add_requirement(lambda m, s, df: (None, "never happened"), name="never_decided")

    mgr._evaluate_requirements()

    result = mgr.requirement_results[0]
    assert result.passed is False
    assert "undetermined at end of trial" in result.message


def test_terminate_on_pass_raises_requirement_satisfied() -> None:
    """A live check with terminate_on_pass=True raises RequirementSatisfied when it passes, but not while undetermined."""
    from mujoco_mojo.runtime.requirements_manager import RequirementSatisfied

    mgr = RuntimeManager()
    mgr._mojo_model = MagicMock()

    verdicts = iter([None, True])
    mgr.add_requirement(
        lambda m, s, df: (next(verdicts), "goal check"),
        name="reached_goal",
        every=1,
        terminate_on_pass=True,
    )

    state = MagicMock()
    state.data.time = 0.1
    mgr.requirements.step(
        state, signal_manager=None, mojo_model=mgr._mojo_model
    )  # None: no raise

    state.data.time = 0.2
    with pytest.raises(RequirementSatisfied, match="reached_goal"):
        mgr.requirements.step(state, signal_manager=None, mojo_model=mgr._mojo_model)


def test_terminate_failure_wins_over_pass_on_same_step() -> None:
    """When a failing terminator and a passing one fire on the same step, RequirementTerminated wins."""
    from mujoco_mojo.runtime.requirements_manager import RequirementTerminated

    mgr = RuntimeManager()
    mgr._mojo_model = MagicMock()

    mgr.add_requirement(
        lambda m, s, df: (True, "done"), name="goal", every=1, terminate_on_pass=True
    )
    mgr.add_requirement(
        lambda m, s, df: (False, "fell"),
        name="upright",
        every=1,
        terminate_on_fail=True,
    )

    state = MagicMock()
    state.data.time = 0.1
    with pytest.raises(RequirementTerminated, match="upright"):
        mgr.requirements.step(state, signal_manager=None, mojo_model=mgr._mojo_model)


def test_latch_on_fail_stops_calling_fn_after_first_failure() -> None:
    """latch_on_fail=True stops calling the check function once it fails, at both live and end-of-trial evaluation."""
    calls: list[float] = []

    def flaky(model, state, df):
        calls.append(state.data.time)
        return state.data.time < 0.25, "check"

    mgr = RuntimeManager()
    mgr._mojo_model = MagicMock()
    mgr.add_requirement(flaky, name="flaky", every=1, latch_on_fail=True)

    for sim_time in (0.1, 0.2, 0.3, 0.4):
        state = MagicMock()
        state.data.time = sim_time
        mgr.requirements.step(state, signal_manager=None, mojo_model=mgr._mojo_model)

    # fn is called for the pass at 0.1, the pass at 0.2, and the fail at 0.3;
    # it must NOT be called again for 0.4 once latched
    assert calls == [0.1, 0.2, 0.3]
    assert mgr.requirements._latched["flaky"][0] is False
    assert mgr.requirements._latched["flaky"][2] == 0.3


def test_latch_on_pass_locks_in_success_despite_later_failure() -> None:
    """latch_on_pass=True freezes the verdict at True: later evaluations that would have failed never run at all, so the requirement stays passed for the trial (unlike the default sticky-failure behavior, where any later False would still doom it)."""
    calls: list[float] = []

    def would_fail_after_first_pass(model, state, df):
        calls.append(state.data.time)
        # passes on the very first evaluation; would fail every time after
        # that if it were ever called again
        return state.data.time == 0.1, "check"

    mgr = RuntimeManager()
    mgr._mojo_model = MagicMock()
    mgr.add_requirement(
        would_fail_after_first_pass, name="latching_goal", every=1, latch_on_pass=True
    )

    for sim_time in (0.1, 0.2, 0.3, 0.4):
        state = MagicMock()
        state.data.time = sim_time
        mgr.requirements.step(state, signal_manager=None, mojo_model=mgr._mojo_model)

    # fn stops being called the moment it passes at t=0.1; the false verdicts
    # it would have returned afterward are never observed
    assert calls == [0.1]
    assert mgr.requirements._first_live_failure == {}
    assert mgr.last_passed("latching_goal", state) is True


def test_latched_verdict_reported_at_end_of_trial_without_calling_fn(
    tmp_path: Path,
) -> None:
    """A latched requirement's end-of-trial result reuses the locked-in verdict and message; fn is never called for the final evaluation."""
    parquet_path = tmp_path / "telemetry.parquet"
    pl.DataFrame({"time": [0.0]}).write_parquet(parquet_path)

    sm = MagicMock(spec=SignalManager)
    sm.export_path = parquet_path
    mgr = RuntimeManager(signal_manager=sm)
    mgr._mojo_model = MagicMock()

    call_count = 0

    def once_only(model, state, df):
        nonlocal call_count
        call_count += 1
        if df is not None:
            raise AssertionError("fn must not be called again once latched")
        return True, "reached at this step"

    mgr.add_requirement(once_only, name="latched_goal", every=1, latch_on_pass=True)

    state = MagicMock()
    state.data.time = 0.1
    mgr.requirements.step(state, signal_manager=None, mojo_model=mgr._mojo_model)
    assert call_count == 1

    mgr._last_state = state
    mgr._evaluate_requirements()

    assert call_count == 1  # not called again for the end-of-trial evaluation
    result = mgr.requirement_results[0]
    assert result.passed is True
    assert "latched passed at t=0.100000" in result.message
    assert "evaluation skipped" in result.message
    assert result.decided_at == 0.1
    assert result.every == 1
    assert result.latch_on_pass is True
    assert result.latch_on_fail is False


def test_requirement_result_decided_at_reflects_when_the_verdict_was_set(
    tmp_path: Path,
) -> None:
    """decided_at is the first live-failure time for a sticky-failed requirement, and the trial's final sim time for a plain end-of-trial verdict."""
    parquet_path = tmp_path / "telemetry.parquet"
    pl.DataFrame({"time": [0.0]}).write_parquet(parquet_path)

    sm = MagicMock(spec=SignalManager)
    sm.export_path = parquet_path
    mgr = RuntimeManager(signal_manager=sm)
    mgr._mojo_model = MagicMock()

    mgr.add_requirement(
        lambda m, s, df: (False, "fell"),
        name="live_fail",
        every=1,
        terminate_on_fail=False,
    )
    mgr.add_requirement(lambda m, s, df: (True, "always ok"), name="plain_check")

    state = MagicMock()
    state.data.time = 0.3
    mgr.requirements.step(state, signal_manager=None, mojo_model=mgr._mojo_model)

    final_state = MagicMock()
    final_state.data.time = 2.5
    mgr._last_state = final_state
    mgr._evaluate_requirements()

    by_name = {r.name: r for r in mgr.requirement_results}
    assert by_name["live_fail"].decided_at == 0.3
    assert by_name["plain_check"].decided_at == 2.5


def test_registering_latch_without_every_warns(caplog) -> None:
    """latch_on_fail/latch_on_pass without `every` set is a no-op (only one evaluation ever happens) and logs a warning."""
    mgr = RuntimeManager()

    with caplog.at_level("WARNING"):
        mgr.add_requirement(
            lambda m, s, df: (True, "ok"), name="check", latch_on_pass=True
        )

    assert any("latch" in r.message for r in caplog.records)


def test_missing_parquet_does_not_crash(tmp_path: Path) -> None:
    """_evaluate_requirements returns silently if the parquet file does not exist."""
    sm = MagicMock(spec=SignalManager)
    sm.export_path = tmp_path / "nonexistent.parquet"
    mgr = RuntimeManager(signal_manager=sm)
    mgr._mojo_model = MagicMock()
    mgr._last_state = MagicMock()
    mgr.add_requirement(lambda m, s, df: (True, "ok"), name="check")

    mgr._evaluate_requirements()  # must not raise

    assert len(mgr.requirement_results) == 1
    assert mgr.requirement_results[0].passed is True
