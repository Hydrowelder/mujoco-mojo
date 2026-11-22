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
def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """A cylinder fixed in place, and an identical one free to drift toward it."""
    mojo_model.mjcf.worldbody = mojo.WorldBody()

    # a builtin mesh, which MuJoCo generates when it compiles the model: 0.2 m across and 1 m long
    mesh = mojo.MeshCylinder(
        name=mojo.MeshName("cylinder"),
        count=(9, 9, 9),
        spacing=np.array((0.025, 0.025, 0.125)),
    )
    mojo_model.mjcf.assets.append(mojo.Asset(meshes=[mesh]))
    assert mesh.name

    target = mojo.GeomMesh(name=mojo.GeomName("target"), mesh=mesh.name, mass=1)
    probe = mojo.GeomMesh(name=mojo.GeomName("probe"), mesh=mesh.name, mass=1)
    probe_body = mojo.Body(
        name=mojo.BodyName("probe"),
        geoms=[probe],
        freejoints=[mojo.FreeJoint()],
    )
    mojo_model.mjcf.worldbody.bodies.extend(
        [
            mojo.Body(
                name=mojo.BodyName("target"),
                pose=mojo.PoseQuat(pos=np.array((1, 0, 0))),
                geoms=[target],
            ),
            probe_body,
        ]
    )
    mojo_model.user_data = Cylinders(target=target, probe=probe, probe_body=probe_body)

    mojo_model.mjcf.options.append(
        mojo.Option(gravity=np.array((0, 0, 0)))  # nothing pulls the probe off its line
    )
    return mojo_model


