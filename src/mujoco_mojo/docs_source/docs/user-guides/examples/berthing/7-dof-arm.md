# 7-DOF Arm

!!! abstract

    This guide builds the arm: a shoulder with three degrees of freedom (DOF), two booms, an elbow with one DOF, and a wrist with three DOF, with an end effector at each end. The base end is latched onto the station's fixture, and the free end reaches for the visitor. Each of the seven joints has a position servo, and [`mink`](https://github.com/kevinzakka/mink), an inverse-kinematics library built on MuJoCo, works out the joint angles that move the free end effector to a goal position and orientation.

---

## End Effector

An end effector is a cylinder with a site on its end. To grab a grapple fixture, the arm lines this site up with the fixture's site. The arm has the same end effector at each end.

??? example "End Effector Inputs"

    ``` python
    class EndEffectorInput(CylinderInput):
        """Dimensions and mass of an end effector, and the size of its tip site."""

        RADIUS: float = 0.14 * US.m
        """Radius of the end effector."""

        LENGTH: float = 0.9 * US.m
        """Length of the end effector, from its root to its tip."""

        MASS: float = 40 * US.kg
        """Mass of the end effector."""

        TIP_SITE_SIZE: float = 0.04 * US.m
        """Radius of the sphere that marks the tip site."""


    END_EFFECTOR = EndEffectorInput()
    ```

``` python
class EndEffector(mojo.UserData):
    """A cylinder that runs along +X from its root to a site at its tip."""

    frame: mojo.Frame
    """The frame at the root, with its X axis along the end effector. Add it to the body it belongs to."""

    geom: mojo.GeomMesh
    """The end effector's volume."""

    tip: mojo.SiteSphere
    """The site at the tip, which meets a grapple fixture's site."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel, name: str, mount: mojo.AnyPose) -> Self:
        """Makes an end effector with its root at `mount`, a pose whose X axis is the direction it points. `name` prefixes the names of everything it makes."""
        mojo_model.mjcf.assets.append(
            mojo.Asset(meshes=[mesh := END_EFFECTOR.mesh(f"{name}_effector_mesh")])
        )
        assert mesh.name

        geom = mojo.GeomMesh(
            name=mojo.GeomName(f"{name}_effector_geom"),
            mesh=mesh.name,
            pose=lying_along("x", center=np.array((END_EFFECTOR.LENGTH / 2, 0, 0))),
            mass=END_EFFECTOR.MASS,
            rgba=mojo.utils.Color.SLATE_300.rgba,
        )

        # no rotation of its own, so the site's X axis points along the end effector, and a fixture's site points the same way when the two are joined
        tip = mojo.SiteSphere(
            name=mojo.SiteName(f"{name}_tip_site"),
            size=END_EFFECTOR.TIP_SITE_SIZE,
            pose=mojo.PoseQuat(pos=np.array((END_EFFECTOR.LENGTH, 0, 0))),
            rgba=mojo.utils.Color.AMBER_500.rgba,
        )

        frame = mojo.Frame(
            name=mojo.FrameName(f"{name}_effector"),
            pose=mount,
            geoms=[geom],
            sites=[tip],
        )
        return cls(frame=frame, geom=geom, tip=tip)


```

A frame at the end effector's root holds the cylinder and the site. Its X axis points along the end effector, from the root toward the site, and the site has the same orientation. When the arm grabs a fixture, the two sites line up and their X axes point the same way. As with the fixture, `mount` places the root and sets which way it points, and `name` prefixes everything the end effector makes.

---

## Inputs and Home Pose

Inputs for the arm hold the dimensions and masses of its parts, the servos, the camera, and the home pose.

