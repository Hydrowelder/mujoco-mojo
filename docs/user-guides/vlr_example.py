"""
Example: a vertically-landing rocket (VLR) with spring-damped landing gear.

The rocket body free-falls from `Inputs.STARTING_HEIGHT`, then its four legs
absorb the landing through a spring at each leg plus contact with the ground
through a footpad.

This file mixes two things that are worth telling apart while reading it:
the physics/model definition itself (the `TubeInput`, `GearInput`, `Side`,
`LandingGear`, `Rocket`, `Ground`, and `VLRModel` classes describe what is
being built), and the mujoco_mojo authoring pattern (`generate()` and
`runtime()` are the two entry points mujoco_mojo calls to build and then
simulate a model). Comments starting with "Mojo:" call out that second,
library-usage kind of detail rather than rocket physics.
"""

# --8<-- [start:imports]
from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Self

import numpy as np
from pydantic import Field

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

logger = mojo.utils.get_logger(__name__)
US = mojo.UnitSystem.si()  # Define a unit system used throughout the model

# Contact groups for `contype`/`conaffinity` on the geoms below. MuJoCo only
# generates a contact between two geoms if one's `contype` bit overlaps the
# other's `conaffinity` bits. We use these so the ground can touch both the
# rocket body and the legs, while the body and legs never touch each other.
GROUND = 0b001
TUBE = 0b010
GEAR = 0b100
# --8<-- [end:imports]


# --8<-- [start:inputs]


class TubeInput(mojo.UserData):
    """Physical dimensions of the rocket's cylindrical body tube."""

    DIAMETER: float = 3 * US.inch
    """Outer diameter of the body tube."""

    LENGTH: float = 1 * US.foot
    """Length of the body tube."""

    @property
    def RADIUS(self) -> float:
        """Outer radius of the body tube, derived from `DIAMETER`."""
        return self.DIAMETER / 2


class GearInput(mojo.UserData):
    """Physical dimensions and layout of a single landing gear leg."""

    ANGLE: float = 30
    """Angle, in degrees, between the leg and the rocket's body tube at rest. 0 would fold the leg flat against the tube; 90 would point it straight out, perpendicular to the tube."""

    LENGTH: float = 6 * US.inch
    """Length of the leg, from its hinge to the footpad."""

    WIDTH: float = 1 * US.inch
    """Width of the leg's square cross-section."""

    SPRING_LEG_OFFSET: float = 3 * US.inch
    """Distance along the leg, measured from its hinge, where the spring attaches."""

    SPRING_VERT_OFFSET: float = 4 * US.inch
    """Height along the body tube, measured from the leg's hinge, where the spring's other end attaches."""

    PAD_DIAMETER: float = 2 * US.inch
    """Diameter of the footpad sphere at the tip of the leg."""

    @property
    def PAD_RADIUS(self) -> float:
        """Radius of the footpad, derived from `PAD_DIAMETER`."""
        return self.PAD_DIAMETER / 2

    @property
    def SPRING_INIT_LENGTH(self) -> float:
        """
        Distance between the spring's two attachment sites when the leg is
        at its resting `ANGLE` — i.e. the spring's natural (rest) length.

        The leg's hinge and the spring's two attachment points form a
        side-angle-side triangle: we know both side lengths (`SPRING_LEG_OFFSET`
        and `SPRING_VERT_OFFSET`) and the angle between them (`ANGLE + 90`,
        since at `ANGLE = 0` the leg sticks out horizontally, perpendicular
        to the vertical tube). The law of cosines then gives the third side.
        """
        b = self.SPRING_LEG_OFFSET
        c = self.SPRING_VERT_OFFSET
        angle = np.deg2rad(self.ANGLE + 90)
        return np.sqrt(b**2 + c**2 - 2 * b * c * np.cos(angle))


class Inputs(mojo.UserData):
    """Top-level physical inputs for the vertically-landing rocket model."""

    tube: TubeInput = Field(default_factory=TubeInput)
    """Dimensions of the rocket's body tube."""

    gear: GearInput = Field(default_factory=GearInput)
    """Dimensions and layout of each landing gear leg."""

    STARTING_HEIGHT: float = 10 * US.foot
    """Height above the ground the rocket starts the simulation at, in free fall."""


INPUTS = Inputs()
# --8<-- [end:inputs]


# --8<-- [start:landing_gear]
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
                return np.deg2rad(0)
            case Side.MX:
                return np.deg2rad(180)
            case Side.PY:
                return np.deg2rad(90)
            case Side.MY:
                return np.deg2rad(270)

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


