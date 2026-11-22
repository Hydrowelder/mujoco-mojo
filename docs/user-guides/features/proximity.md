# Proximity

!!! abstract

    **Proximity** measures the shortest distance between two mesh volumes while a model runs, logs it, and draws it as a line between the two nearest points. It answers "how close do these two parts get?" without waiting for them to touch. The berthing example uses it twice: the clearance between the arm and the visiting vehicle's hull, which must stay above zero, and the gap between the arm's end effector and the grapple fixture it is closing on.

    <figure markdown="span">
        <video controls muted loop playsinline width="80%">
            <source src="../examples/berthing/overview.mp4" type="video/mp4">
        </video>
        <figcaption>The berthing example, filmed by its overview camera. The label shows the gap and the clearance, which are Proximity measurements, and the thin line joins the nearest points of the end effector and the grapple fixture. Once the visitor is grabbed, the pairs are switched off and the label drops the numbers.</figcaption>
    </figure>

---

## Measuring a Pair

A pair is two **mesh** volumes: a `GeomMesh` or a `SiteMesh`. Mojo's builtin meshes work, such as `MeshCylinder`, which MuJoCo generates when it compiles the model, so there are no mesh files to ship. This model has two cylinders, one fixed and one free to drift toward it:

```python
--8<-- "docs/user-guides/features/proximity_example.py:model"
```

Inside the runtime function, make the [`Proximity`][mujoco_mojo.utils.proximity.Proximity] from the two volumes and register it with the [`RuntimeManager`][mujoco_mojo.runtime.runtime_manager.RuntimeManager], which draws it. Then `request` logs it to the trial's telemetry, and `channels` picks what is logged: `dist` (the distance), `fromto` (the nearest point on each volume) and `prox_type` (the algorithm that produced the distance).

```python
--8<-- "docs/user-guides/features/proximity_example.py:pair"
```

The distance is logged every step as `Proximities/probe_to_target:dist`, and the nearest points as `Proximities/probe_to_target/fromto/probe:x` (and `y`, `z`, and the same for `target`). A pair is named `<volume_1>_to_<volume_2>`.

You can also read a pair yourself at any step, which is how a runtime acts on a distance:

```python
--8<-- "docs/user-guides/features/proximity_example.py:read"
```

The surfaces start 0.8 m apart and the probe drifts 0.5 m, so after a second `distance` is about 0.3 m, measured between `probe_point` and `target_point`.

---

## Algorithm and Range

By default the distance is between the **convex hulls** of the two meshes (`algorithm=ProximityType.CONVEX_HULL`). That is exact for convex shapes such as cylinders and boxes, and fast, so it is the one to use unless a part is concave. [`ProximityType`][mujoco_mojo.typing.ProximityType] lists the others, which work from the meshes' triangles.

`dist_max` is how far apart two volumes can be and still get an exact distance. When their bounding spheres are further apart than that, Mojo returns the sphere-to-sphere estimate and skips the rest, which is cheap and all you need when you only care about a part getting close. A closer pair gets its exact distance, but never more than `dist_max`. The `prox_type` channel says which you got.

---

## Drawing, Cost and Switching Off

Each registered pair is drawn as a line between its nearest points, in the viewer (see [Reloaded](reloaded.md)) and in videos recorded with `show_proximities=True`. Set `visualize=False` on a pair to hide its line. The color is the `visualization.clearance_line` setting, white by default, and setting it to an empty string turns the lines off everywhere.

A pair that is drawn or logged costs a distance calculation every step, though it is calculated once per step however many times it is read. When a pair stops mattering, set its `active` flag to `False`. It is then no longer measured, drawn or logged, so it costs nothing, and setting `active` back to `True` starts it again. A direct call to `get_proximity` still works either way.

---

## In the Berthing Example

The berthing example makes four pairs: the first boom, the second boom and the end effector, each against the visitor's hull, and the end effector against the visitor's grapple fixture. Two methods of the model's user data read them: `clearance` is the smallest of the first three, and `gap` is the last.

Once the arm has grabbed the visitor, the gap is zero and the arm carries the hull wherever it goes, so there is nothing left to watch. The runtime calls `stop_proximities` at that moment, which sets every pair's `active` flag to `False` and also makes the video labels drop the numbers.

??? example "The Proximity Code in the Berthing Example"

    ```python
    --8<-- "docs/user-guides/examples/berthing/simulation.py:proximities"
    ```

<!-- docs/assets/models/berthing/model.xml is written by scripts/gen_docs_models.py, and a pre-push hook keeps it current. Do not edit it by hand. -->

You can look around the berthing model in your browser with MuJoCo Live. It is the model as `generate` leaves it, before any runtime behavior, so nothing drives the arm, the weld is off, and no distance is measured.

[Open the model in MuJoCo Live :material-open-in-new:](https://live.mujoco.org/?model=github:Hydrowelder/mujoco-mojo/master/docs/assets/models/berthing/model.xml){ .md-button .md-button--primary target=_blank }

---

??? example "All Code"

    ```python
    --8<-- "docs/user-guides/features/proximity_example.py"
    ```

---

!!! success

    You can now measure how close any two mesh parts get, log it, read it during a run, and stop measuring when it no longer matters.
