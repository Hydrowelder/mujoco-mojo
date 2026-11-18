# Requirements Checker

!!! abstract

    **Requirements** are named pass/fail checks that run automatically at the end of every trial (and optionally during the simulation loop itself). They give you a structured way to answer the question:

    > Did this simulation do what it needed to do or meet some specification while it ran?

    Results are saved to `requirements.json` inside each trial directory, stored on [`TrialStatus`][mujoco_mojo.utils.statusing.TrialStatus], and aggregated per-requirement at the job level for reports and the Dojo monitor.

---

## Overview

A **requirement** is a function you register on the [`RuntimeManager`][mujoco_mojo.runtime.runtime_manager.RuntimeManager]. It is called with the model, the last simulation state, and (at end of trial) the full telemetry parquet file. Mojo calls each registered function in order, collects the results, and writes them to disk.

The function signature is:

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:signature"
```

- `mojo_model`: the [`MojoModel`][mujoco_mojo.mojo_model.MojoModel] for the trial, giving access to `user_data`, distributions, named values, etc.
- `state`: the last [`MjState`][mujoco_mojo.mj_state.MjState] seen before the trial ended (access `state.data.qpos`, `state.data.time`, etc.)
- `df`: the full trial telemetry as a `MojoDataFrame` (a Polars DataFrame with Mojo's signal-aware namespace). `None` when the function is called during a live step check (see [Live checks](#live-checks)).
- **Return value:** `(passed, message)`: the verdict and a human-readable description. `passed` is tri-state:
  - `True`: the requirement is satisfied
  - `False`: the requirement is violated
  - `None`: no verdict yet. During live checks this is a no-op (nothing is recorded); a check that is still `None` at end of trial is recorded as failed

---

## Completion states

Requirements affect how a trial's [`Completion`][mujoco_mojo.utils.statusing.Completion] is recorded:

| `Completion` | Meaning                                                                       | Counted as          |
| :----------- | :---------------------------------------------------------------------------- | :------------------ |
| `SUCCESS`    | Trial ended normally and _all_ requirements passed (or none were registered)  | Success             |
| `FAILURE`    | Trial ended normally but _at least one_ requirement returned `passed=False`   | Requirement failure |
| `TERMINATED` | A live requirement with `terminate_on_fail=True` stopped the simulation early | Requirement failure |
| `ERROR`      | An unhandled exception was raised while processing the trial                  | Error               |
| `INCOMPLETE` | Trial is still running (intermediate state)                                   | Pending             |

!!! note "Failures vs. errors"

    Job statistics (the runtime report, [`JobStatus`][mujoco_mojo.utils.statusing.JobStatus], and the Dojo monitor) keep requirement failures and errors separate: `FAILURE`/`TERMINATED` mean the run worked but missed its requirements, while `ERROR` means the run itself broke.

    Errored trials are also excluded from throughput and time-remaining estimates, since a run that crashed says nothing about how long a real trial takes.

---

## Registering requirements

There are two equivalent approaches to defining a requirement: using a decorator and direct registration.

!!! info

    It is recommended to define requirements functions before running your main simulation loop.

Both styles accept the same keyword arguments:

| Argument            | Meaning                                                                                                                                   |
| :------------------ | :---------------------------------------------------------------------------------------------------------------------------------------- |
| `name`              | Label used in results and telemetry                                                                                                       |
| `every`             | `None`: end-of-trial only. `N`: also evaluate every N steps during the simulation                                                         |
| `terminate_on_fail` | When `every` is set, a failing live check stops the simulation (trial fails)                                                              |
| `terminate_on_pass` | When `every` is set, a passing live check stops the simulation (trial succeeds)                                                           |
| `latch_on_fail`     | **Defaults to `True`.** When `every` is set, once the check fails it is never evaluated again (see [Latching Results](#latching-results)) |
| `latch_on_pass`     | Defaults to `False`. When `every` is set, once the check passes it is never evaluated again (see [Latching Results](#latching-results))   |
| `post_result`       | Post live results to the telemetry parquet (see below)                                                                                    |

### Decorator style

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:decorator"
```

The decorator returns the original function unchanged, so the function remains callable on its own for testing.

### Direct registration

Given an end-of-trial check:

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:end_of_trial_check"
```

register it with `add_requirement`:

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:direct"
```

---

## Live checks

By default (`every=None`), requirements are evaluated once at end of trial. Set `every=N` to also run the check inside `step()` every N steps:

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:live"
```

- `every=N`: evaluate every N steps. Useful for expensive checks or when only coarse monitoring is needed
- `df` is always `None` during live calls; use `state` for real-time values or cache key values in your `mojo_model.user_data` object
- Returning `None` means no verdict yet, for example "reached the goal" before the goal is reachable, so an unfinished objective is not mistaken for a violation.
  - It never posts telemetry, fails the requirement (see the note below), or triggers `terminate_on_fail`/`terminate_on_pass`.
  - It is still recorded for that sim time, so `last_passed()` can tell "evaluated, no verdict yet" from "not evaluated at this step".
- Unless `post_result=False`, each `True`/`False` verdict is recorded in the telemetry parquet as `Requirements/{name}:result` (`1.0` passed, `0.0` failed), so you can plot it in the Dojo beside other signals, where the two values are labeled `PASS` and `FAIL`.
  - The last known verdict is re-posted on steps with no evaluation or no verdict, so the signal is continuous.

???+ note "Note: Failed Live Requirement"

    **A live requirement that explicitly fails (returns `False`) at any point during the run is failed for the trial**, even if it passes again by end of trial. `None` verdicts never trigger this.

    Since `latch_on_fail` [defaults to `True`](#latching-results), the function stops being called right after that first failure, and the recorded message reads `latched failed at t=...`. Pass `latch_on_fail=False` to keep evaluating after a failure. The message then reports how many live checks failed, when the first failure occurred, and the end-of-trial result.

### Reacting to Live Results in the Loop

Live results are cached by simulation time, so your control code can read the outcome of the most recent evaluation at no additional cost:

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:last_passed"
```

