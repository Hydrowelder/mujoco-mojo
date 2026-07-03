"""
Type-checked source for every code example in `docs/user-guides/requirements.md`.

The documentation embeds these snippets directly via `pymdownx.snippets` section markers (`--8<-- [start:name]` / `--8<-- [end:name]`), so the examples shown to users are exactly the code that ruff and pyright validate. If a requirements API change breaks an example, the checkers fail on this file instead of the documentation silently rotting.
"""

from __future__ import annotations

import numpy as np

from mujoco_mojo import Body, MojoModel, UserData
from mujoco_mojo.mj_state import MjState
from mujoco_mojo.runtime import (
    RequirementSatisfied,
    RequirementTerminated,
    RuntimeManager,
)
from mujoco_mojo.utils import MojoDataFrame
from mujoco_mojo.utils.statusing import TrialStatus


# --8<-- [start:user_data_model]
class BumperData(UserData):
    """Handoff data written during `generate()` and read back inside requirement checks."""

    min_speed: float = 0.5
    min_ground_clearance: float = 0.02
    goal_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    base: Body


# --8<-- [end:user_data_model]


# --8<-- [start:signature]
def my_check(
    mojo_model: MojoModel,
    state: MjState,
    df: MojoDataFrame | None,
) -> tuple[bool | None, str]:
    """Every requirement takes `(mojo_model, state, df)` and returns `(passed, message)`."""
    # passed: True = satisfied, False = violated, None = no verdict yet
    return True, "always passes"


# --8<-- [end:signature]


# --8<-- [start:end_of_trial_check]
def check_max_height(
    mojo_model: MojoModel,
    state: MjState,
    df: MojoDataFrame | None,
) -> tuple[bool, str]:
    """Passes when the robot's peak height stayed under 2 m for the whole trial."""
    assert df is not None  # end-of-trial checks always receive the telemetry frame
    max_z = df["Bodies/Robot/xpos:z"].max()
    assert isinstance(max_z, float)
    return max_z < 2.0, f"max z = {max_z:.3f} m"


# --8<-- [end:end_of_trial_check]


def register_directly(runtime_manager: RuntimeManager, state: MjState) -> None:  # pyright: ignore[reportRedeclaration]
    """Registers requirements with plain method calls, then runs the simulation."""
    # --8<-- [start:direct]
    runtime_manager: RuntimeManager

    runtime_manager.add_requirement(
        check_max_height
    )  # name inferred: "check_max_height"
    runtime_manager.add_requirement(
        check_max_height, name="max_height_ok"
    )  # explicit name

    with runtime_manager as rm:
        for _ in range(10_000):
            rm.step(state)

    # the requirement is checked here upon leaving the with block!
    # --8<-- [end:direct]


def register_with_decorator(rm: RuntimeManager) -> None:
    """Registers the same checks with the decorator style."""

    # --8<-- [start:decorator]
    @rm.requirement()  # name inferred: "check_settle_time"
    def check_settle_time(
        mojo_model: MojoModel,
        state: MjState,
        df: MojoDataFrame | None,
    ) -> tuple[bool, str]:
        """Passes when the simulation ran for at least one second."""
        return state.data.time > 1.0, f"final sim time = {state.data.time:.3f} s"

    @rm.requirement("avg_speed_ok")  # explicit name
    def check_avg_speed(
        mojo_model: MojoModel,
        state: MjState,
        df: MojoDataFrame | None,
    ) -> tuple[bool, str]:
        """Passes when the average forward speed met the per-trial target."""
        target = mojo_model.get_user_data(BumperData).min_speed
        assert df is not None
        avg = df["Bodies/Robotxvelp:x"].mean()
        assert isinstance(avg, float)
        return avg >= target, f"avg speed = {avg:.3f} m/s (target >= {target})"

    # --8<-- [end:decorator]


def apply_recovery(state: MjState) -> None:
    """Placeholder controller action taken when the upright check fails."""


def register_live_check_and_react(rm: RuntimeManager, state: MjState) -> None:
    """Registers a live check that runs every 100 steps, then reacts to its cached result inside the sim loop."""

    # --8<-- [start:live]
    @rm.requirement(every=100)
    def upright(
        mojo_model: MojoModel,
        state: MjState,
        df: MojoDataFrame | None,
    ) -> tuple[bool, str]:
        """Passes while the base stays above 5 cm."""
        # df is None during live checks; use state directly
        z_up = float(state.data.qpos[2])
        return z_up > 0.05, f"base height = {z_up:.3f} m"

    # --8<-- [end:live]

    # --8<-- [start:last_passed]
    for _ in range(10_000):
        rm.step(state)
        # returns the cached live result at the current sim time, or None if
        # there is no verdict yet. Pass the function itself (returned
        # unchanged by the decorator) instead of retyping its name.
        if rm.last_passed(upright, state) is False:
            apply_recovery(state)
    # --8<-- [end:last_passed]


