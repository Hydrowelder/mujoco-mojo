# Custom Signals

!!! abstract

    Mojo records many signals for you: a body's position or energy, a joint's angle, a sensor's reading, each turned on with `request()` (see [request-based telemetry](../../workflow/runtime-script.md#request-based-telemetry)). A **custom signal** is a value Mojo does not work out for you, such as an angle between two vectors, a controller's error or the number of contacts. Your runtime calculates it and posts it, and Mojo records it in the trial's `telemetry.parquet` beside the built-in signals.

    A custom signal is a signal like any other from then on: the [Dojo](../dojo/dojo.md) plots it, a [MojoDataFrame](../mojo-dataframe/mojo-dataframe.md) loads it, and it can carry a unit, a description and labels for integer codes.

---

## Naming a Signal

Every signal is named by a [`Column`][mujoco_mojo.utils.column.Column]: a category, a path of subgroups under it, and an attribute, written `Category/subgroup/...:attr`. The Dojo shows the names as a tree, with each part a level of it.

``` python
--8<-- "docs/user-guides/features/custom-signals/custom_signals_example.py:column"
```

The category is one of `mojo.SignalCategory`, such as `BODIES` or `JOINTS`, or any name of your own. Use the category of the part a signal belongs to, so it sits next to that part's built-in signals, and `CUSTOM` for a signal that belongs to no one part. No part of the name may contain `/` or `:`, which separate the parts.

---

## Posting from a Sampler

A sampler is a function of the state that the signal manager calls on every recorded step, once the step's positions and velocities are up to date. It works out its values and posts each one with [`post()`][mujoco_mojo.runtime.signal_manager.SignalManager.post]. Register it with [`register_sampler()`][mujoco_mojo.runtime.signal_manager.SignalManager.register_sampler] inside the `with runtime_manager as rm:` block:

``` python
--8<-- "docs/user-guides/features/custom-signals/custom_signals_example.py:sampler"
```

Build each `Column` once, outside the sampler. The sampler runs on every recorded step, and a `Column` built there would be made, validated and looked up again on each one.

???+ example "Example: Nutation Angle"

    The [tennis racket example](../../examples/tennis-racket/tennis-racket.md) records the angle between the racket's handle and its angular momentum, which swings each time the racket flips. Its sampler reads the body's angular momentum and orientation from the state and posts the angle between them:

    ``` python
    --8<-- "src/mujoco_mojo/examples/tennis_racket/simulation.py:nutation"
    ```

---

## Tracking a Value

When the runtime already works out a value in its loop, [`track()`][mujoco_mojo.runtime.signal_manager.SignalManager.track] records it without a sampler of your own. It takes a function with no arguments that returns the value, and calls it on every recorded step. The function has to read the value when it is called, such as a variable the loop reassigns:

``` python
--8<-- "docs/user-guides/features/custom-signals/custom_signals_example.py:track"
```

???+ warning "Warning: Read the Value When the Function Is Called"

    `track()` posts whatever the function returns, on every recorded step. A function that returns a value read once, before the loop, posts that same value on every step. Nothing warns you: the signal is just a flat line.

    ``` python
    --8<-- "docs/user-guides/features/custom-signals/custom_signals_example.py:track_stale"
    ```

    Two kinds of function stay current:

    - One that reads from an object that changes in place, such as `lambda: float(state.data.qpos[2])` or `lambda: controller.error`.
    - One that reads a variable the loop reassigns, like `error` above. Python looks the variable up each time the function is called, so the function sees the latest value. The loop has to reassign that same variable, in the same function: assigning `error` inside a helper function makes a new variable there (unless the helper declares it `nonlocal`), and the tracked one keeps its first value.

---

## When a Signal Is Recorded

- Samplers run only on **recorded** steps: every step by default, or every `record_decimation`-th step when it is set (`rm.signal_manager.record_decimation = 10` records every tenth).
- In [Reloaded](../reloaded/reloaded.md), nothing is recorded until recording is on (the `record` command, or `--record`).
- A column that a sampler does not post on a recorded step is empty (NaN) in that row. The nutation sampler skips the steps where the racket is not spinning, for example, since the angle is undefined there.
- `rm.signal_manager` is typed as optional, so check it before registering a sampler, as the examples here do.

---

## Units, Descriptions and Labels

A `Column` can carry a [`ColumnMetadata`][mujoco_mojo.utils.signal_metadata.ColumnMetadata], which is saved in the telemetry file with the signal. The Dojo shows a signal's unit and description, and a MojoDataFrame converts its units (see [metadata](../mojo-dataframe/mojo-dataframe.md#metadata-units-tags-and-labels) in the MojoDataFrame guide).

- `unit` is for a value that is always in one unit, such as the degrees the nutation sampler posts.
- `dimension` is for a value in the model's own units, such as a length: it says what the value measures without naming a unit, so the Dojo can label it in the display unit system you pick, and `df.mojo.with_unit_system(..., assume_source=...)` can convert it once you say which system it was recorded in. An angle has no dimension to Pint, so give it a `unit` and a `quantity` instead.
- `quantity` names what the value measures when its unit does not say: a degree has no dimension to Pint, so the nutation angle says `quantity="angle"`.
- `transform_type` says how the value behaves when the data is put in another [reference frame](../mojo-dataframe/mojo-dataframe.md#changing-the-reference-frame). `TransformType.SCALAR` is for a value that stays the same in any frame, such as an angle or an energy.
- `description` says what the signal holds, in plain words.

``` python
--8<-- "docs/user-guides/features/custom-signals/custom_signals_example.py:metadata"
```

A signal that holds integer codes, like the state of a controller, can carry labels for them. [`ColumnMetadata.from_enum()`][mujoco_mojo.utils.signal_metadata.ColumnMetadata.from_enum] builds the labels from an enum class, and the Dojo plots the signal on its own axis named by them. In a loaded MojoDataFrame, `df.mojo.convert_enums(path=...)` swaps the codes for their labels.

``` python
--8<-- "docs/user-guides/features/custom-signals/custom_signals_example.py:enum"
```

The metadata is saved the first time a name is posted. A later `Column` with the same name and different metadata records into the same signal and its metadata is ignored.

---

!!! success

    That covers custom signals. Open a trial in the [Dojo](../dojo/dojo.md) to plot them, or load its telemetry with a [MojoDataFrame](../mojo-dataframe/mojo-dataframe.md).