class LandingGear(mojo.UserData):
    """
    A single landing gear leg: a rigid leg with a footpad at the tip, hinged
    to the rocket body, with a spring connecting the leg back to the body to
    absorb the landing.
    """

    side_id: Side
    """Which of the four sides this leg is mounted on."""

    body: mojo.Body
    """The leg's MJCF body, containing its geometry and hinge joint."""

    leg_spring_site: mojo.AnySite
    """Attachment point for the spring, on the leg."""

    tube_spring_site: mojo.AnySite
    """Attachment point for the spring, on the rocket body."""

    @classmethod
    def new(cls, side: mojo.Body, side_id: Side) -> Self:

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
                    contype=GEAR,
                    conaffinity=GROUND,
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
                    contype=GEAR,
                    conaffinity=GROUND,
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
        side.bodies.append(body)

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
        side.sites.append(tube_site)

        return cls(
            side_id=side_id,
            body=body,
            leg_spring_site=leg_site,
            tube_spring_site=tube_site,
        )

    def add_spring(self) -> None:
        """Attach a linear spring-damper between this leg and the rocket body, acting as its shock absorber."""
        rt.PointToPointForce.ideal_spring(
            name=f"{self.side_id}_spring",
            action_site=self.leg_spring_site,
            xtion_site=self.tube_spring_site,
            stiffness=1e1 * US["lbf/inch"],
            damping=1e-1 * US["lbf*s/in"],
            rest_length=INPUTS.gear.SPRING_INIT_LENGTH,
        ).register_to_rm()


# --8<-- [end:landing_gear]


