# Composing the Model

!!! abstract

    In this section, we will walk through defining the generate function and begin building the MJCF tree.

---

## Generate Function

Mojo can use either a function or staticmethod as the entrypoint to generating the kinematic tree. This is most commonly done using a function called `generate` (but it can really be anything). For complex models, this is often used for initializing the MJCF tree and setting some parameters for Mojo.

One of these initialization steps is declaring to Mojo what unit system the code will be using via `mojo_model.us = US`. This is used to automatically convert units when performing random draws (using `mojo_model.sample_dist`) and will set metadata for requested signals.

???+ note

    It is recommended to declare a unit system as soon as you enter the generate function and stick with it. Changing the unit system partway through your model is often not necessary, and will result in inconsistent or incorrect conversions.

After declaring the units, we go into our custom logic to create the model (`VLRModel.new()`). It is added as `user_data` so that we can access it later when we define the simulation behavior of the model. For the moment we will skip over that since it will be explained in detail later.

The `options` tag is used to set some key parameters like the simulation timestep, integrator, and contact parameters. At the end, the modified `mojo_model` is returned for future steps.

```python
def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """
    Generates the MJCF model and samples distributions.

    This is one of the two entry points mujoco_mojo calls for every
    trial (the other is `runtime()`, below) — it builds and returns the
    MJCF model, but doesn't step the simulation.
    """
    mojo_model.us = US
    mojo_model.user_data = VLRModel.new(mojo_model)

    mojo_model.mjcf.options.append(
        mojo.Option(
            timestep=0.001 * US.s,
            gravity=np.array((0, 0, -9.81 * US["m/s**2"])),
            integrator=mojo.Integrator.EULER,
            cone=mojo.Cone.ELLIPTIC,
            # These `o_*` fields override every contact's solver and friction
            # parameters -- but MuJoCo silently ignores them unless
            # `flag.override` is also enabled, as it is below. Without the
            # flag, each contact would keep combining its two geoms'
            # individual `solref`/`friction` instead (their element-wise
            # maximum), which is easy to miss.
            o_solref=np.array((0.005, 1)),
            o_friction=np.array((0, 0, 0, 0, 0)),
            flag=mojo.Flag(override=mojo.typing.EnableDisable.ENABLE),
        )
    )
    mojo_model.mjcf.visuals.append(
        mojo.Visual(rgba=mojo.VisualRGBA(haze=np.array((0, 0, 0, 0))))
    )
    return mojo_model

```

You can explore the model this builds in your browser with MuJoCo Live. It is the model as `generate` leaves it, before any runtime behavior, so the landing gear's springs (added by the runtime step later in this guide) are not part of it.

[Open the model in MuJoCo Live](https://live.mujoco.org/?model=github:Hydrowelder/mujoco-mojo/master/docs/assets/models/vlr/model.xml)

---

## VLRModel Definition

Since in the previous step, we glossed over `VLRModel.new()`, we will cover it now! Note that many of the attributes in this section will be called, but not defined yet. It is okay to comment out those lines until they are set up later.

Our `VLRModel` will have a few things defined by the end of the `classmethod`:

1. `WorldBody`: The `<worldbody>` is technically an optional field in MJCF, so we need to define one to give our bodies a world to live in.
    - This `WorldBody` is also added to our `mojo_model.mjcf`, this is super critical. If it is not added to the `mojo_model`, Mojo will be unable to include it in the MJCF it generates, breaking the whole model.
2. `ground`: Another custom class used to define parameters and the portion of the MJCF tree related to what the ground is, looks like, and other "world frame" components.
3. `rocket`: A more complex class which defines the kinematically unconstrained body which we will attach legs and have fall onto the ground.
4. `camera`: For the purpose of recording video later, we will need a reference to a camera defined in the model. We define the camera, and provide its name for future reference.
    - Similar to the worldbody, this needs to be added to the MJCF, so make sure it is added to the worldbody we already added to the `mojo_model`. Any time you define a MJCF element, make sure it is referenced by `mojo_model.mjcf` so that MuJoCo is aware of its existence!
5. We also define a light for _dramatic_ effect.

```python
class VLRModel(mojo.UserData):
    """
    Root user-data container for the whole model.

    `generate()` builds this and stores it on `mojo_model.user_data`;
    `runtime()` later reads it back out via `mojo_model.get_user_data()` to
    get at the MJCF pieces (sites, bodies) it needs to attach forces to and
    step the simulation.
    """

    ground: Ground
    """The ground plane and world setup."""

    rocket: Rocket
    """The rocket body and its four landing gear legs."""

    camera: mojo.CameraName
    """Name of the camera `runtime()` points the video recorder at."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        mojo_model.mjcf.model = mojo.ModelName("Vertically Landing Rocket")
        mojo_model.mjcf.worldbody = mojo.WorldBody()

        ground = Ground.new(mojo_model)
        rocket = Rocket.new(mojo_model)

        # A fixed viewing camera, used later by the VideoRecorder in runtime()
        camera_name = mojo.CameraName("iso_view")
        mojo_model.mjcf.worldbody.cameras.append(
            mojo.Camera(
                name=camera_name,
                pose=mojo.PoseQuat.look_at(
                    target=np.array((0, 0, 6 * US.inch)),
                    eye=np.array((1, 1, 1)) * 2 * US.foot,
                    roll=-90,
                ),
            )
        )

        mojo_model.mjcf.worldbody.lights.append(
            mojo.Light(
                pos=mojo.Pos(np.array((0, 0, 10 * US.foot + INPUTS.STARTING_HEIGHT)))
            )
        )

        return cls(ground=ground, rocket=rocket, camera=camera_name)

```

---

!!! success

    We now have a partially defined model (at least with some stubs we know we will define next). We need to define a ground that our rocket will be landing on, we will do this next.