def run_with_early_termination(rm: RuntimeManager, state: MjState) -> None:
    """Stops the simulation as soon as the live check fails and handles the resulting exception."""

    # --8<-- [start:terminate_on_fail]
    @rm.requirement(every=50, terminate_on_fail=True)
    def upright(
        mojo_model: MojoModel,
        state: MjState,
        df: MojoDataFrame | None,
    ) -> tuple[bool, str]:
        """Terminates the trial if the robot falls over."""
        return float(state.data.qpos[2]) > 0.05, "robot fell over"

    try:
        for _ in range(10_000):
            rm.step(state)
    except RequirementTerminated as e:
        print(f"stopped early: {e}")
    # --8<-- [end:terminate_on_fail]


def run_with_latching(rm: RuntimeManager, state: MjState) -> None:
    """Registers an expensive live check that stops re-evaluating itself the moment its verdict is decided, without ending the simulation."""

    def very_expensive_function(state: MjState) -> float:
        return 0.0

    # --8<-- [start:latching]
    # latch_on_fail=True is the default; spelled out here for symmetry with
    # latch_on_pass, which must be opted into explicitly
    @rm.requirement(every=23, latch_on_pass=True, latch_on_fail=True)
    def check_expensive_requirement(
        mojo_model: MojoModel,
        state: MjState,
        df: MojoDataFrame | None,
    ) -> tuple[bool | None, str]:
        """Runs a very expensive function."""
        value = very_expensive_function(state)

        if value < 2.7128:
            # check_expensive_requirement will always return this value
            return False, "Expensive function was below Euler's number"
        elif value > 2 * 3.1415:
            # check_expensive_requirement will always return this value
            return True, "Expensive function was above 2 pi!"

        # check_expensive_requirement will be run again in 23 timesteps
        return None, "Requirement neither passed nor failed"

    # --8<-- [end:latching]


def run_with_successful_early_termination(rm: RuntimeManager, state: MjState) -> None:
    """Ends the trial early as a success the moment the goal is reached."""

    # --8<-- [start:terminate_on_pass]
    @rm.requirement(every=25, terminate_on_pass=True)
    def reached_goal(
        mojo_model: MojoModel,
        state: MjState,
        df: MojoDataFrame | None,
    ) -> tuple[bool | None, str]:
        """Ends the trial successfully once the base gets within 10 cm of the goal."""
        handoff = mojo_model.get_user_data(BumperData)

        goal = np.asarray(handoff.goal_position)
        dist = float(np.linalg.norm(handoff.base.rt_xipos(state) - goal))

        if dist < 0.1:
            return True, f"goal reached at t={state.data.time:.2f} s"

        # None: no verdict yet; being far from the goal mid-run is not a failure
        return None, f"distance to goal = {dist:.2f} m"

    try:
        for _ in range(100_000):
            rm.step(state)
    except RequirementSatisfied as e:
        print(f"success, ending early: {e}")
    # --8<-- [end:terminate_on_pass]


def read_results_in_process(rm: RuntimeManager) -> None:
    """Reads requirement results directly off the runtime manager after the `with` block exits."""
    # --8<-- [start:in_process]
    for result in rm.requirement_results:
        print(result.name, result.passed, result.message)
    # --8<-- [end:in_process]


def inspect_trial_status(status: TrialStatus) -> None:
    """Reads per-requirement results and the aggregate pass/fail from a trial's status."""
    # --8<-- [start:trial_status]
    for result in status.requirements:
        print(result.name, result.passed, result.message)

    # True: all passed; False: at least one failed; None: none registered
    print(status.requirements_passed)
    # --8<-- [end:trial_status]


def register_parametric_check(rm: RuntimeManager) -> None:
    """Makes a check parametric per trial by reading handoff data from the model."""

    # --8<-- [start:user_data]
    @rm.requirement("clearance_ok")
    def check_clearance(
        mojo_model: MojoModel,
        state: MjState,
        df: MojoDataFrame | None,
    ) -> tuple[bool, str]:
        """Passes if the chassis never dipped below the generated clearance threshold."""
        min_clearance = mojo_model.get_user_data(BumperData).min_ground_clearance
        assert df is not None
        lowest_z = df["Bodies/Chassis/xpos:z"].min()
        assert isinstance(lowest_z, float)
        return (
            lowest_z >= min_clearance,
            f"min z = {lowest_z:.4f} (threshold = {min_clearance})",
        )

    # --8<-- [end:user_data]


def register_final_state_check(rm: RuntimeManager) -> None:
    """Checks where things ended up using only the final state, no telemetry needed."""

    # --8<-- [start:final_state]
    @rm.requirement("reached_goal")
    def check_goal(
        mojo_model: MojoModel,
        state: MjState,
        df: MojoDataFrame | None,
    ) -> tuple[bool, str]:
        """Passes if the base finished within 10 cm of the goal position."""
        handoff = mojo_model.get_user_data(BumperData)

        goal = np.asarray(handoff.goal_position)
        dist = float(np.linalg.norm(handoff.base.rt_xipos(state) - goal))

        return dist < 0.1, f"final distance to goal = {dist:.3f} m"

    # --8<-- [end:final_state]
