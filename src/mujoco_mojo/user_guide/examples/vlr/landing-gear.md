# Assembling Landing Gear

!!! abstract

    This section walks through the final step in building the kinematic tree by building the landing gear.

---

## Patterning around Rocket

We begin by defining an enumeration called `Side`. This `StrEnum` is used as a convenient way to ensure each side of the landing gear has a different name, and to compute each side's clocking angle (its rotation around the tube's axis) and position from that name. It lets us loop over the four sides and compute each one's placement from a single definition, rather than repeating that logic four times.

```python
class Side(StrEnum):
    """
    One of the four positions, spaced evenly around the rocket's body tube,
    where a landing gear leg is mounted. Named after the world-frame
    direction each side faces: `PX`/`MX` face +X/-X, `PY`/`MY` face +Y/-Y.
    """

    PX = "px"
    MX = "mx"
    PY = "py"
    MY = "my"

    @property
    def clocking_angle(self) -> float:
        """Angle, in radians, of this side around the tube's Z axis."""
        match self:
            case Side.PX:
                return float(np.deg2rad(0))
            case Side.MX:
                return float(np.deg2rad(90))
            case Side.PY:
                return float(np.deg2rad(180))
            case Side.MY:
                return float(np.deg2rad(270))

    @property
    def pos(self) -> mojo.Vec3:
        """Unit vector, in the XY plane, pointing outward from the tube toward this side."""
        return np.array(
            (
                np.cos(self.clocking_angle),
                np.sin(self.clocking_angle),
                0,
            )
        )

```

Recall in the previous section that we defined a for loop to make each leg of the landing gear. We used `Side` to loop over all of the defined enumeration branches to make a body with a clocking angle and position. This is done by using `mojo.Frame` which allows us to define a single side in a simple reference frame, allowing the MuJoCo compiler to perform the frame rotations for us. This is nice (compared to defining each side around a body) since we do not have to carry around four `<body>` tags whose only purpose would be to hold a position and orientation.

In this case we define a `Frame` at each clocking angle, extended one radius from the cylinder's centerline. Then we use the `LandingGear.new()` class method to make a leg in that `Frame`.

```python
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
class LandingGear(mojo.UserData):
    """
    A single landing gear leg: a rigid leg with a footpad at the tip, hinged
    to the rocket body, with a spring connecting the leg back to the body to
    absorb the landing.
    """

    leg_spring_site: mojo.AnySite
    """Attachment point for the spring, on the leg."""

    tube_spring_site: mojo.AnySite
    """Attachment point for the spring, on the rocket body."""

    @classmethod
    def new(cls, frame: mojo.Frame, side_id: Side) -> Self:
        # Make a leg with a footpad angled at the ground
        body = mojo.Body(
            name=mojo.BodyName(f"{side_id}_leg"),
            pose=mojo.PoseEuler(
                # Rotate about Y so the leg points down and out at ANGLE
                # degrees from horizontal
                euler=np.array((0, INPUTS.gear.ANGLE, 0)),
                angle=mojo.Angle.DEGREE,
            ),
            geoms=[
                # Main leg geometry
                mojo.GeomBox(
                    size=np.array((INPUTS.gear.WIDTH / 2, 0, 0)),
                    fromto=np.array((0, 0, 0, INPUTS.gear.LENGTH, 0, 0)),
                    rgba=mojo.utils.Color.ROSE_500.with_alpha(0.5),
                    # A geom without an explicit mass/density defaults to the
                    # density of water (1000 kg/m^3), which would make this
                    # leg unrealistically heavy. 1.24 g/cm^3 is roughly a
                    # rigid engineering plastic (e.g. ABS/nylon).
                    density=1.24 * US["gram/cm^3"],
                ),
                # Footpad: the part of the leg that actually touches the ground
                mojo.GeomSphere(
                    size=INPUTS.gear.PAD_RADIUS,
                    pose=mojo.PoseQuat(pos=np.array((INPUTS.gear.LENGTH, 0, 0))),
                    rgba=mojo.utils.Color.PURPLE_500.rgba,
                    # Modeled as massless (density=0): its job is only to
                    # define the leg's contact surface, not to add inertia.
                    # Left at the default water density, it adds a lot of
                    # mass right at the tip of the leg (its maximum lever
                    # arm from the hinge), which makes landings look far
                    # more damped than they should.
                    density=0,
                ),
            ],
            joints=[
                # This joint allows the leg to pivot
                mojo.Joint(
                    name=mojo.JointName(f"{side_id}_leg_main_hinge"),
                    type=mojo.JointType.HINGE,
                    axis=np.array((0, 1, 0)),
                )
            ],
        )
        frame.bodies.append(body)

        # Make a site on the leg where one end of the spring will attach
        leg_site = mojo.SiteSphere(
            name=mojo.SiteName(f"{side_id}_leg_spring"),
            pose=mojo.PoseQuat(pos=np.array((INPUTS.gear.SPRING_LEG_OFFSET, 0, 0))),
            size=INPUTS.gear.WIDTH * 0.7,
            rgba=mojo.utils.Color.AMBER_500.rgba,
        )
        body.sites.append(leg_site)

        # Make another site on the rocket body for the other end of the spring
        tube_site = mojo.SiteSphere(
            name=mojo.SiteName(f"{side_id}_tube_spring"),
            pose=mojo.PoseQuat(pos=np.array((0, 0, INPUTS.gear.SPRING_VERT_OFFSET))),
            size=leg_site.size,
            rgba=leg_site.rgba,
        )
        frame.sites.append(tube_site)

        return cls(
            leg_spring_site=leg_site,
            tube_spring_site=tube_site,
        )
```

---

!!! success

    We have fully defined the kinematic tree! This has all the linkages, joints, and bodies we need to simulate, but we are missing some key things like the springs and defining the runtime loop. See how to implement those in the next guide.