# --8<-- [start:rocket]
class Rocket(mojo.UserData):
    """The rocket: a body tube with four landing gear legs mounted around it."""

    body: mojo.Body
    """The rocket's MJCF body: the body tube geometry, with a free joint so it can fall and land."""

    landing_gear: dict[Side, LandingGear]
    """The four landing gear legs, keyed by which side they're mounted on."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        assert mojo_model.mjcf.worldbody  # For type hinting

        # Make a cylinder to represent the body tube
        # We use a Geom instead of a Site since it will have mass
        body_tube = mojo.GeomCylinder(
            size=INPUTS.tube.RADIUS,
            fromto=np.array((0, 0, 0, 0, 0, INPUTS.tube.LENGTH)),
            rgba=mojo.utils.Color.CYAN_500.with_alpha(0.2),
            mass=1 * US.pound,
            contype=TUBE,
            conaffinity=GROUND,
        )

        # Make the body with the geometry
        # It is defined at STARTING_HEIGHT so that it has distance to the ground
        # and we use a FreeJoint so that it is free to move
        rocket_body = mojo.Body(
            name=mojo.BodyName("rocket"),
            pose=mojo.PoseQuat(pos=np.array((0, 0, INPUTS.STARTING_HEIGHT))),
            freejoints=[mojo.FreeJoint()],
            geoms=[body_tube],
        )
        mojo_model.mjcf.worldbody.bodies.append(rocket_body)

        # Add 4 symmetric sides around the rocket, each mounting one landing gear leg
        landing_gear: dict[Side, LandingGear] = {}
        for side_id in Side:
            angle = side_id.clocking_angle
            # Make a new side for clocking around
            side = mojo.Body(
                name=mojo.BodyName(f"{side_id}_side"),
                pose=mojo.PoseEuler(
                    euler=np.array((0, 0, angle)),
                    angle=mojo.Angle.RADIAN,
                    pos=INPUTS.tube.RADIUS * side_id.pos,
                ),
            )
            rocket_body.bodies.append(side)

            # We no longer need to pass mojo_model around since we will be using
            # the newly made side as our base object
            landing_gear[side_id] = LandingGear.new(side, side_id)
        return cls(body=rocket_body, landing_gear=landing_gear)


# --8<-- [end:rocket]


# --8<-- [start:ground]
class Ground(mojo.UserData):
    """
    Definition of the ground plane.

    Also used for setting up other parts of the world like the skybox.
    """

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        assert mojo_model.mjcf.worldbody  # For type hinting

        # Configure ground grid and plane
        mojo_model.mjcf.assets.append(
            mojo.Asset(
                textures=[
                    grid_tex := mojo.TextureBuiltIn(
                        name=mojo.TextureName("grid_tex"),
                        type=mojo.TextureType.D2,
                        builtin=mojo.TextureBuiltInType.CHECKER,
                        width=1024,
                        height=1024,
                        rgb1=mojo.utils.Color.SLATE_400.rgb,
                        rgb2=mojo.utils.Color.SLATE_600.rgb,
                    )
                ],
                materials=[
                    grid_mat := mojo.Material(
                        name=mojo.MaterialName("grid_mat"),
                        texture=grid_tex.name,
                        texrepeat=np.array((1, 1)),
                    )
                ],
            )
        )
        mojo_model.mjcf.worldbody.geoms.append(
            mojo.GeomPlane(
                name=mojo.GeomName("floor"),
                size=np.array([0, 0, 0.1]),
                pose=mojo.PoseQuat(pos=np.array((0.5 * US.m, 0.5 * US.m, 0))),
                material=grid_mat.name,
                contype=GROUND,
                conaffinity=TUBE | GEAR,
            ),
        )
        mojo_model.mjcf.worldbody.lights.append(
            mojo.Light(
                pos=mojo.Pos(np.array((0, 0, 10 * US.foot + INPUTS.STARTING_HEIGHT)))
            )
        )

        # Optionally add an interesting skybox
        # Mojo: `is_nominal` is only true for the single baseline trial, not
        # any randomized Monte Carlo variations, so this only runs once
        if mojo_model.is_nominal:
            skybox_folder = (mojo.DepPath() / "textures" / "stars").resolve()
            mojo_model.mjcf.assets.append(
                mojo.Asset(
                    textures=[
                        mojo.Texture(
                            name=mojo.TextureName("skybox_texture_colors"),
                            type=mojo.TextureType.SKYBOX,
                            fileback=skybox_folder / "nz.png",
                            filedown=skybox_folder / "ny.png",
                            filefront=skybox_folder / "pz.png",
                            fileleft=skybox_folder / "nx.png",
                            fileright=skybox_folder / "px.png",
                            fileup=skybox_folder / "py.png",
                        )
                    ]
                ),
            )
        return cls()


# --8<-- [end:ground]


# --8<-- [start:thin_wrapper]
class VLRModel(mojo.UserData):
    """
    Root user-data container for the whole model.

    Mojo: `generate()` builds this and stores it on `mojo_model.user_data`;
    `runtime()` later reads it back out via `mojo_model.get_user_data()` to
    get at the MJCF pieces (sites, bodies) it needs to attach forces to and
    step the simulation.
    """

    ground: Ground
    """The ground plane and world setup (skybox, lights)."""

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
        return cls(ground=ground, rocket=rocket, camera=camera_name)


# --8<-- [end:thin_wrapper]


# --8<-- [start:generate]
def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """
    Generates the MJCF model and samples distributions.

    Mojo: this is one of the two entry points mujoco_mojo calls for every
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
    )  # BUG need to fix
    return mojo_model


# --8<-- [end:generate]


# --8<-- [start:runtime]
# --8<-- [start:runtime-handle]
def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    """
    Executes the physics simulation.

    Mojo: the other entry point mujoco_mojo calls for every trial, after
    `generate()` has built and compiled the MJCF model. `state` wraps the
    live `mjModel`/`mjData`; `runtime_manager` (opened as `rm` below) is
    what forces and recorders get registered against and what actually
    advances the simulation each `rm.step()`.
    """
    # --8<-- [end:runtime-handle]
    with runtime_manager as rm:
        vlr_model = mojo_model.get_user_data(VLRModel)
        assert mojo_model.mjcf.worldbody  # For type hinting

        # Attach each leg's shock-absorber spring now that the model is compiled
        for gear in vlr_model.rocket.landing_gear.values():
            gear.add_spring()

        # Mojo: only record a video for the single baseline trial, not every
        # randomized Monte Carlo variation
        if mojo_model.is_nominal:
            rt.VideoRecorder(
                path=mojo_model.trial_dir / "video.mp4", camera_name=vlr_model.camera
            ).setup(state).register_to_rm()
        while state.data.time < 4.0:
            rm.step(state)
        # --8<-- [end:stepping]

    return mojo_model


# --8<-- [end:runtime]

# --8<-- [start:main]
if __name__ == "__main__":
    mojo.utils.setup_logger()
    workdir = Path(__file__).parent / "monte_carlo_study"

    runner = mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
        workdir=workdir,
        config=mojo.utils.MonteCarloConfig(n_trial=10, n_proc=1),
    )

    runner.run(clean_workdir=True)
# --8<-- [end:main]