```

Inside the runtime function, make the [`Proximity`][mujoco_mojo.utils.proximity.Proximity] from the two volumes and register it with the [`RuntimeManager`][mujoco_mojo.runtime.runtime_manager.RuntimeManager], which draws it. Then `request` logs it to the trial's telemetry, and `channels` picks what is logged: `dist` (the distance), `fromto` (the nearest point on each volume) and `prox_type` (the algorithm that produced the distance).

```python
proximity = mojo.utils.Proximity(
    volume_1=cylinders.probe, volume_2=cylinders.target, dist_max=2.0
).register_to_rm()
proximity.request(channels=["dist", "fromto"])
```

The distance is logged every step as `Proximities/probe_to_target:dist`, and the nearest points as `Proximities/probe_to_target/fromto/probe:x` (and `y`, `z`, and the same for `target`). A pair is named `<volume_1>_to_<volume_2>`.

You can also read a pair yourself at any step, which is how a runtime acts on a distance:

```python
distance, probe_point, target_point, algorithm = proximity.get_proximity(state)
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
    _clearances: list[mojo.utils.Proximity] = PrivateAttr(default_factory=list)
    """Distances from each boom and the free end effector to the hull."""

    _gap: mojo.utils.Proximity | None = PrivateAttr(default=None)
    """Distance from the free end effector to the visitor's grapple fixture."""

    def register_proximities(self) -> None:
        """Starts measuring and logging the clearance from the arm to the hull and the gap to the grapple fixture. Call it inside the runtime manager's `with` block."""
        arm, visitor = self.arm, self.visitor

        # `Proximity` works on mesh volumes, which is why these parts are meshes
        self._clearances = [
            mojo.utils.Proximity(
                volume_1=part, volume_2=visitor.hull, dist_max=MISSION.CLEARANCE_RANGE
            ).register_to_rm()
            for part in (arm.boom_1, arm.boom_2, arm.free_effector.geom)
        ]
        self._gap = mojo.utils.Proximity(
            volume_1=arm.free_effector.geom,
            volume_2=visitor.fixture.geom,
            dist_max=MISSION.GAP_RANGE,
        ).register_to_rm()

        for proximity in (*self._clearances, self._gap):
            proximity.request(channels=["dist", "fromto", "prox_type"])

    def gap(self, state: mojo.MjState) -> float:
        """Distance from the free end effector to the visitor's grapple fixture."""
        assert self._gap  # made by register_proximities
        return self._gap.get_proximity(state)[0]

    def clearance(self, state: mojo.MjState) -> float:
        """Distance from the closest boom or the free end effector to the hull."""
        return min(part.get_proximity(state)[0] for part in self._clearances)

    @property
    def tracking(self) -> bool:
        """Whether the distances are still being measured."""
        return self._gap is not None and self._gap.active

    def stop_proximities(self) -> None:
        """Stops measuring, drawing and logging the distances. Call it once the weld is on: the visitor is held, so there is nothing left to watch."""
        assert self._gap  # made by register_proximities
        for proximity in (*self._clearances, self._gap):
            proximity.active = False

    ```

<!-- docs/assets/models/berthing/model.xml is written by scripts/gen_docs_models.py, and a pre-push hook keeps it current. Do not edit it by hand. -->

You can look around the berthing model in your browser with MuJoCo Live. It is the model as `generate` leaves it, before any runtime behavior, so nothing drives the arm, the weld is off, and no distance is measured.

[Open the model in MuJoCo Live :material-open-in-new:](https://live.mujoco.org/?model=github:Hydrowelder/mujoco-mojo/master/docs/assets/models/berthing/model.xml){ .md-button .md-button--primary target=_blank }

---

??? example "All Code"

    ```python
    """Two cylinders and the distance between them, for the Proximity guide."""

    import numpy as np

    import mujoco_mojo as mojo
    import mujoco_mojo.runtime as rt


    class Cylinders(mojo.UserData):
        """The two cylinders, so the runtime can find them."""

        target: mojo.GeomMesh
        probe: mojo.GeomMesh
        probe_body: mojo.Body


    def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
        """A cylinder fixed in place, and an identical one free to drift toward it."""
        mojo_model.mjcf.worldbody = mojo.WorldBody()

        # a builtin mesh, which MuJoCo generates when it compiles the model: 0.2 m across and 1 m long
        mesh = mojo.MeshCylinder(
            name=mojo.MeshName("cylinder"),
            count=(9, 9, 9),
            spacing=np.array((0.025, 0.025, 0.125)),
        )
        mojo_model.mjcf.assets.append(mojo.Asset(meshes=[mesh]))
        assert mesh.name

        target = mojo.GeomMesh(name=mojo.GeomName("target"), mesh=mesh.name, mass=1)
        probe = mojo.GeomMesh(name=mojo.GeomName("probe"), mesh=mesh.name, mass=1)
        probe_body = mojo.Body(
            name=mojo.BodyName("probe"),
            geoms=[probe],
            freejoints=[mojo.FreeJoint()],
        )
        mojo_model.mjcf.worldbody.bodies.extend(
            [
                mojo.Body(
                    name=mojo.BodyName("target"),
                    pose=mojo.PoseQuat(pos=np.array((1, 0, 0))),
                    geoms=[target],
                ),
                probe_body,
            ]
        )
        mojo_model.user_data = Cylinders(target=target, probe=probe, probe_body=probe_body)

        mojo_model.mjcf.options.append(
            mojo.Option(gravity=np.array((0, 0, 0)))  # nothing pulls the probe off its line
        )
        return mojo_model




    def runtime(
        mojo_model: mojo.MojoModel,
        runtime_manager: rt.RuntimeManager,
        state: mojo.MjState,
        *args,
        **kwargs,
    ) -> mojo.MojoModel:
        with runtime_manager as rm:
            cylinders = mojo_model.get_user_data(Cylinders)

            proximity = mojo.utils.Proximity(
                volume_1=cylinders.probe, volume_2=cylinders.target, dist_max=2.0
            ).register_to_rm()
            proximity.request(channels=["dist", "fromto"])

            # set the initial velocity (qvel) of a free-joint body so the probe drifts toward the target at 0.5 m/s
            cylinders.probe_body.set_initial_velocity(
                state, linear_velocity=np.array((0.5, 0, 0))
            )
            while state.data.time < 1.0:
                rm.step(state)

            distance, probe_point, target_point, algorithm = proximity.get_proximity(state)
            print(distance, probe_point, target_point, algorithm.name)

        return mojo_model
    ```

---

!!! success

    You can now measure how close any two mesh parts get, log it, read it during a run, and stop measuring when it no longer matters.
