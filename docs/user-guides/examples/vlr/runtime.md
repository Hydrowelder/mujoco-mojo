# Runtime Behavior

!!! abstract

    Mojo provides many tools to run MuJoCo models, in addition to building the XML files. In this section we will cover implementing the runtime behavior of the model: adding the shock-absorber springs and stepping the simulation.

---

## Adding Forces

In the `LandingGear` class, we are going to add a new instance method called `add_spring`. This method will add a force that acts between the two sites incorporated in the previous section using the runtime toolkit (`mujoco_mojo.runtime`, imported as `rt`).

This `rt.PointToPointForce` is created with the `ideal_spring()` helper. We provide:

1. A unique name for the spring (using the `side_id`)
2. Between what two sites the spring acts
3. The spring stiffness and damping coefficient
4. The rest length, computed from the leg's geometry (this is just the distance between our two sites)

Finally, we register this force to our `RuntimeManager` (`rm`). You will notice we do not provide one directly since we will use the `RuntimeManager` as a context manager.

```python
--8<-- "docs/user-guides/examples/vlr/vlr_example.py:landing_gear_dynamics"
```

---

## Defining the Runtime Method

Like with our `generator`, Mojo uses another function to define the runtime behavior of the model. Before calling this, Mojo will initialize a `mojo.MjState` which contains a `mujoco.MjModel`, `mujoco.MjData`, and your `UnitSystem` (if declared).

It also provides a `RuntimeManager` to use. Most often we will immediately use `with runtime_manager as rm:` since it makes building models easier, and we will only ever really need the one manager.

Once in the context block, we do a few things:

1. Extract our `VLRModel` from the user data
2. Loop over the landing gear to add the springs using our `add_spring` method
3. Use the camera we defined to record video and take screenshots during the simulation
    - We only do this for the nominal trial, not every randomized Monte Carlo trial, since video files can increase runtime, memory/storage space, and are generally not needed.
4. Run the solver by looping using `rm.step(state)` (this is where `rt.PointToPointForce` will automatically be computed and applied for each timestep)
5. Take one last screenshot when the rocket has landed

```python
--8<-- "docs/user-guides/examples/vlr/vlr_example.py:runtime"
```

---

## Running One Trial

Running the model can be done using `mojo.utils.MojoRunner`, providing the generator, runtime, a workdir, and configuration for how many [Monte Carlo trials](../../workflow/running-jobs/running-jobs.md#running-a-monte-carlo) should be run. It then tells it to run with a clean working directory.

```python
--8<-- "docs/user-guides/examples/vlr/vlr_example.py:main"
```

---

??? example "All Code"

    ```python
    --8<-- "docs/user-guides/examples/vlr/vlr_example.py"
    ```

---

!!! success

    That is pretty much it. MuJoCo Mojo provides _many_ more tools than just the ones used in this walkthrough (such as automating data output, requirements verification, running optimization studies, and data interaction through [Dojo](../../features/dojo/dojo.md), the list could go on).