??? example "Arm Inputs"

    ``` python
    class CameraInput(mojo.UserData):
        """Where the arm camera sits in the end effector's frame, and how wide it sees."""

        FOVY: float = 70
        """Vertical field of view, in degrees."""

        HEIGHT: float = 0.22 * US.m
        """How far the camera sits off the end effector's axis, clear of its radius."""

        SETBACK: float = 0.1 * US.m
        """How far the camera sits behind the tip."""


    class ServoInput(mojo.UserData):
        """The position servo on every joint."""

        KP: float = 2e5 * US["N*m/rad"]
        """Position gain, in torque per radian of error."""

        KV: float = 1e5 * US["N*m*s/rad"]
        """Velocity gain, in torque per radian per second, which damps the joint."""

        ARMATURE: float = 10 * US["kg*m**2"]
        """Armature of every joint, which keeps the lightest ones well behaved under high gains."""

        RANGE_DEG: float = 180
        """Largest angle a servo can be commanded to, in degrees either way."""

        SLEW_RATE_DEG: float = 8
        """Fastest a commanded angle may change, in degrees per second."""


    class HomeInput(mojo.UserData):
        """The angle of each joint when the model is built, in degrees. The arm is built bent like this, so every joint angle is measured from this home pose, and a servo commanded to zero holds it."""

        SHOULDER_ROLL: float = VISITOR.AZIMUTH_DEG - 70
        """Shoulder roll, which turns the plane the arm bends in."""

        SHOULDER_YAW: float = 0
        """Shoulder yaw."""

        SHOULDER_PITCH: float = 20
        """Shoulder pitch, which tilts the first boom away from straight out of the station."""

        ELBOW_PITCH: float = 130
        """Elbow pitch, which folds the second boom back toward the first."""

        WRIST_PITCH: float = -35
        """Wrist pitch."""

        WRIST_YAW: float = 0
        """Wrist yaw."""

        WRIST_ROLL: float = 0
        """Wrist roll."""


    class ArmInput(mojo.UserData):
        """Dimensions and masses of the arm's parts, from the station out. The roll, yaw and pitch housings are the same at both ends."""

        roll: CylinderInput = CylinderInput(
            RADIUS=0.3 * US.m, LENGTH=0.4 * US.m, MASS=100 * US.kg
        )
        """The roll housing, a drum along the arm from the joint outward."""

        yaw: CylinderInput = CylinderInput(
            RADIUS=0.22 * US.m, LENGTH=0.5 * US.m, MASS=60 * US.kg
        )
        """The yaw housing, a cylinder along the yaw axis, centered on the joint."""

        pitch: CylinderInput = CylinderInput(
            RADIUS=0.22 * US.m, LENGTH=0.5 * US.m, MASS=60 * US.kg
        )
        """The pitch housing, a cylinder along the pitch axis, centered on the joint."""

        boom_1: CylinderInput = CylinderInput(
            RADIUS=0.12 * US.m, LENGTH=3.0 * US.m, MASS=150 * US.kg
        )
        """The first boom, from the shoulder to the elbow."""

        elbow: CylinderInput = CylinderInput(
            RADIUS=0.2 * US.m, LENGTH=0.4 * US.m, MASS=40 * US.kg
        )
        """The elbow housing, a cylinder along the elbow's axis, centered on the joint."""

        boom_2: CylinderInput = CylinderInput(
            RADIUS=0.12 * US.m, LENGTH=3.0 * US.m, MASS=120 * US.kg
        )
        """The second boom, from the elbow to the wrist."""

        camera: CameraInput = CameraInput()
        """The camera on the free end effector."""

        servo: ServoInput = ServoInput()
        """The servo on each joint."""

        home: HomeInput = HomeInput()
        """The pose the arm starts in."""


    ARM = ArmInput()
    ```

Built bent into a V that points toward the visitor, the arm starts in its home pose, and every joint angle is measured from it. The home angles are part of the joint bodies' poses, so a servo commanded to zero holds the arm in the home pose.

???+ tip "Tip: Try Other Home Poses"

    `arm.py` has `HOME_POSES`, a set of start poses the arm was tested from: the default, a fully extended arm, an arm with the elbow folded back, an arm folded tightly, and six drawn at random. Each completes the berthing. Set `ARM.home = HOME_POSES["straight"]` before `generate` to try one.

---

## Joints

A few small helpers build the joints, and each is used many times:

- **Housings**, one each for roll, yaw and pitch, are the shapes at a joint. They are colored by the axis they turn about, red for roll (X), green for pitch (Y) and blue for yaw (Z), which makes each joint's axis visible in the viewer. The shoulder and the wrist have the same three, and building each housing once means the two ends cannot differ.
- `hinge` makes every joint. It gives each one the arm's armature, an added inertia that keeps the light joints stable under the servos' high gains, so the servos can be stiff. It also gives each joint the servos' range as a joint limit, which is how `mink` learns the range.
- `turned` places a joint's body at its home angle. The arm is built bent, so each body is turned from straight by its home angle about its own axis. This is how the home pose gets into the model.
- `out_of_station` places the whole arm. The station's fixture points into the station, but the arm should point out of it, so the first body is given a half turn about Y, and everything after it follows.

