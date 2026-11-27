# Custom Signals

!!! abstract

    Mojo records many signals for you: a body's position or energy, a joint's angle, a sensor's reading, each turned on with `request()` (see [request-based telemetry](../../workflow/runtime-script.md#request-based-telemetry)). A **custom signal** is a value Mojo does not work out for you, such as an angle between two vectors, a controller's error or the number of contacts. Your runtime calculates it and posts it, and Mojo records it in the trial's `telemetry.parquet` beside the built-in signals.

    A custom signal is a signal like any other from then on: the [Dojo](../dojo/dojo.md) plots it, a [MojoDataFrame](../mojo-dataframe/mojo-dataframe.md) loads it, and it can carry a unit, a description and labels for integer codes.

---

## Naming a Signal

Every signal is named by a [`Column`][mujoco_mojo.utils.column.Column]: a category, a path of subgroups under it, and an attribute, written `Category/subgroup/...:attr`. The Dojo shows the names as a tree, with each part a level of it.

``` python
spring_force = mojo.utils.Column(
    category=mojo.SignalCategory.CUSTOM,
    subgroups=("suspension", "front_left"),
    attr="force",
)
# str(spring_force) is "Custom/suspension/front_left:force"
```

The category is one of `mojo.SignalCategory`, such as `BODIES` or `JOINTS`, or any name of your own. Use the category of the part a signal belongs to, so it sits next to that part's built-in signals, and `CUSTOM` for a signal that belongs to no one part. No part of the name may contain `/` or `:`, which separate the parts.

---

## Posting from a Sampler

A sampler is a function of the state that the signal manager calls on every recorded step, once the step's positions and velocities are up to date. It works out its values and posts each one with [`post()`][mujoco_mojo.runtime.signal_manager.SignalManager.post]. Register it with [`register_sampler()`][mujoco_mojo.runtime.signal_manager.SignalManager.register_sampler] inside the `with runtime_manager as rm:` block:

``` python
def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    # built once: the sampler runs on every recorded step
    contacts = mojo.utils.Column(
        category=mojo.SignalCategory.CUSTOM,
        subgroups=("contacts",),
        attr="count",
    )

    def sample_contacts(state: mojo.MjState) -> None:
        assert runtime_manager.signal_manager
        runtime_manager.signal_manager.post(state.data.ncon, contacts)

    with runtime_manager as rm:
        if rm.signal_manager:
            rm.signal_manager.register_sampler(sample_contacts)

        while state.data.time < 2.0:
            rm.step(state)

    return mojo_model


```

Build each `Column` once, outside the sampler. The sampler runs on every recorded step, and a `Column` built there would be made, validated and looked up again on each one.

???+ example "Example: Nutation Angle"

    The [tennis racket example](../../examples/tennis-racket/tennis-racket.md) records the angle between the racket's handle and its angular momentum, which swings each time the racket flips. Its sampler reads the body's angular momentum and orientation from the state and posts the angle between them:

    ``` python
    # It will be logged to "Bodies/racket:nutation_deg" ("category/subgroup:attr")
    # Build the column once, `post` is called every timestep
    nutation_column = mojo.utils.Column(
        category=mojo.SignalCategory.BODIES,
        subgroups=(f"{handoff.racket.name}",),
        attr="nutation_deg",
        metadata=mojo.utils.ColumnMetadata(
            # The sampler converts to degrees, whatever units the model is in
            unit="degree",
            # Pint counts a degree as dimensionless, so name what it measures
            quantity="angle",
            # The angle is the same in any reference frame
            transform_type=mojo.utils.TransformType.SCALAR,
            description="Angle between the racket's handle and its angular momentum",
        ),
    )

    # Define a custom signal sampler
    def sample_nutation(state: mojo.MjState) -> None:
        """Adds the [nutation angle](https://en.wikipedia.org/wiki/Nutation) as an output signal."""
        assert runtime_manager.signal_manager

        # Get the angular momentum vector and magnitude
        L = handoff.racket.rt_ang_mom(state)
        L_mag = np.linalg.norm(L)

        if L_mag > 1e-9:
            # Get the handle axis in the world frame
            R = handoff.racket.rt_xmat(state)
            handle_axis = R[:, 0]

            # Calculate the angle (theta) between L and the handle axis
            # cos(theta) = (L * handle) / (|L| * |handle|)
            dot_product = np.dot(L, handle_axis) / L_mag
            nutation_rad = np.acos(np.clip(dot_product, -1, 1))
            nutation_deg = np.degrees(nutation_rad)

            # Post to the signal manager
            runtime_manager.signal_manager.post(float(nutation_deg), nutation_column)

    with runtime_manager as rm:
        # Request telemetry to monitor the tumbling
        if rm.signal_manager:
            rm.signal_manager.register_sampler(sample_nutation)
    ```

---

## Tracking a Value

When the runtime already works out a value in its loop, [`track()`][mujoco_mojo.runtime.signal_manager.SignalManager.track] records it without a sampler of your own. It takes a function with no arguments that returns the value, and calls it on every recorded step. The function has to read the value when it is called, such as a variable the loop reassigns:

``` python
target = 0.5
error = 0.0

with runtime_manager as rm:
    if rm.signal_manager:
        rm.signal_manager.track(
            lambda: error,
            mojo.utils.Column(
                category=mojo.SignalCategory.CUSTOM,
                subgroups=("controller",),
                attr="error",
            ),
        )

    while state.data.time < 2.0:
        error = target - float(state.data.qpos[0])
        state.data.ctrl[0] = 10.0 * error
        rm.step(state)
```

???+ warning "Warning: Read the Value When the Function Is Called"

    `track()` posts whatever the function returns, on every recorded step. A function that returns a value read once, before the loop, posts that same value on every step. Nothing warns you: the signal is just a flat line.

    ``` python
    # wrong: the height is read once, so every row holds the starting height
    start = float(state.data.qpos[2])
    rm.signal_manager.track(lambda: start, height)

    # right: the height is read again each time the function is called
    rm.signal_manager.track(lambda: float(state.data.qpos[2]), height)
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
spring_stretch = mojo.utils.Column(
    category=mojo.SignalCategory.CUSTOM,
    subgroups=("suspension", "front_left"),
    attr="stretch",
    metadata=mojo.utils.ColumnMetadata(
        dimension="[length]",
        description="How far the front left spring is stretched past its rest length",
    ),
)
```

A signal that holds integer codes, like the state of a controller, can carry labels for them. [`ColumnMetadata.from_enum()`][mujoco_mojo.utils.signal_metadata.ColumnMetadata.from_enum] builds the labels from an enum class, and the Dojo plots the signal on its own axis named by them. In a loaded MojoDataFrame, `df.mojo.convert_enums(path=...)` swaps the codes for their labels.

``` python
class Mode(IntEnum):
    IDLE = 0
    RUNNING = 1


mode = mojo.utils.Column(
    category=mojo.SignalCategory.CUSTOM,
    subgroups=("controller",),
    attr="mode",
    metadata=mojo.utils.ColumnMetadata.from_enum(Mode),
)
```

The metadata is saved the first time a name is posted. A later `Column` with the same name and different metadata records into the same signal and its metadata is ignored.

---

!!! success

    That covers custom signals. Open a trial in the [Dojo](../dojo/dojo.md) to plot them, or load its telemetry with a [MojoDataFrame](../mojo-dataframe/mojo-dataframe.md).
