# Station and Visitor

!!! abstract

    This guide builds the station and the visiting vehicle. Each carries a grapple fixture: the arm's base attaches to the station's, and the arm grabs the visitor's. The guide also adds the sky, the sun and a fixed camera that follows the visitor. The arm is the next guide.

    Each part follows the pattern from the [introduction](introduction.md): the part is a `UserData` class, and a `new` method builds it into the model and returns it. Where a part has dimensions, they are in an input class. The values carry their units through `US`, as in [the rocket example](../vlr/introduction.md#inputs).

---

## Shared Helpers

[Proximity](../../features/proximity/proximity.md) measures distances between mesh volumes, so the station, the hull and the fixtures are meshes instead of primitive `Geom`s. MuJoCo can generate a mesh itself, so no mesh file is needed. `CylinderInput` holds the radius, length and mass of a cylindrical part, and its `mesh` method uses Mojo's `MeshCylinder` to make the mesh. A generated cylinder is built along Z, and `lying_along` gives the pose that turns one to lie along X or Y.

The helpers also hold the contact settings. Two geoms collide only if the `contype` of one shares a bit with the `conaffinity` of the other. The arm's parts offer bit 1 and accept none, so none touches another, which matters because the housings overlap at the joints. The hull, the station and the fixtures accept bit 1 and offer none, so the arm can touch them but they cannot touch each other.

??? example "Helper Code"

    ``` python
    # contact filtering: MuJoCo lets two geoms collide only if the `contype` of one shares a bit with the `conaffinity` of the other
    # the arm's parts offer bit 1 and accept none, so no part of the arm touches another, even where their volumes overlap at a joint
    ARM_CONTYPE = 1
    ARM_CONAFFINITY = 0
    # the hull, the station and the grapple fixtures accept bit 1 and offer none, so the arm touches them and they do not touch each other
    OBSTACLE_CONTYPE = 0
    OBSTACLE_CONAFFINITY = 1


    class CylinderInput(mojo.UserData):
        """Radius, length and mass of a cylinder."""

        RADIUS: float
        """Radius of the cylinder."""

        LENGTH: float
        """Length of the cylinder, along its axis."""

        MASS: float
        """Mass of the cylinder."""

        CELLS: int = 8
        """Cells along each axis of the mesh's grid. More cells make a finer mesh."""

        def mesh(self, name: str) -> mojo.MeshCylinder:
            """A builtin cylinder mesh along Z, centered on the origin."""
            # a builtin mesh spans (count - 1) * spacing along each axis, so count is one more than the cells
            cells = self.CELLS
            return mojo.MeshCylinder(
                name=mojo.MeshName(name),
                count=(cells + 1, cells + 1, cells + 1),
                spacing=np.array(
                    (2 * self.RADIUS / cells, 2 * self.RADIUS / cells, self.LENGTH / cells)
                ),
            )


    def lying_along(
        axis: Literal["x", "y"], center: mojo.Vec3 | None = None
    ) -> mojo.PoseEuler:
        """A pose at `center` that turns a mesh built along Z to lie along `axis`."""
        euler = {"x": (0, 90, 0), "y": (-90, 0, 0)}[axis]
        return mojo.PoseEuler(
            euler=np.array(euler),
            angle=mojo.Angle.DEGREE,
            pos=np.zeros(3) if center is None else center,
        )


    ```

---

## Grapple Fixture

A grapple fixture is a post that sticks out of a structure, with a site on its end for the arm to grab. The station has one, which the arm's base attaches to, and the visitor has one, which the arm takes hold of. The same class makes both.

??? example "Fixture Inputs"

    ``` python
    class FixtureInput(CylinderInput):
        """Dimensions and mass of a grapple fixture."""

        LENGTH: float = 0.4 * US.m
        """How far the post sticks out of the structure, which is the distance from the surface to the site."""

        RADIUS: float = 0.15 * US.m
        """Radius of the post."""

        MASS: float = 20 * US.kg
        """Mass of the post."""

        SITE_SIZE: float = 0.05 * US.m
        """Radius of the sphere that marks the site."""


    FIXTURE = FixtureInput()
    ```

``` python
class GrappleFixture(mojo.UserData):
    """A post sticking out of a structure, with a site at its tip."""

    frame: mojo.Frame
    """The frame where the post meets the structure, with its X axis pointing into the structure. Add it to the structure's body."""

    geom: mojo.GeomMesh
    """The post's volume."""

    site: mojo.SiteSphere
    """The site at the post's tip. Its X axis points into the structure. An end effector that grabs the fixture lines its own site up with this one, X axis to X axis."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel, name: str, mount: mojo.AnyPose) -> Self:
        """Makes a fixture at `mount`, a pose whose X axis points into the structure. `name` prefixes the names of everything it makes."""
        # longer than the part that shows, by the seat
        post = FIXTURE.model_copy(update={"LENGTH": FIXTURE.LENGTH + SEAT})
        mojo_model.mjcf.assets.append(
            mojo.Asset(meshes=[mesh := post.mesh(f"{name}_fixture_mesh")])
        )
        assert mesh.name

        # in the mount's frame the structure is on the +X side, so the post runs along -X from the seat to the tip
        geom = mojo.GeomMesh(
            name=mojo.GeomName(f"{name}_fixture_geom"),
            mesh=mesh.name,
            pose=lying_along("x", center=np.array(((SEAT - FIXTURE.LENGTH) / 2, 0, 0))),
            mass=FIXTURE.MASS,
            rgba=mojo.utils.Color.ORANGE_500.rgba,
            contype=OBSTACLE_CONTYPE,
            conaffinity=OBSTACLE_CONAFFINITY,
        )

        # no rotation of its own, so the site's X axis is the mount's
        site = mojo.SiteSphere(
            name=mojo.SiteName(f"{name}_grapple_site"),
            size=FIXTURE.SITE_SIZE,
            pose=mojo.PoseQuat(pos=np.array((-FIXTURE.LENGTH, 0, 0))),
            rgba=mojo.utils.Color.ORANGE_500.rgba,
        )

        frame = mojo.Frame(
            name=mojo.FrameName(f"{name}_fixture"),
            pose=mount,
            geoms=[geom],
            sites=[site],
        )
        return cls(frame=frame, geom=geom, site=site)


```

---

## Station

A station is one fixed body: a cylinder mesh that lies along Y, a grapple fixture on top for the arm's base, and the berthing point. The berthing point is a site where the arm will bring the visitor's grapple site.

??? example "Station Inputs"

    ``` python
    class StationInput(CylinderInput):
        """Dimensions of the station."""

        RADIUS: float = 0.8 * US.m
        """Radius of the station's cylinder."""

        LENGTH: float = 6.0 * US.m
        """Length of the station's cylinder, which lies along Y and is centered on the origin."""

        MASS: float = 400_000 * US.kg
        """Mass of the station's cylinder. It has no effect, since the station is fixed in the world."""

        BERTH_POSITION: tuple[float, float, float] = (3.0 * US.m, 0.0 * US.m, 1.5 * US.m)
        """Where the visitor's grapple site is brought to, as X, Y and Z in the world. It must be far enough out for the end effector, which lies behind the site, to clear the station."""


    STATION = StationInput()
    ```

``` python
class Station(mojo.UserData):
    """The station's cylinder, the grapple fixture for the arm's base and the berthing point, in one fixed body."""

    body: mojo.Body
    """The station's body, fixed in the world."""

    cylinder: mojo.GeomMesh
    """The station's cylinder."""

    fixture: GrappleFixture
    """The grapple fixture the arm's base attaches to. Its site's X axis points down into the station."""

    berth: mojo.SiteSphere
    """The berthing point, a marker for where the visitor goes. Its X axis points away from the station."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        assert mojo_model.mjcf.worldbody  # for type hinting

        mojo_model.mjcf.assets.append(
            mojo.Asset(meshes=[mesh := STATION.mesh("station_mesh")])
        )
        assert mesh.name

        cylinder = mojo.GeomMesh(
            name=mojo.GeomName("station_geom"),
            mesh=mesh.name,
            pose=lying_along("y"),
            mass=STATION.MASS,
            rgba=mojo.utils.Color.SLATE_500.with_alpha(OPACITY),
            contype=OBSTACLE_CONTYPE,
            conaffinity=OBSTACLE_CONAFFINITY,
        )

        # turned so the fixture's X axis points down into the station
        fixture = GrappleFixture.new(
            mojo_model,
            "station",
            mojo.PoseEuler(
                euler=np.array((0, 90, 0)),
                angle=mojo.Angle.DEGREE,
                pos=np.array((0, 0, STATION.RADIUS)),
            ),
        )

        # no rotation of its own, so its X axis points away from the station, and so does the visitor's once it is berthed
        berth = mojo.SiteSphere(
            name=mojo.SiteName("berth_site"),
            size=0.1 * US.m,
            pose=mojo.PoseQuat(pos=np.array(STATION.BERTH_POSITION)),
            rgba=mojo.utils.Color.LIME_400.rgba,
        )

        body = mojo.Body(
            name=mojo.BodyName("station"),
            geoms=[cylinder],
            sites=[berth],
            frames=[fixture.frame],
        )
        mojo_model.mjcf.worldbody.bodies.append(body)

        return cls(body=body, cylinder=cylinder, fixture=fixture, berth=berth)


```

---

## Visitor

A visitor is a cylindrical hull that lies along Y, with a grapple fixture on the side that faces the station. Its body has a free joint, so it can move. Since the model has no gravity, it stays at its initial position until the arm grapples and moves it.

??? example "Visitor Inputs"

    ``` python
    class VisitorInput(mojo.UserData):
        """Dimensions, mass and starting place of the visitor."""

        hull: CylinderInput = CylinderInput(
            RADIUS=0.9 * US.m, LENGTH=3.0 * US.m, MASS=1500 * US.kg
        )
        """The hull, a cylinder that lies along Y."""

        RANGE: float = 6.0 * US.m
        """Horizontal distance from the shoulder's axis to the hull's center."""

        AZIMUTH_DEG: float = 20
        """Direction of the hull from the shoulder's axis, in degrees from the station's X axis. The visitor's X axis points this way."""

        HEIGHT: float = 1.5 * US.m
        """Height of the hull's center above the station's center line."""


    VISITOR = VisitorInput()
    ```

``` python
class Visitor(mojo.UserData):
    """A cylindrical hull with a grapple fixture, free to drift. Its X axis points away from the station."""

    body: mojo.Body
    """The visitor's body, with a free joint."""

    hull: mojo.GeomMesh
    """The hull's volume."""

    fixture: GrappleFixture
    """The grapple fixture on the side of the hull that faces the station."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        assert mojo_model.mjcf.worldbody  # for type hinting

        mojo_model.mjcf.assets.append(
            mojo.Asset(meshes=[hull_mesh := VISITOR.hull.mesh("hull_mesh")])
        )
        assert hull_mesh.name

        hull = mojo.GeomMesh(
            name=mojo.GeomName("hull_geom"),
            mesh=hull_mesh.name,
            pose=lying_along("y"),
            mass=VISITOR.hull.MASS,
            rgba=mojo.utils.Color.CYAN_500.with_alpha(OPACITY),
            contype=OBSTACLE_CONTYPE,
            conaffinity=OBSTACLE_CONAFFINITY,
        )

        # the station is on the body's -X side, so the fixture is mounted there, and the body's X axis already points into the hull
        fixture = GrappleFixture.new(
            mojo_model,
            "visitor",
            mojo.PoseQuat(pos=np.array((-VISITOR.hull.RADIUS, 0, 0))),
        )

        # the body faces along the line from the shoulder's axis out through its center
        azimuth = np.deg2rad(VISITOR.AZIMUTH_DEG)
        center = np.array(
            (
                VISITOR.RANGE * np.cos(azimuth),
                VISITOR.RANGE * np.sin(azimuth),
                VISITOR.HEIGHT,
            )
        )
        body = mojo.Body(
            name=mojo.BodyName("visitor"),
            pose=mojo.PoseEuler(
                euler=np.array((0, 0, VISITOR.AZIMUTH_DEG)),
                angle=mojo.Angle.DEGREE,
                pos=center,
            ),
            geoms=[hull],
            frames=[fixture.frame],
            freejoints=[mojo.FreeJoint()],
        )
        mojo_model.mjcf.worldbody.bodies.append(body)

        return cls(body=body, hull=hull, fixture=fixture)


```

---

## Sky and Overview Camera

Two small parts finish the scene. `Environment` is a dark gradient sky and the sun, a directional light that illuminates everything. `Overview` is a fixed camera that pivots to keep the center of mass of the arm's free end in view, which is how the [overview video](introduction.md) follows the action. It is built after the arm, since it aims at one of the arm's bodies. [Video Recording](../../features/video-recording/video-recording.md) covers filming a camera.

??? example "Sky and Overview Camera Code"

    ``` python
    class Environment(mojo.UserData):
        """The sky behind everything and the sun that lights it."""

        sky: mojo.TextureBuiltIn
        """The skybox texture, a gradient."""

        sun: mojo.Light
        """The sun, a directional light, so its position does not matter."""

        @classmethod
        def new(cls, mojo_model: mojo.MojoModel) -> Self:
            assert mojo_model.mjcf.worldbody  # for type hinting

            # the viewer finds a skybox on its own, so nothing refers to it by name
            sky = mojo.TextureBuiltIn(
                name=mojo.TextureName("sky"),
                type=mojo.TextureType.SKYBOX,
                builtin=mojo.TextureBuiltInType.GRADIENT,
                width=16,
                height=16,
                rgb1=mojo.utils.Color.SLATE_700.rgb,
                rgb2=mojo.utils.Color.SLATE_950.rgb,
            )
            mojo_model.mjcf.assets.append(mojo.Asset(textures=[sky]))

            sun = mojo.Light(
                name=mojo.LightName("sun"),
                type=mojo.LightType.DIRECTIONAL,
                dir=np.array((-0.4, 0.4, -0.8)),
            )
            mojo_model.mjcf.worldbody.lights.append(sun)

            return cls(sky=sky, sun=sun)


    ```

    ``` python
    class Overview(mojo.UserData):
        """A camera fixed in the world that turns to keep the center of mass of the arm's free end in view."""

        camera: mojo.Camera
        """The camera. Its `name` is what a video recorder needs."""

        @classmethod
        def new(cls, mojo_model: mojo.MojoModel, target: mojo.Body) -> Self:
            """Makes the camera and puts it in the world, aimed at `target`."""
            assert mojo_model.mjcf.worldbody  # for type hinting
            assert target.name

            # in this mode MuJoCo works out the orientation, so only the position is given
            camera = mojo.Camera(
                name=mojo.CameraName("overview"),
                mode=mojo.TrackingMode.TARGETBODYCOM,
                target=target.name,
                fovy=OVERVIEW.FOVY,
                pose=mojo.PoseQuat(pos=np.array(OVERVIEW.POSITION)),
            )
            mojo_model.mjcf.worldbody.cameras.append(camera)

            return cls(camera=camera)


    ```

---

!!! success

    That completes the scene. In the next guide we build the arm.
