# Assembling Landing Gear

!!! abstract

    This section walks through the final step in building the kinematic tree by building the landing gear.

---

## Patterning around Rocket

We begin by defining an enumeration called `Side`. This `StrEnum` is used as a convenient way to ensure each side of the landing gear has a different name, and to compute each side's clocking angle (its rotation around the tube's axis) and position from that name. It lets us loop over the four sides and compute each one's placement from a single definition, rather than repeating that logic four times.

```python
--8<-- "docs/user-guides/examples/vlr/vlr_example.py:side"
```

Recall in the previous section that we defined a for loop to make each leg of the landing gear. We used `Side` to loop over all of the defined enumeration branches to make a body with a clocking angle and position. This is done by using `mojo.Frame` which allows us to define a single side in a simple reference frame, allowing the MuJoCo compiler to perform the frame rotations for us. This is nice (compared to defining each side around a body) since we do not have to carry around four `<body>` tags whose only purpose would be to hold a position and orientation.

In this case we define a `Frame` at each clocking angle, extended one radius from the cylinder's centerline. Then we use the `LandingGear.new()` class method to make a leg in that `Frame`.

```python
--8<-- "docs/user-guides/examples/vlr/vlr_example.py:patterning"
```

---

## Adding a Leg

The landing gear we will be adding has a hinge at its root (right where we defined our `Frame`) and has two sites which we will use later to attach a spring-damper acting as the leg's shock absorber.

Because the `Frame` already carries each side's clocking rotation and offset from the tube, everything we define inside it can use simple, local coordinates. To define the leg we

1. Use `INPUTS.gear.ANGLE` to set the angle with the ground so the leg initially points down.
    - Try modifying this number and see how the legs change their initial orientation.
2. Define a `GeomBox` to be the leg (with a small mass) and a `GeomSphere` to make contact with our `Ground` plane.
3. Finally add the hinge at the root of the leg, oriented so it is horizontal.
4. Then append to the frame.

After adding the leg we also add two sites, one attached to the leg, and the other attached to the rocket body (via the frame). These will be used later when defining the runtime behavior of the legs since we will be attaching a spring between them.

```python
--8<-- "docs/user-guides/examples/vlr/vlr_example.py:landing_gear_kinematics"
```

---

!!! success

    We have fully defined the kinematic tree! This has all the linkages, joints, and bodies we need to simulate, but we are missing some key things like the springs and defining the runtime loop. See how to implement those in the next guide.