### Early termination

#### On Failure

Add `terminate_on_fail=True` to stop the simulation as soon as a live check fails:

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:terminate_on_fail"
```

When the check fails, [`RuntimeManager.step()`][mujoco_mojo.runtime.runtime_manager.RuntimeManager.step] raises [`RequirementTerminated`][mujoco_mojo.runtime.requirements_manager.RequirementTerminated] (a subclass of [`SimulationStopped`][mujoco_mojo.runtime.requirements_manager.SimulationStopped], so existing handlers keep working), which unwinds the simulation loop.

- The trial is marked [`Completion.TERMINATED`][mujoco_mojo.utils.statusing.Completion.TERMINATED].
- End-of-trial evaluation still runs, so every requirement appears in `requirements.json`.
- If several terminating requirements fail on the same step, all are evaluated and their messages are combined into the one exception.

#### On Success

The mirror image: add `terminate_on_pass=True` to stop the simulation as soon as a live check passes, without spending the rest of the simulation budget. Combine it with `None` verdicts so the waiting period is not counted as a failure:

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:terminate_on_pass"
```

When the check passes, [`RuntimeManager.step()`][mujoco_mojo.runtime.runtime_manager.RuntimeManager.step] raises [`RequirementSatisfied`][mujoco_mojo.runtime.requirements_manager.RequirementSatisfied] (also a subclass of [`SimulationStopped`][mujoco_mojo.runtime.requirements_manager.SimulationStopped]). Unlike `terminate_on_fail=True`, this is a **normal completion**: end-of-trial evaluation runs as usual and the trial is marked `SUCCESS` (or `FAILURE` if some _other_ requirement failed), not `TERMINATED`.

If a failing terminator and a passing one fire on the same step, the failure wins and the trial terminates as a failure.

!!! note

    Only requirements with `every` set and `terminate_on_fail=True`/`terminate_on_pass=True` can stop the simulation early. Non-terminating live checks let it continue.

### Latching Results

Latching is for a requirement that is expensive to keep checking once it has passed or failed. `latch_on_pass` and `latch_on_fail` lock in a verdict the first time the check produces it. The function is never called again, live or at end of trial, and the locked-in result is replayed for free. Each can be set independently.

They are not symmetric, though:

- `latch_on_fail`: Any live failure already dooms the trial for that requirement (see the note above), so locking it in does not change the outcome. It only saves calls to `fn`. Because of that, **`latch_on_fail` defaults to `True`**. Pass `latch_on_fail=False` to keep the function running after a failure, for example for its own logging or side effects.
- `latch_on_pass`: Without it, a requirement that passes once but fails on a later evaluation is still failed for the trial. With it, the check is never run again once it passes, so the requirement stays passed. This is the only way to get "once passed, stays passed" without ending the simulation via `terminate_on_pass`. Because it can hide a real later violation, **`latch_on_pass` defaults to `False`** and must be opted into.

Latching logs one debug line when it locks in ("requirement 'x' latched pass/fail at t=..."), not on every step that replays the verdict.

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:latching"
```

---

## Accessing results

### In-process

After the `with runtime_manager` block exits, the results are available directly on the manager:

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:in_process"
```

### Per-Trial JSON

After each trial, Mojo writes a `requirements.json` to the trial directory:

```json
[
  { "name": "max_height_ok", "passed": true, "message": "max z = 1.73 m" },
  {
    "name": "avg_speed_ok",
    "passed": false,
    "message": "avg speed = 0.41 m/s (target >= 0.5)"
  }
]
```

### Runtime Report

The standard Mojo job runner aggregates results across all trials. The generated `MOJO_RUNTIME_REPORT.md` includes a per-requirement table and pass/fail counters.

### Dojo

The Dojo monitor separates successes, requirement failures, and errors in its chips, progress bar, and timeline chart. This provides a graphical way to quickly identify trials with failed requirements.

- **Monitor** provides a way to view the job requirements at a glance via the top level summary, callouts for the individual trials, and a timeline chart to indicate if any failures are time based
- **Mosaic** provides a tabular view for a particular trial in the `Trial Execution` expander which includes any of the logs provided for verdicts

---

## Using `user_data` in checks

Because the `model` argument is the full [`MojoModel`][mujoco_mojo.mojo_model.MojoModel], you can access your handoff data to make requirements parametric per-trial. Define your handoff model:

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:user_data_model"
```

then read it back with `get_user_data` inside the check:

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:user_data"
```

This makes the same check automatically adapt to each trial's generated configuration.

---

## Using `state` for final-state checks

End-of-trial requirements receive the last state the simulation reached, which is useful for checking where things ended up without needing the full telemetry:

```python
--8<-- "docs/user-guides/features/requirements_doc_examples.py:final_state"
```

---

!!! success

    You now know the ins and outs of using automated requirement evaluation to cleanly trigger simulation shutdowns and more easily gain insight on simulation performance!
