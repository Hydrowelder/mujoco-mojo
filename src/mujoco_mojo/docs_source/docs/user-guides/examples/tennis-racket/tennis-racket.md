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
# Setup world and options
mojo_model.mjcf.options = [
    mojo.Option(
        integrator=mojo.Integrator.RK4,
        timestep=0.001,
        gravity=np.asarray((0, 0, 0)),
    )
]
```

The racket's inertia is set directly, with a `mojo.Inertial` (MuJoCo's [`inertial`](https://mujoco.readthedocs.io/en/stable/XMLreference.html#body-inertial){target="_blank"} element) whose diagonal holds the three principal moments, instead of being worked out from its shapes. The moment is smallest about the handle (X), largest about the axis you swing a racket around (Z), and in between about the axis it flips around (Y). The handle and the two halves of the head, red and blue so a flip is easy to see, are only for looks: a body with an `Inertial` does not take its mass from its geoms.

``` python
# Inertias
I_minor = 700.0  # Around the handle (X)
I_inter = 2000.0  # Flip axis (Y)
I_major = 2400.0  # Swing axis (Z)
```

??? example "Generator Code"

    ``` python
    def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
        """Generates the tennis racket model with distinct inertial properties."""
        mojo_model.us = US

        # A dark gradient sky, the same as the berthing example's
        mojo_model.mjcf.assets = [
            mojo.Asset(
                textures=[
                    mojo.TextureBuiltIn(
                        name=mojo.TextureName("sky"),
                        type=mojo.TextureType.SKYBOX,
                        builtin=mojo.TextureBuiltInType.GRADIENT,
                        width=16,
                        height=16,
                        rgb1=mojo.utils.Color.SLATE_700.rgb,
                        rgb2=mojo.utils.Color.SLATE_950.rgb,
                    )
                ],
            ),
        ]

        # Setup world and options
        mojo_model.mjcf.options = [
            mojo.Option(
                integrator=mojo.Integrator.RK4,
                timestep=0.001,
                gravity=np.asarray((0, 0, 0)),
            )
        ]

        # The sun, a directional light like the berthing example's
        mojo_model.mjcf.worldbody = mojo.WorldBody(
            lights=[
                mojo.Light(
                    name=mojo.LightName("sun"),
                    type=mojo.LightType.DIRECTIONAL,
                    dir=np.array((-0.4, 0.4, -0.8)),
                )
            ]
        )

        # Major dimensions
        total_racket_length = 70.0
        total_handle_length = 30.0
        total_head_width = 27.0
        total_head_thickness = 1.0
        handle_radius = 1.5

        # Derived values
        handle_half_length = total_handle_length / 2.0
        total_head_length = total_racket_length - total_handle_length
        head_half_length = total_head_length / 2.0
        head_half_width = total_head_width / 2.0
        head_half_thickness = total_head_thickness / 2.0

        # Inertias
        I_minor = 700.0  # Around the handle (X)
        I_inter = 2000.0  # Flip axis (Y)
        I_major = 2400.0  # Swing axis (Z)

        mojo_model.mjcf.worldbody.bodies = [
            # Define the racket
            racket := mojo.Body(
                name=mojo.BodyName("racket"),
                freejoints=[mojo.FreeJoint()],
                # Distinct moments of inertia
                inertial=mojo.Inertial(
                    pos=mojo.Pos(pos=np.array((0, 0, 0))),
                    mass=1,
                    diaginertia=np.array([I_minor, I_inter, I_major]),
                ),
                # Add a graphic for the racket
                geoms=[
                    mojo.GeomCylinder(
                        name=mojo.GeomName("handle"),
                        size=np.array([handle_radius, handle_half_length]),
                        pose=mojo.PoseEuler(
                            pos=np.array([-handle_half_length, 0, 0]),
                            euler=np.array([0, 90, 0]),
                        ),
                        rgba=mojo.utils.Color.WHITE.rgba,
                    ),
                    mojo.GeomEllipsoid(
                        name=mojo.GeomName("red_half"),
                        size=np.array(
                            [head_half_length, head_half_width, head_half_thickness]
                        ),
                        pose=mojo.PoseQuat(
                            pos=np.array([head_half_length, 0, head_half_thickness])
                        ),
                        rgba=mojo.utils.Color.RED_500.rgba,
                    ),
                    mojo.GeomEllipsoid(
                        name=mojo.GeomName("blue_half"),
                        size=np.array(
                            [head_half_length, head_half_width, head_half_thickness]
                        ),
                        pose=mojo.PoseQuat(
                            pos=np.array([head_half_length, 0, -head_half_thickness])
                        ),
                        rgba=mojo.utils.Color.BLUE_500.rgba,
                    ),
                ],
            )
        ]

        mojo_model.user_data = Handoff(racket=racket)
        return mojo_model


    ```

---

## The Spin

The runtime starts the racket spinning at 4 rad/s about its middle axis, with a nudge of 0.1 rad/s about the handle. A perfect spin about the middle axis would carry on, but any disturbance grows, and the nudge is what sets it off.

``` python
handoff.racket.set_initial_velocity(
    state,
    angular_velocity=np.asarray([0.1, 4.0, 0.0]),
    angle=mojo.Angle.RADIAN,
)
```

---

## Measuring the Flips

With no gravity and nothing to touch, no torque acts on the racket, so its angular momentum stays fixed in space while the racket turns around it. The angle between the handle and the angular momentum, the nutation angle, starts near 90 degrees and swings away from it each time the racket flips.

The runtime registers a sampler, a function the signal manager calls as the run steps, which posts that angle as a signal of its own, `Bodies/racket:nutation_deg`:

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

Turn recording on in Reloaded (the `record` command) to save the signal to the trial's `telemetry.parquet`, then plot it in the [Dojo](../../features/dojo/dojo.md) with `mujoco-mojo dojo mojo-examples/tennis-racket`.

---

## Running One Trial

Its `simulation.py` also runs one trial on its own, with `python -m mujoco_mojo.examples.tennis_racket.simulation`, into `tennis_racket_study` in the folder you run it from:

``` python
if __name__ == "__main__":
    mojo.utils.setup_logger()

    runner = mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
        workdir=Path("tennis_racket_study"),
        config=mojo.utils.MonteCarloConfig(n_trial=1, n_proc=1, resume=False),
    )

    runner.run(clean_workdir=True, cleanup_delay=0)
