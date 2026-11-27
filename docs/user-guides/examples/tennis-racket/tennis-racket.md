# Tennis Racket Theorem

!!! abstract

    This guide models the [tennis racket theorem](https://en.wikipedia.org/wiki/Tennis_racket_theorem){target="_blank"}: a rigid body whose three principal moments of inertia all differ spins steadily about the axes of its smallest and its largest moment, but not about the one in between. Spun about that middle axis, a tennis racket flips over again and again, however carefully it is thrown. It is also called the Dzhanibekov effect, after the cosmonaut who saw a wing nut do it in orbit.

    The model is a racket floating with no gravity (though it really looks more like a ping pong paddle). The runtime spins it and records a signal of its own, the angle between the racket's handle and its angular momentum, which shows each flip.

---

## Running It

The example ships with Mojo as `mujoco_mojo.examples.tennis_racket`. Open it in [Reloaded](../../features/reloaded/reloaded.md):

``` bash linenums="0"
mujoco-mojo examples run tennis-racket
```

<!-- docs/assets/models/tennis-racket/model.xml is written by scripts/gen_docs_models.py, and a pre-push hook keeps it current. Do not edit it by hand. -->

You can also look around the model in your browser with MuJoCo Live. It is the model as `generate` leaves it, before the runtime spins it, so the racket stays still.

[Open the model in MuJoCo Live :material-open-in-new:](https://live.mujoco.org/?model=github:Hydrowelder/mujoco-mojo/master/docs/assets/models/tennis-racket/model.xml){ .md-button .md-button--primary target=_blank }

---

## The Racket

Gravity is off, so only the spin moves the racket, and the fourth-order Runge-Kutta integrator with a 1 ms step follows the spin closely. The racket floats against the same dark sky and sun as the [berthing example](../berthing/introduction.md).

``` python
--8<-- "src/mujoco_mojo/examples/tennis_racket/simulation.py:options"
```

The racket's inertia is set directly, with a `mojo.Inertial` (MuJoCo's [`inertial`](https://mujoco.readthedocs.io/en/stable/XMLreference.html#body-inertial){target="_blank"} element) whose diagonal holds the three principal moments, instead of being worked out from its shapes. The moment is smallest about the handle (X), largest about the axis you swing a racket around (Z), and in between about the axis it flips around (Y). The handle and the two halves of the head, red and blue so a flip is easy to see, are only for looks: a body with an `Inertial` does not take its mass from its geoms.

``` python
--8<-- "src/mujoco_mojo/examples/tennis_racket/simulation.py:inertia"
```

??? example "Generator Code"

    ``` python
    --8<-- "src/mujoco_mojo/examples/tennis_racket/simulation.py:generate"
    ```

---

## The Spin

The runtime starts the racket spinning at 4 rad/s about its middle axis, with a nudge of 0.1 rad/s about the handle. A perfect spin about the middle axis would carry on, but any disturbance grows, and the nudge is what sets it off.

``` python
--8<-- "src/mujoco_mojo/examples/tennis_racket/simulation.py:spin"
```

---

## Measuring the Flips

With no gravity and nothing to touch, no torque acts on the racket, so its angular momentum stays fixed in space while the racket turns around it. The angle between the handle and the angular momentum, the nutation angle, starts near 90 degrees and swings away from it each time the racket flips.

The runtime registers a sampler, a function the signal manager calls as the run steps, which posts that angle as a signal of its own, `Bodies/racket:nutation_deg`:

``` python
--8<-- "src/mujoco_mojo/examples/tennis_racket/simulation.py:nutation"
```

Turn recording on in Reloaded (the `record` command) to save the signal to the trial's `telemetry.parquet`, then plot it in the [Dojo](../../features/dojo/dojo.md) with `mujoco-mojo dojo mojo-examples/tennis-racket`.

---

## Running One Trial

Its `simulation.py` also runs one trial on its own, with `python -m mujoco_mojo.examples.tennis_racket.simulation`, into `tennis_racket_study` in the folder you run it from:

``` python
--8<-- "src/mujoco_mojo/examples/tennis_racket/simulation.py:main"
```

---

??? example "All Code"

    ``` python
    --8<-- "src/mujoco_mojo/examples/tennis_racket/simulation.py"
    ```

---

!!! success

    That is the whole model. Change the three moments in the generator, or which axis the runtime spins the racket about, and watch which spins stay steady.
