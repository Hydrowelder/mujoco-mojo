# Proximity

!!! abstract

    **Proximity** measures the shortest distance between two mesh volumes while a model runs, logs it, and draws it as a line between the two nearest points. It answers "how close do these two parts get?" without waiting for them to touch, so a runtime can act on a clearance that must stay above zero or a gap that is closing.

    <figure markdown="span">
        <video autoplay controls muted loop playsinline width="80%">
            <source src="proximity.mp4" type="video/mp4">
        </video>
        <figcaption>The two cylinders from the example below, at half speed. The probe drifts toward the target and spins, the thin line joins the nearest points and moves around the surfaces as the probe turns, and the label shows the distance and the algorithm that produced it.</figcaption>
    </figure>

    <!-- proximity.mp4 is made by record_clip in proximity_example.py: run that file to remake it (set MUJOCO_GL=egl if there is no display) -->

---

## Measuring a Pair

A pair is two **mesh** volumes: a `GeomMesh` or a `SiteMesh`. MuJoCo's builtin meshes work too, such as `MeshCylinder`, which MuJoCo generates when it compiles the model, so there are no mesh files to ship. This model has two cylinders, one fixed and one free to drift toward it:

``` python
--8<-- "docs/user-guides/features/proximity/proximity_example.py:model"
```

Inside the runtime function, make the [`Proximity`][mujoco_mojo.utils.proximity.Proximity] from the two volumes and register it with the [`RuntimeManager`][mujoco_mojo.runtime.runtime_manager.RuntimeManager], which draws it. Then `request` logs it to the trial's telemetry, and `channels` picks what is logged: `dist` (the distance), `fromto` (the nearest point on each volume) and `prox_type` (the algorithm that produced the distance).

``` python
--8<-- "docs/user-guides/features/proximity/proximity_example.py:pair"
```

The distance is logged every step as `Proximities/probe_to_target:dist`, the nearest points as `Proximities/probe_to_target/fromto/probe:x` (and `y`, `z`, and the same for `target`), and the algorithm as `Proximities/probe_to_target:prox_type`. A pair is named `<volume_1>_to_<volume_2>`.

You can also read a pair yourself at any step, which is how a runtime acts on a distance:

``` python
--8<-- "docs/user-guides/features/proximity/proximity_example.py:read"
```

The surfaces start 1.3 m apart. The probe drifts toward the target at 0.8 m/s and spins at 10 rad/s about Y, so it is tumbling as it arrives. After 1.4 s `distance` is about 0.07 m, measured between `probe_point` on the probe's tilted end and `target_point` on the side of the target. `algorithm` says how it was measured, which changes during this run (see below).

---

## Algorithm and Range

By default the distance is between the **convex hulls** of the two meshes (`algorithm=ProximityType.CONVEX_HULL`). That is exact for convex shapes such as cylinders and boxes, and fast, so it is the one to use unless a part is concave. A concave part, such as a cup, is treated as if it were filled in, so a ball inside the cup reads as touching it. For those, `algorithm=ProximityType.FACE_TO_FACE` measures to the actual surface, at a much higher cost per step, so use it only on the pairs that need it. [`ProximityType`][mujoco_mojo.typing.ProximityType] lists the others, which work from the meshes' triangles.

`dist_max` is how far apart two volumes can be and still get an exact distance. When their bounding spheres are further apart than that, Mojo returns the sphere-to-sphere estimate and skips the rest, which is cheap and all you need when you only care about a part getting close. A closer pair gets its exact distance, but never more than `dist_max`. The `prox_type` channel says which you got.

In the example `dist_max` is 0.4 m. The probe starts far enough away to get the estimate, `SPHERE_TO_SPHERE`, and the label above changes to `CONVEX_HULL` once the bounding spheres are within 0.4 m. The distance then reads 0.4 m, with the nearest points still those of the bounding spheres, until the surfaces themselves are closer than that.

---

## Drawing, Cost and Switching Off

Each registered pair is drawn as a line between its nearest points, in the viewer (see [Reloaded](../reloaded/reloaded.md)) and in videos recorded with `show_proximities=True`. Set `visualize=False` on a pair to hide its line. The color is the `visualization.clearance_line` setting, white by default, and setting it to an empty string turns the lines off everywhere.

A pair that is drawn or logged costs a distance calculation every step, though it is calculated once per step however many times it is read. When a pair stops mattering, set its `active` flag to `False`. It is then no longer measured, drawn or logged, so it costs nothing, and setting `active` back to `True` starts it again. A direct call to `get_proximity` still works either way.

``` python
--8<-- "docs/user-guides/features/proximity/proximity_example.py:stop"
```

---

??? example "All Code"

    ``` python
    --8<-- "docs/user-guides/features/proximity/proximity_example.py:example"
    ```

---

!!! success

    You can now measure how close any two mesh parts get, log it, read it during a run, and stop measuring when it no longer matters.