```

---

??? example "All Code"

    ``` python
    """Example: a racket spun about its middle axis, which flips over and over, as the [tennis racket theorem](https://en.wikipedia.org/wiki/Tennis_racket_theorem) says it should."""

    from pathlib import Path

    import numpy as np

    import mujoco_mojo as mojo
    import mujoco_mojo.runtime as rt

    logger = mojo.utils.get_logger(__name__)


    US = mojo.UnitSystem.si()


    class Handoff(mojo.UserData):
        racket: mojo.Body




    def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
        """Generates the tennis racket model with distinct inertial properties."""
        mojo_model.us = US

        # A dark gradient sky, the same as the berthing example's
        mojo_model.mjcf.assets = [
            mojo.Asset(
                textures=[
                    mojo.TextureBuiltIn(
                        name=mojo.TextureName("sky"),
                        type=mojo.TextureType.SKYBOX,
                        builtin=mojo.TextureBuiltInType.GRADIENT,
                        width=16,
                        height=16,
                        rgb1=mojo.utils.Color.SLATE_700.rgb,
                        rgb2=mojo.utils.Color.SLATE_950.rgb,
                    )
                ],
            ),
        ]

        # Setup world and options
        mojo_model.mjcf.options = [
            mojo.Option(
                integrator=mojo.Integrator.RK4,
                timestep=0.001,
                gravity=np.asarray((0, 0, 0)),
            )
        ]

        # The sun, a directional light like the berthing example's
        mojo_model.mjcf.worldbody = mojo.WorldBody(
            lights=[
                mojo.Light(
                    name=mojo.LightName("sun"),
                    type=mojo.LightType.DIRECTIONAL,
                    dir=np.array((-0.4, 0.4, -0.8)),
                )
            ]
        )

        # Major dimensions
        total_racket_length = 70.0
        total_handle_length = 30.0
        total_head_width = 27.0
        total_head_thickness = 1.0
        handle_radius = 1.5

        # Derived values
        handle_half_length = total_handle_length / 2.0
        total_head_length = total_racket_length - total_handle_length
        head_half_length = total_head_length / 2.0
        head_half_width = total_head_width / 2.0
        head_half_thickness = total_head_thickness / 2.0

        # Inertias
        I_minor = 700.0  # Around the handle (X)
        I_inter = 2000.0  # Flip axis (Y)
        I_major = 2400.0  # Swing axis (Z)

        mojo_model.mjcf.worldbody.bodies = [
            # Define the racket
            racket := mojo.Body(
                name=mojo.BodyName("racket"),
                freejoints=[mojo.FreeJoint()],
                # Distinct moments of inertia
                inertial=mojo.Inertial(
                    pos=mojo.Pos(pos=np.array((0, 0, 0))),
                    mass=1,
                    diaginertia=np.array([I_minor, I_inter, I_major]),
                ),
                # Add a graphic for the racket
                geoms=[
                    mojo.GeomCylinder(
                        name=mojo.GeomName("handle"),
                        size=np.array([handle_radius, handle_half_length]),
                        pose=mojo.PoseEuler(
                            pos=np.array([-handle_half_length, 0, 0]),
                            euler=np.array([0, 90, 0]),
                        ),
                        rgba=mojo.utils.Color.WHITE.rgba,
                    ),
                    mojo.GeomEllipsoid(
                        name=mojo.GeomName("red_half"),
                        size=np.array(
                            [head_half_length, head_half_width, head_half_thickness]
                        ),
                        pose=mojo.PoseQuat(
                            pos=np.array([head_half_length, 0, head_half_thickness])
                        ),
                        rgba=mojo.utils.Color.RED_500.rgba,
                    ),
                    mojo.GeomEllipsoid(
                        name=mojo.GeomName("blue_half"),
                        size=np.array(
                            [head_half_length, head_half_width, head_half_thickness]
                        ),
                        pose=mojo.PoseQuat(
                            pos=np.array([head_half_length, 0, -head_half_thickness])
                        ),
                        rgba=mojo.utils.Color.BLUE_500.rgba,
                    ),
                ],
            )
        ]

        mojo_model.user_data = Handoff(racket=racket)
        return mojo_model




    def runtime(
        mojo_model: mojo.MojoModel,
        runtime_manager: rt.RuntimeManager,
        state: mojo.MjState,
        *args,
        **kwargs,
    ) -> mojo.MojoModel:
        """Applies perturbation and runs the physics."""
        assert mojo_model.mjcf.worldbody
        handoff = mojo_model.get_user_data(Handoff)

        handoff.racket.set_initial_velocity(
            state,
            angular_velocity=np.asarray([0.1, 4.0, 0.0]),
            angle=mojo.Angle.RADIAN,
        )

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
                for b in mojo_model.mjcf.worldbody.walk_bodies():
                    b.request(rm.signal_manager)

            # Run to observe multiple flips
            while state.data.time < 10.0:
                rm.step(state)

        return mojo_model



    if __name__ == "__main__":
        mojo.utils.setup_logger()

        runner = mojo.utils.MojoRunner(
            generator=generate,
            runtime=runtime,
            workdir=Path("tennis_racket_study"),
            config=mojo.utils.MonteCarloConfig(n_trial=1, n_proc=1, resume=False),
        )

        runner.run(clean_workdir=True, cleanup_delay=0)
    ```

---

!!! success

    That is the whole model. Change the three moments in the generator, or which axis the runtime spins the racket about, and watch which spins stay steady.
