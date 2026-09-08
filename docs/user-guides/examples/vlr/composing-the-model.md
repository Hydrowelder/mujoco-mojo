# Composing the Model

!!! abstract

    In this section, we will walk through defining the generate function and begin building the MJCF tree.

---

## Generate Function

Mojo can use either a function or staticmethod as the entrypoint to generating the kinematic tree. This is most commonly done using a function called `generate` (but it can really be anything). For complex models, this is often used for initializing the MJCF tree and setting some parameters for Mojo.

One of these initialization steps is declaring to Mojo what unit system the code will be using via `mojo_model.us = US`. This is used to automatically convert units when performing randoms draws (using `mojo_model.sample_dist`) and will set metadata for requested signals.

???+ note

    It is recommended to declare a unit system as soon as you enter the generate function and stick with it. Changing the unit system partway through your model is often not neccessary, and will result in inconsistent or incorrect conversions.

After declaring the units, we go into our custom logic to create the model (`VLRModel.new`). It is added as `user_data` so that we can access it later when we define the simulation behavior of the model. For the moment we will skip over that since it will be explained in detail later.

The `options` tag, is used to set some key parameters like the simulation timestep, integrator, and contact parameters. At the end, the modified `mojo_model` is returned for future steps.

```python
--8<-- "docs/user-guides/examples/vlr/vlr_example.py:generate"
```

---

## VLRModel Definition

Since in the previous step, we glossed over `VLRModel.new`, we will cover it now! Note that many of the attributes in this section will be called, but not defined yet. It is okay to comment out those lines until they are set up later.

Our `VLRModel` will have a few things defined by the end of the `classmethod`:

1. `WorldBody`: The `<worldbody>` is technically an optional field in MJCF, so we need to define one to give our bodies a world to live in.
    - This `WorldBody` is also added to our `mojo_model.mjcf`, this is super critical. If it is not added to the `mojo_model`, Mojo will be unable to include it in the MJCF it generates, breaking the whole model.
2. `ground`: Another custom class used to define parameters and the portion of the MJCF tree related to what the ground is, looks like, and other "world frame" components.
3. `rocket`: A more complex class which defines the kinematically unconstrained body which we will attach legs and have fall onto the ground.
4. `camera`: For the purpose of recording video later, we will need a reference to a camera defined in the model. We define the camera, and provide its name for future reference.
    - Similar to the worldbody, this needs to be added to the MJCF so make sure it is added to the worldbody we already added to the `mojo_model`. Any time you define a MJCF element, make sure it is referenced `mojo_model.mjcf` so that MuJoCo is aware of its existance!

We also define a light for _dramatic_ effect.

```python
--8<-- "docs/user-guides/examples/vlr/vlr_example.py:thin_wrapper"
```

---

!!! success

    We now have a partially defined model (at least with some stubs we know we will define next). We need to define a ground that our rocket will be landing on, we will do this next.