??? example "Helper Code"

    ``` python
    # the housings are built once and used at both ends, so the ends cannot differ
    def roll_housing(name: str) -> mojo.GeomCylinder:
        """A roll housing: a drum from the joint along the arm."""
        return mojo.GeomCylinder(
            name=mojo.GeomName(name),
            size=ARM.roll.RADIUS,
            fromto=np.array((0, 0, 0, ARM.roll.LENGTH, 0, 0)),
            mass=ARM.roll.MASS,
            rgba=ROLL_COLOR,
        )


    def yaw_housing(name: str) -> mojo.GeomCylinder:
        """A yaw housing: a cylinder along Z, centered on the joint."""
        return mojo.GeomCylinder(
            name=mojo.GeomName(name),
            size=ARM.yaw.RADIUS,
            fromto=np.array((0, 0, -ARM.yaw.LENGTH / 2, 0, 0, ARM.yaw.LENGTH / 2)),
            mass=ARM.yaw.MASS,
            rgba=YAW_COLOR,
        )


    def pitch_housing(name: str) -> mojo.GeomCylinder:
        """A pitch housing: a cylinder along Y, centered on the joint."""
        return mojo.GeomCylinder(
            name=mojo.GeomName(name),
            size=ARM.pitch.RADIUS,
            fromto=np.array((0, -ARM.pitch.LENGTH / 2, 0, 0, ARM.pitch.LENGTH / 2, 0)),
            mass=ARM.pitch.MASS,
            rgba=PITCH_COLOR,
        )


    def hinge(name: str, axis: tuple[float, float, float]) -> mojo.Joint:
        """A hinge joint about `axis`, with the arm's armature."""
        return mojo.Joint(
            name=mojo.JointName(name),
            type=mojo.JointType.HINGE,
            axis=np.array(axis),
            armature=ARM.servo.ARMATURE,
            limited=mojo.JointLimited.TRUE,
            # in degrees, the unit MuJoCo's compiler reads by default
            range=np.array((-ARM.servo.RANGE_DEG, ARM.servo.RANGE_DEG)),
        )


    def out_of_station(pos: mojo.Vec3) -> mojo.PoseEuler:
        """A pose at `pos` in the station fixture's frame whose X axis points out of the station."""
        # the fixture's X axis points into the station, so this is half a turn about Y
        return mojo.PoseEuler(euler=np.array((0, 180, 0)), angle=mojo.Angle.DEGREE, pos=pos)


    def turned(
        pos: mojo.Vec3, axis: Literal["x", "y", "z"], degrees: float
    ) -> mojo.PoseEuler:
        """The pose of a joint's body at `pos` when the joint is at its home angle: turned `degrees` about its own `axis`."""
        euler = np.zeros(3)
        euler["xyz".index(axis)] = degrees
        return mojo.PoseEuler(euler=euler, angle=mojo.Angle.DEGREE, pos=pos)


    ```

---

## Nesting the Bodies

This arm is a chain of bodies, one for each joint, starting at the station. Each body is a child of the one before it, so each joint turns everything after it. The shoulder has three DOF, so it has three bodies: roll, yaw and pitch. Their axes meet at one point:

``` python
# one body per joint, from the station out, so each joint turns everything after it
roll_body = mojo.Body(
    name=mojo.BodyName("shoulder_roll"),
    # turned out of the station, then rolled about its own X axis
    pose=out_of_station(root)
    * turned(np.zeros(3), "x", ARM.home.SHOULDER_ROLL),
    geoms=[roll_housing("shoulder_roll_geom")],
)
shoulder_roll = hinge("shoulder_roll", (1, 0, 0))
roll_body.joints.append(shoulder_roll)

# the yaw and pitch bodies sit at the shoulder, so all three axes meet there
yaw_body = mojo.Body(
    name=mojo.BodyName("shoulder_yaw"),
    pose=turned(np.array((ARM.roll.LENGTH, 0, 0)), "z", ARM.home.SHOULDER_YAW),
    geoms=[yaw_housing("shoulder_yaw_geom")],
)
shoulder_yaw = hinge("shoulder_yaw", (0, 0, 1))
yaw_body.joints.append(shoulder_yaw)
roll_body.bodies.append(yaw_body)

pitch_body = mojo.Body(
    name=mojo.BodyName("shoulder_pitch"),
    pose=turned(np.zeros(3), "y", ARM.home.SHOULDER_PITCH),
    geoms=[pitch_housing("shoulder_pitch_geom"), boom_1],
)
shoulder_pitch = hinge("shoulder_pitch", (0, 1, 0))
pitch_body.joints.append(shoulder_pitch)
yaw_body.bodies.append(pitch_body)
```

The rest of the chain follows the same pattern:

- **First boom:** a shape on the pitch body.
- **Elbow:** one body, which carries the elbow housing and the second boom.
- **Wrist:** three bodies, the same as the shoulder, hanging from the elbow body.
- **Free end effector:** attached to the last wrist body.
- **Base end effector:** latched onto the station's fixture, with its end at the fixture's site. The whole chain sits in the fixture's frame.

---

## Servos

Each joint gets a position servo. A servo pulls its joint toward a commanded angle using some gain, damping, and range:

``` python
limit = np.deg2rad(ARM.servo.RANGE_DEG)
arm.servos.extend(
    mojo.ActuatorPosition(
        name=mojo.ActuatorName(f"{joint.name}_servo"),
        joint=joint.name,
        kp=ARM.servo.KP,
        kv=ARM.servo.KV,
        ctrlrange=np.array((-limit, limit)),
    )
    for joint in arm.joints
)
mojo_model.mjcf.actuators.append(mojo.Actuator(positions=arm.servos))
```

---

## Driving the Servos

Commanded angles live in a list on the arm, one for each joint. Each servo gets an `ActuatorControl`, which copies its joint's commanded angle into the control array every step. `ActuatorControl` is one of Mojo's [loads](../../workflow/runtime-script.md#defining-loads).

``` python
def register_servos(self) -> None:
    """Hands each servo to the runtime, which reads its control value from the commanded angles every step. Call it inside the runtime manager's `with` block."""
    for i, servo in enumerate(self.servos):
        rt.ActuatorControl(
            name=f"{servo.name}_command",
            actuator=servo,
            control_func=lambda user_data, state, i=i: float(self._command[i]),
        ).register_to_rm()

```

The arm's methods change those commanded angles. `move_to` is the one that moves them, and it uses `mink`.

---

## Inverse Kinematics

Inverse kinematics finds the joint motion that puts the end effector at a goal. [`mink`](https://kevinzakka.github.io/mink/) is an established library for it, built on MuJoCo, so it reads the same compiled model as the simulation and the arm is described only once. The arm sets `mink` up with these pieces:

- A frame task asks the end effector's site to be at the goal, in position and orientation.
- A posture task pulls the joints weakly toward home. A goal does not fix all seven joints, because the elbow can swivel about the line from the shoulder to the wrist, so the pull picks one answer.
- A configuration limit keeps every joint inside its range, which `mink` reads from the model.
- A velocity limit caps how fast each joint moves.
- A collision avoidance limit slows any part of the arm that gets within a keep-out distance of the station or the visitor's hull, and `keep_clear_of` says which geoms those are. The free end effector may touch the visitor's grapple fixture, since that is its job, but no other part of the arm may.
- A frozen set of degrees of freedom holds everything that is not one of the arm's joints still, which here is the visitor's free joint. `mink` treats every degree of freedom in the model as something it can move, so without this it could satisfy a distance limit by pushing the visitor out of the arm's way.

`move_to` gives `mink` the goal, asks for the joint velocities, integrates them for one timestep, and copies the result into the commanded angles, so all the joints move at once. Mojo helps with the setup: `Joint.qpos_address` and `Joint.dof_address` say where each joint sits in the configuration and in the Jacobian.

``` python
def keep_clear_of(
    self,
    *obstacles: mojo.GeomMesh,
    grapple: mojo.GeomMesh,
) -> None:
    """Makes the arm keep clear of `obstacles`, and of `grapple` too, except that the free end effector may touch `grapple`. Call it before the first `move_to`."""
    self._obstacles = list(obstacles)
    self._grapple = grapple

def _keep_out(self, model: mujoco.MjModel) -> mink.CollisionAvoidanceLimit:
    """The limit that keeps the arm's geoms away from the obstacles."""
    assert self._grapple is not None
    arm = [
        int(g) for g in mink.get_subtree_geom_ids(model, self.body.get_id(model))
    ]
    free_end = self.free_effector.geom.get_id(model)
    obstacles = [obstacle.get_id(model) for obstacle in self._obstacles]
    return mink.CollisionAvoidanceLimit(
        model,
        geom_pairs=[
            (arm, obstacles),
            # the free end effector is meant to meet the grapple fixture, so it is left out
            ([g for g in arm if g != free_end], [self._grapple.get_id(model)]),
        ],
        minimum_distance_from_collisions=KEEP_OUT_DISTANCE,
        collision_detection_distance=KEEP_OUT_DETECTION,
    )

def _start_ik(self, state: mojo.MjState) -> None:
    """Sets up mink, starting from the state's configuration."""
    model = state.model
    q = state.data.qpos.copy()
    self._qpos_address = np.array([j.qpos_address(state) for j in self.joints])
    dof_address = np.array([j.dof_address(state) for j in self.joints])
    assert self.free_effector.tip.name

    self._configuration = mink.Configuration(model, q)
    self._frame_task = mink.FrameTask(
        frame_name=self.free_effector.tip.name,
        frame_type="site",
        position_cost=IK_POSITION_COST,
        orientation_cost=IK_ORIENTATION_COST,
    )

    # the goal leaves one joint free (the elbow can swivel about the line from shoulder to wrist), so a weak pull toward home picks one answer
    cost = np.zeros(model.nv)
    cost[dof_address] = IK_POSTURE_COST
    posture = mink.PostureTask(model, cost=cost)
    home = q.copy()
    home[self._qpos_address] = 0
    posture.set_target(home)

    self._other_qpos = np.setdiff1d(np.arange(model.nq), self._qpos_address)

    # with nothing holding it, the solver can satisfy a distance limit by moving the visitor away instead of the arm
    others = np.setdiff1d(np.arange(model.nv), dof_address)
    self._held = [mink.DofFreezingTask(model, [int(dof) for dof in others])]

    speeds: dict[str, float] = {}
    for joint in self.joints:
        assert joint.name
        speeds[joint.name] = np.deg2rad(ARM.servo.SLEW_RATE_DEG)
    self._tasks = [self._frame_task, posture]
    self._limits = [
        mink.ConfigurationLimit(model),
        mink.VelocityLimit(model, speeds),
    ]
    if self._obstacles:
        self._limits.append(self._keep_out(model))

def move_to(self, state: mojo.MjState, tip: mojo.Vec3, frame: mojo.Mat3) -> float:
    """Takes one step toward the end effector's site being at `tip` with orientation `frame`, both fixed in the world. Returns the distance the site still has to go."""
    if self._configuration is None:
        self._start_ik(state)
    assert self._configuration is not None
    assert self._frame_task is not None

    self._frame_task.set_target(
        mink.SE3.from_rotation_and_translation(
            mink.SO3.from_matrix(np.asarray(frame, dtype=float)),
            np.asarray(tip, dtype=float),
        )
    )
    # the visitor moves in the simulation but not in mink's copy, so bring it up to date
    q = self._configuration.q.copy()
    q[self._other_qpos] = state.data.qpos[self._other_qpos]
    self._configuration.update(q)

    timestep = state.model.opt.timestep
    velocity = mink.solve_ik(
        self._configuration,
        self._tasks,
        timestep,
        IK_SOLVER,
        damping=IK_DAMPING,
        limits=self._limits,
        constraints=self._held,
    )
    self._configuration.integrate_inplace(velocity, timestep)
    self._command[:] = self._configuration.q[self._qpos_address]
    return float(np.linalg.norm(self.free_effector.tip.rt_pos(state) - tip))

```

---

## Goals

`approach` calls `move_to` with a goal in front of a site, with the end effector facing it. The goal follows the site, so the arm keeps up if the visitor drifts:

``` python
def approach(
    self, state: mojo.MjState, site: mojo.SiteSphere, standoff: float
) -> float:
    """Takes one step toward the tip being `standoff` in front of `site`, facing it. Returns the distance the tip still has to go. `standoff` is measured back along the site's X axis, and facing means the tip's frame matches the site's. The goal follows the site, so it is no use once the tip holds the site: use `move_to` then."""
    frame = site.rt_xmat(state)
    return self.move_to(state, site.rt_pos(state) - standoff * frame[:, 0], frame)

```

`carry_to` is like `move_to`, but the goal travels to the target in a straight line at a set speed. That is how the arm carries the visitor. `misalignment` measures how far the end effector is from lining up with a site, and the runtime uses it to decide when the arm can move in.

---

## Camera

Only the free end has a camera. It is placed in the end effector's frame, so it turns with the wrist roll, and it is off the axis, so the end effector stays out of the picture. The [Video Recording](../../features/video-recording.md) guide covers filming a camera.

``` python
# only the free end has a camera: in the end effector's frame, so the roll turns it, and off the axis, so the end effector stays out of the picture
eye = np.array((END_EFFECTOR.LENGTH - ARM.camera.SETBACK, 0, ARM.camera.HEIGHT))
camera = mojo.Camera(
    name=mojo.CameraName("arm_camera"),
    fovy=ARM.camera.FOVY,
    pose=mojo.PoseQuat.look_at(
        target=eye + np.array((1, 0, 0)), eye=eye, roll=-90
    ),
)
free_effector.frame.cameras.append(camera)
```

---

!!! success

    That completes the arm, which can now be driven to a goal. In the last guide we write the runtime that runs the berthing.
