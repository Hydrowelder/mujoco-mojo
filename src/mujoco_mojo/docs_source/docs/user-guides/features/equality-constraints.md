# Equality Constraints

!!! abstract

    An **equality constraint** ties two parts of a model together, such as a weld that holds one body to another. Any of them can start switched off and be switched on and off during a run, which is how you model a grab and a release, a latch or a clamp.

    <figure markdown="span">
        <video autoplay controls muted loop playsinline width="80%">
            <source src="equality-constraints.mp4" type="video/mp4">
        </video>
        <figcaption>Video of the example below: the ball falls with the weld <b>inactive</b>. When it reaches the hook, the weld is <b>activated</b> and the ball stays there. Half a second later the weld is again made <b>inactive</b> and the ball falls again.</figcaption>
    </figure>

    <!-- equality-constraints.mp4 is made by record_clip in equality_constraints_example.py: run that file to remake it (set MUJOCO_GL=egl if there is no display) -->

---

## A Constraint That Starts Off

This model has a ball above a hook, which is a site fixed in the world. The weld joins a site on the ball, `ball_site`, to the hook, `hook_site`:

```python
assert ball_site.name
assert hook_site.name
weld = mojo.EqualityWeldSite(
    name=mojo.EqualityName("catch"),
    site1=ball_site.name,
    site2=hook_site.name,
    # off, so the ball falls freely until the runtime switches it on
    active=False,
)
mojo_model.mjcf.equalities.append(mojo.Equality(welds=[weld]))
```

`EqualityWeldSite` welds two **sites**: it pulls their frames together wherever their bodies are, so the ball is held with its site on the hook. The sites' names come from the objects themselves, so there is no string to retype. `active=False` makes the constraint exist but do nothing until the run switches it on. Put it in an `Equality`, and append that to `mjcf.equalities`.

---

## Switching It On and Off

In the runtime function, `enable`, `disable` and `is_active` act on the running simulation. They take the state because the switch is `mjData.eq_active`, which lives in the state and not in the model. `set_active` does the same with a `bool`. Here the weld goes on as the ball passes the hook, holds it for half a second, and goes off:

```python
# on only once the ball is close, so the weld has almost nothing to pull in
while gap(state) > 0.05:
    rm.step(state)
scene.weld.enable(state)

caught_at = state.data.time
while state.data.time < caught_at + 0.5:
    rm.step(state)
held = scene.weld.is_active(state)
scene.weld.disable(state)
```

