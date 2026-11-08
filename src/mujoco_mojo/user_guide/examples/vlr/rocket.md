# Building the Rocket

!!! abstract

    This section walks through the first step in building our kinematically unconstrained (free falling) rocket body. It will setup the body on which we will be connecting a set of identical landing gear.

    Figure: The completed rocket landed on the ground. The rocket has a transparent blue cylinder representing the body tube and four identical red legs (defined later) with purple footpads. The yellow spheres on the tube and midway on the legs represent where the shock absorbers will be connected.

---

## Making the Body

The rocket is composed of a `body` and a set of `landing_gear` and is created with the `Rocket.new()` class method to keep form with the other constructors.

1. `mojo.BodyName`: A simple name to render in the viewer.
2. `mojo.GeomCylinder`: The body tube geometry defined with a radius and length
   - Its mass is declared to something reasonable.
3. `mojo.PoseEuler`: This type sets the initial position and orientation (when combined this is called a pose).
    - We also define a slight initial tip off angle of a few degrees.
    - There are many other ways to define an orientation such as quaternions, axis angles, etc.
4. `mojo.FreeJoint()`: This allows the body to move freely. Without this it would just be stuck in place.
    - _Try commenting this line out to see for yourself!_ You will see the body just levitates.
5. Finally, the body is appended to the list of `worldbody` bodies.

```python
class Rocket(mojo.UserData):
    """The rocket: a body tube with four landing gear legs mounted around it."""

    body: mojo.Body
    """The rocket's MJCF body: the body tube geometry, with a free joint so it can fall and land."""

    landing_gear: dict[Side, LandingGear]
    """The four landing gear legs, keyed by which side they're mounted on."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        assert mojo_model.mjcf.worldbody  # For type hinting

        # Make the body with the geometry
        # It is defined at STARTING_HEIGHT so that it has distance to the ground
        # and we use a FreeJoint so that it is free to move
        rocket_body = mojo.Body(
            name=mojo.BodyName("rocket"),
            geoms=[
                # Make a cylinder to represent the body tube
                # We use a Geom instead of a Site since it will have mass
                mojo.GeomCylinder(
                    size=INPUTS.tube.RADIUS,
                    fromto=np.array((0, 0, 0, 0, 0, INPUTS.tube.LENGTH)),
                    rgba=mojo.utils.Color.CYAN_500.with_alpha(0.2),
                    mass=1 * US.pound,
                )
            ],
            pose=mojo.PoseEuler(
                euler=np.array((5, 0, 0)),
                angle=mojo.Angle.DEGREE,
                pos=np.array((0, 0, INPUTS.STARTING_HEIGHT)),
            ),
            freejoints=[mojo.FreeJoint()],
        )
        mojo_model.mjcf.worldbody.bodies.append(rocket_body)

        # Add 4 symmetric sides around the rocket, each mounting one landing gear leg
        landing_gear: dict[Side, LandingGear] = {}
        for side_id in Side:
            # Make a new side for clocking around
            frame = mojo.Frame(
                name=mojo.FrameName(f"{side_id}_side"),
                pose=mojo.PoseEuler(
                    euler=np.array((0, 0, side_id.clocking_angle)),
                    angle=mojo.Angle.RADIAN,
                    pos=INPUTS.tube.RADIUS * side_id.pos,
                ),
            )
            rocket_body.frames.append(frame)

            # We no longer need to pass mojo_model around since we will be using
            # the newly made `frame` as our base object
            landing_gear[side_id] = LandingGear.new(frame, side_id)

        return cls(body=rocket_body, landing_gear=landing_gear)

```

---

!!! success

    We have defined the main free kinematic body we are studying. After defining the main body, we enter a for loop to define each side of the landing gear system. We will cover the building the landing gear next.
