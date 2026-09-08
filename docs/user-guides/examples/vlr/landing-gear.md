# Assembling Landing Gear

!!! abstract

    This section walks through the final step in building the kinematic tree with the landing gear.

    <figure markdown="span">
        ![Rocket preview](./landed.jpg){ width="50%" height="auto" }
        <figcaption>The completed rocket landed on the ground. The rocket has a transparent blue cylinder representing the body tube and four identical red legs (defined later) with purple footpads. The yellow spheres on the tube and midway on the legs represent where the shock absorbers will be connected.</figcaption>
    </figure>

---

## Patterning around Rocket

We begin by defining an enumeration called `Side`. This `StrEnum` is used as a convenient way to ensure each side of the landing gear have different names as well as for convenient ways to define positions and clocking angles. It allows us to dynamically define the number of legs the rocket has as well as where they are located.

```python
--8<-- "docs/user-guides/examples/vlr/vlr_example.py:side"
```

Recall in the previous section that we defined a for loop to make each leg of the landing gear. We used `Side` to loop over all of the defined enumeration branches to make a body with a clocking angle and position. This is done by using `mojo.Frame` which allows us to define a single side in a simple reference frame, allowing the MuJoCo compiler to perform the frame rotations for us. This is nice (compared to defining each side around a body) since we won't carry around 4 `<body>` tags that are not even being used.

In this case we define a `Frame` at each clocking angle, extended one radius from the cylinder's centerline. Then we use the `LandingGear.new()` class method to make a leg in that `Frame`.

```python
--8<-- "docs/user-guides/examples/vlr/vlr_example.py:patterning"
```

---

## Adding a Leg

The landing gear we will be adding has a hinge at its root (right where we defined our `Frame`) and has two sites which we will use later to define a spring-damper to hold the landing gear open.

Because the `Frame` already carries each side's clocking rotation and offset from the tube, everything we define inside it can use simple, local coordinates. To define the leg we

1. Use `INPUTS.gear.ANGLE` to set the angle with the ground so the leg initially points down.
    - Try modifying this number and see how the legs change their initial orientation.
2. Define a `GeomBox` to be the leg (with a small mass) and `GeomSphere` to contact with our `Ground` plane.
3. Finally add the hinge at the root of the leg, oriented so it is horizontal.
4. Then append to the frame.

After adding the leg we also add two sites, one attached to the leg, and the other attached to the rocket body (via the frame). These will be used later when defining the runtime behavior of the legs since we will be attaching a spring between them.

```python
--8<-- "docs/user-guides/examples/vlr/vlr_example.py:landing_gear_kinematics"
```

---

!!! success

    We have fully defined the kinematic tree! This has all the linkages, joints, and bodies we need to simulate, but we are missing some key things like the springs and defining the runtime loop. See how to implement those in the next guide.