The ball falls freely until the weld is enabled, stays on the hook while it is on, and falls again once it is disabled. Every kind of equality constraint has the same methods, and the kinds are listed under [Equality Types](#equality-types).

???+ tip "Tip: Switch On When the Parts Are Close"

    A weld is soft, so it pulls the two sites together however far apart they are, and `solref` and `solimp` set how stiff it is. Switched on across a large gap, it pulls hard and the parts can jump. Switch it on once the parts are already close, as the example does.

---

## Equality Types

Each kind goes in the matching list of an `Equality`: `connects`, `welds`, `joints`, `tendons`, `flexes` or `flexstrains`. All of them are soft, with `solref` and `solimp` setting how stiff, and all of them have `active` and the methods above.

???+ question "Available Equality Types"

    <div class="grid cards" markdown>

    - `EqualityConnectBody`

        ---

        **Pins one body to another at an anchor point**, which you give in the first body's frame. It works like a ball joint outside the kinematic tree, and the bodies must start with the point together. Leave out the second body to pin the first to the world.

        > Holds a position only, so the bodies can still rotate about the point. `EqualityWeldBody` holds the rotation too.

    - `EqualityConnectSite`

        ---

        **Pulls a site on one body onto a site on another**, so the two meet at a point. It is the ball joint of `EqualityConnectBody`, but set by sites. The sites do not have to start together, and moving a site's position at runtime moves the constraint.

        > Holds a position only. `EqualityWeldSite` holds the rotation too.

    - `EqualityWeldBody`

        ---

        **Holds two bodies at the relative pose they have in the model**, removing all relative motion between them, softly like every constraint in MuJoCo. The bodies do not need to be close together. Leave out the second body to weld the first to the world, and switching that weld on and off fixes the body in place for a while.

        > Think of it as gluing two bodies in place. If they never need to come apart, make one a child of the other instead. `torquescale` sets how much the weld cares about rotation compared with position, and 0 makes it behave like a connect.

    - `EqualityWeldSite`

        ---

        **Aligns the frames of two sites**, position and orientation, wherever their bodies are. It is the body weld set by sites, so the sites do not have to start together, and the constraint pulls them together when it is on.

        > The one in the example above, and a good fit for a grab or a clamp. `torquescale` works as it does for the body weld, and 0 makes it behave like `EqualityConnectSite`.

    - `EqualityJoint`

        ---

        **Makes one joint follow another**, so moving one moves the other. Slide and hinge joints only. Leave out the second joint and the first is held in place.

        > Good for a gear ratio, or for two fingers of a gripper that move together. Holding a joint in place makes one you can lock and unlock during a run.

    - `EqualityTendon`

        ---

        **Makes the length of one tendon follow another's.** Leave out the second tendon and the first is held at its length.

        > Couples two tendons the way `EqualityJoint` couples two joints, or holds one tendon at a length you can lock and unlock during a run.

    - `EqualityFlex`

        ---

        **Keeps every edge of a flex at its starting length**, which maintains the shape of the deformable object. It adds one constraint per edge, where every other kind adds a fixed number.

        > The cost grows with the flex, since every edge is a constraint. Use it when a flex should keep its shape.

    - `EqualityFlexStrain`

        ---

        **Holds the strain of a flex to its starting values**, so a soft body keeps its volume and resists shear. Only for 3D flexes with trilinear or quadratic interpolation, and `cell` picks the grid cell it applies to.

        > The cost per element is high: 26 constraints for a trilinear element and 162 for a quadratic one.

    </div>

---

??? example "All Code"

    ```python
    import numpy as np

    import mujoco_mojo as mojo
    import mujoco_mojo.runtime as rt


    class Scene(mojo.UserData):
        """The weld and the two sites it joins, so the runtime can find them."""

        weld: mojo.EqualityWeldSite
        ball_site: mojo.SiteSphere
        hook_site: mojo.SiteSphere


    def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
        """A ball above a fixed hook, and a weld that can catch the ball on the hook."""
        worldbody = mojo_model.mjcf.worldbody = mojo.WorldBody()

        hook_site = mojo.SiteSphere(
            name=mojo.SiteName("hook"),
            size=0.03,
            rgba=mojo.utils.Color.GREEN_500.rgba,
            pose=mojo.PoseQuat(pos=np.array((0, 0, 1))),
        )
        worldbody.sites.append(hook_site)

        ball_site = mojo.SiteSphere(name=mojo.SiteName("ball_site"), size=0.02)
        worldbody.bodies.append(
            mojo.Body(
                name=mojo.BodyName("ball"),
                pose=mojo.PoseQuat(pos=np.array((0, 0, 1.5))),
                geoms=[
                    mojo.GeomSphere(size=0.1, mass=1, rgba=mojo.utils.Color.RED_500.rgba)
                ],
                sites=[ball_site],
                freejoints=[mojo.FreeJoint()],
            )
        )

        assert ball_site.name
        assert hook_site.name
        weld = mojo.EqualityWeldSite(
            name=mojo.EqualityName("catch"),
            site1=ball_site.name,
            site2=hook_site.name,
            # off, so the ball falls freely until the runtime switches it on
            active=False,
        )
        mojo_model.mjcf.equalities.append(mojo.Equality(welds=[weld]))

        mojo_model.user_data = Scene(weld=weld, ball_site=ball_site, hook_site=hook_site)
        return mojo_model




    def runtime(
        mojo_model: mojo.MojoModel,
        runtime_manager: rt.RuntimeManager,
        state: mojo.MjState,
        *args,
        **kwargs,
    ) -> mojo.MojoModel:
        with runtime_manager as rm:
            scene = mojo_model.get_user_data(Scene)

            def gap(state: mojo.MjState) -> float:
                return float(
                    np.linalg.norm(
                        scene.ball_site.rt_pos(state) - scene.hook_site.rt_pos(state)
                    )
                )

            # on only once the ball is close, so the weld has almost nothing to pull in
            while gap(state) > 0.05:
                rm.step(state)
            scene.weld.enable(state)

            caught_at = state.data.time
            while state.data.time < caught_at + 0.5:
                rm.step(state)
            held = scene.weld.is_active(state)
            scene.weld.disable(state)

            released_at = state.data.time
            while state.data.time < released_at + 0.3:
                rm.step(state)

            print(held, gap(state))

        return mojo_model


    ```

---

!!! success

    You can now define an equality constraint that starts off, and switch it on and off while a run is going.
