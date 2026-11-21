"""The robotic arm, the same from either end: an end effector, a roll, yaw and pitch joint, a boom, the elbow, a boom, a pitch, yaw and roll joint, and an end effector. One end is latched onto the station's grapple fixture, and the other reaches for the visitor."""

from __future__ import annotations

from typing import Self

import numpy as np
from end_effector import END_EFFECTOR, EndEffector
from fixture import GrappleFixture
from shapes import CylinderInput, cylinder_mesh, lying_along

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()  # define a unit system used throughout the model

# each joint's housing is colored by the axis it turns about: red for roll (X), green for pitch (Y) and blue for yaw (Z), the colors a viewer draws for those axes
ROLL_COLOR = mojo.utils.Color.RED_500.rgba
PITCH_COLOR = mojo.utils.Color.GREEN_500.rgba
YAW_COLOR = mojo.utils.Color.BLUE_500.rgba

REACH_OPACITY = 0.02


# --8<-- [start:inputs]
class CameraInput(mojo.UserData):
    """Where the camera on the free end effector sits, in the end effector's frame, and how wide it sees. It looks along the end effector."""

    FOVY: float = 70
    """Vertical field of view, in degrees."""

    HEIGHT: float = 0.22 * US.m
    """How far the camera sits off the end effector's axis, clear of its radius, so the end effector stays out of the picture."""

    SETBACK: float = 0.1 * US.m
    """How far the camera sits behind the end effector's tip."""


class ArmInput(mojo.UserData):
    """Dimensions and masses of the arm's parts, from the station out. The end effector is `END_EFFECTOR`, in its own module, since both ends use it. The roll, yaw and pitch housings are the same at both ends of the arm."""

    roll: CylinderInput = CylinderInput(
        RADIUS=0.3 * US.m, LENGTH=0.4 * US.m, MASS=100 * US.kg
    )
    """The roll housing, a drum that runs from the joint out along the arm. The shoulder's runs from the base end effector's root to the shoulder, and the wrist's runs from the wrist to the free end effector's root."""

    yaw: CylinderInput = CylinderInput(
        RADIUS=0.22 * US.m, LENGTH=0.5 * US.m, MASS=60 * US.kg
    )
    """The yaw housing, a cylinder along the yaw axis and centered on the joint."""

    pitch: CylinderInput = CylinderInput(
        RADIUS=0.22 * US.m, LENGTH=0.5 * US.m, MASS=60 * US.kg
    )
    """The pitch housing, a cylinder along the pitch axis and centered on the joint."""

    boom_1: CylinderInput = CylinderInput(
        RADIUS=0.12 * US.m, LENGTH=3.0 * US.m, MASS=150 * US.kg
    )
    """The first boom, from the shoulder to the elbow."""

    elbow: CylinderInput = CylinderInput(
        RADIUS=0.2 * US.m, LENGTH=0.4 * US.m, MASS=40 * US.kg
    )
    """The elbow housing, a cylinder along the elbow's axis and centered on the joint."""

    boom_2: CylinderInput = CylinderInput(
        RADIUS=0.12 * US.m, LENGTH=3.0 * US.m, MASS=120 * US.kg
    )
    """The second boom, from the elbow to the wrist."""

    camera: CameraInput = CameraInput()
    """The camera on the free end effector. The base end effector has none."""

    @property
    def LENGTH(self) -> float:
        """The arm's length from end to end when it is straight: both end effectors, both roll housings and both booms. The free end can get no farther than this from the tip of the base end effector."""
        return (
            2 * END_EFFECTOR.LENGTH
            + 2 * self.roll.LENGTH
            + self.boom_1.LENGTH
            + self.boom_2.LENGTH
        )


ARM = ArmInput()
# --8<-- [end:inputs]


# the three housings are built here, once, and used at both ends of the arm, so the ends cannot differ
def roll_housing(name: str) -> mojo.GeomCylinder:
    """A roll joint's housing, a red drum that runs from the joint out along the arm."""
    return mojo.GeomCylinder(
        name=mojo.GeomName(name),
        size=ARM.roll.RADIUS,
        fromto=np.array((0, 0, 0, ARM.roll.LENGTH, 0, 0)),
        mass=ARM.roll.MASS,
        rgba=ROLL_COLOR,
    )


def yaw_housing(name: str) -> mojo.GeomCylinder:
    """A yaw joint's housing, a blue cylinder along the yaw axis (Z) and centered on the joint."""
    return mojo.GeomCylinder(
        name=mojo.GeomName(name),
        size=ARM.yaw.RADIUS,
        fromto=np.array((0, 0, -ARM.yaw.LENGTH / 2, 0, 0, ARM.yaw.LENGTH / 2)),
        mass=ARM.yaw.MASS,
        rgba=YAW_COLOR,
    )


def pitch_housing(name: str) -> mojo.GeomCylinder:
    """A pitch joint's housing, a green cylinder along the pitch axis (Y) and centered on the joint."""
    return mojo.GeomCylinder(
        name=mojo.GeomName(name),
        size=ARM.pitch.RADIUS,
        fromto=np.array((0, -ARM.pitch.LENGTH / 2, 0, 0, ARM.pitch.LENGTH / 2, 0)),
        mass=ARM.pitch.MASS,
        rgba=PITCH_COLOR,
    )


def out_of_station(pos: mojo.Vec3) -> mojo.PoseEuler:
    """A pose at `pos`, in the frame of the station's grapple fixture, whose X axis points out of the station. The fixture's own X axis points into the station, so this is half a revolution about Y."""
    return mojo.PoseEuler(euler=np.array((0, 180, 0)), angle=mojo.Angle.DEGREE, pos=pos)


# --8<-- [start:arm]
class Arm(mojo.UserData):
    """The robotic arm. In its own frame the arm points along +X, which is out of the station, and the roll joints turn about X, the yaw joints about Z and the pitch joints about Y."""

    body: mojo.Body
    """The arm's first body, the shoulder roll's, which sits at the root of the base end effector."""

    shoulder_roll: mojo.Joint
    """The shoulder's roll joint, about the arm's own axis."""

    shoulder_yaw: mojo.Joint
    """The shoulder's yaw joint."""

    shoulder_pitch: mojo.Joint
    """The shoulder's pitch joint."""

    elbow_pitch: mojo.Joint
    """The elbow's pitch joint, which bends the second boom toward or away from the first."""

    boom_1: mojo.GeomMesh
    """The first boom's volume, from the shoulder to the elbow."""

    boom_2: mojo.GeomMesh
    """The second boom's volume, from the elbow to the wrist."""

    wrist_pitch: mojo.Joint
    """The wrist's pitch joint."""

    wrist_yaw: mojo.Joint
    """The wrist's yaw joint."""

    wrist_roll: mojo.Joint
    """The wrist's roll joint, about the free end effector's own axis."""

    base_effector: EndEffector
    """The end effector at the base, latched onto the station's grapple fixture. Its tip site is at the fixture's site, with the same frame."""

    free_effector: EndEffector
    """The end effector at the free end, which reaches for the visitor's grapple fixture."""

    reach: mojo.GeomMesh
    """The reach envelope, a translucent hemisphere centered on the tip of the base end effector with the arm's full length as its radius. The free end can never get outside it."""

    camera: mojo.Camera
    """The camera on the free end effector, looking along it. Its `name` is what a video recorder needs."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel, base: GrappleFixture) -> Self:
        """Builds the arm and nests it in the frame of `base`, the station's grapple fixture."""
        # the booms are builtin cylinders and the reach envelope is a builtin hemisphere, which MuJoCo makes when it compiles the model: a cylinder lies along Z until it is laid down along the arm, and a hemisphere has its flat face on the origin and its dome along Z, with its radius set by the scale
        mojo_model.mjcf.assets.append(
            mojo.Asset(
                meshes=[
                    boom_1_mesh := cylinder_mesh(
                        "boom_1_mesh", ARM.boom_1.RADIUS, ARM.boom_1.LENGTH
                    ),
                    boom_2_mesh := cylinder_mesh(
                        "boom_2_mesh", ARM.boom_2.RADIUS, ARM.boom_2.LENGTH
                    ),
                    reach_mesh := mojo.MeshHemisphere(
                        name=mojo.MeshName("reach_mesh"),
                        resolution=8,
                        scale=np.full(3, ARM.LENGTH),
                    ),
                ]
            )
        )
        assert boom_1_mesh.name
        assert boom_2_mesh.name
        assert reach_mesh.name

        # each boom runs from its joint outward along the arm, so it is laid down along X and moved out by half its length
        boom_1 = mojo.GeomMesh(
            name=mojo.GeomName("boom_1_geom"),
            mesh=boom_1_mesh.name,
            pose=lying_along("x", center=np.array((ARM.boom_1.LENGTH / 2, 0, 0))),
            mass=ARM.boom_1.MASS,
            rgba=mojo.utils.Color.SLATE_200.rgba,
        )
        boom_2 = mojo.GeomMesh(
            name=mojo.GeomName("boom_2_geom"),
            mesh=boom_2_mesh.name,
            pose=lying_along("x", center=np.array((ARM.boom_2.LENGTH / 2, 0, 0))),
            mass=ARM.boom_2.MASS,
            rgba=mojo.utils.Color.SLATE_400.rgba,
        )

        # the end effector at the base is the same part as the one at the free end, latched onto the station's fixture the way the free one will latch onto the visitor's: its tip is at the fixture's site with the same frame, and it runs out of the station, so its root is one end effector length farther out
        root = base.site.pose.pos - np.array((END_EFFECTOR.LENGTH, 0, 0))
        base_effector = EndEffector.new(mojo_model, "base", mojo.PoseQuat(pos=root))
        base.frame.frames.append(base_effector.frame)

        # the reach envelope is a hemisphere with its flat face on the fixture's site and its dome pointing out of the station, and no mass or collisions of its own: the fixture's X axis points into the station, so turning the dome's Z axis a quarter revolution about Y the other way points it out
        reach = mojo.GeomMesh(
            name=mojo.GeomName("reach_geom"),
            mesh=reach_mesh.name,
            pose=mojo.PoseEuler(
                euler=np.array((0, -90, 0)),
                angle=mojo.Angle.DEGREE,
                pos=base.site.pose.pos,
            ),
            density=0,
            contype=0,
            conaffinity=0,
            rgba=mojo.utils.Color.TEAL_500.with_alpha(REACH_OPACITY),
        )
        base.frame.geoms.append(reach)

        # one body per joint, from the station out, so each joint turns everything after it: roll, then yaw, then pitch, starting at the root of the base end effector's far end
        roll_body = mojo.Body(
            name=mojo.BodyName("shoulder_roll"),
            pose=out_of_station(root),
            geoms=[roll_housing("shoulder_roll_geom")],
        )
        shoulder_roll = mojo.Joint(
            name=mojo.JointName("shoulder_roll"),
            type=mojo.JointType.HINGE,
            axis=np.array((1, 0, 0)),
        )
        roll_body.joints.append(shoulder_roll)

        # the yaw and pitch bodies sit at the shoulder, the far end of the roll housing, so all three axes meet there
        yaw_body = mojo.Body(
            name=mojo.BodyName("shoulder_yaw"),
            pose=mojo.PoseQuat(pos=np.array((ARM.roll.LENGTH, 0, 0))),
            geoms=[yaw_housing("shoulder_yaw_geom")],
        )
        shoulder_yaw = mojo.Joint(
            name=mojo.JointName("shoulder_yaw"),
            type=mojo.JointType.HINGE,
            axis=np.array((0, 0, 1)),
        )
        yaw_body.joints.append(shoulder_yaw)
        roll_body.bodies.append(yaw_body)

        # the pitch body carries the first boom
        pitch_body = mojo.Body(
            name=mojo.BodyName("shoulder_pitch"),
            geoms=[pitch_housing("shoulder_pitch_geom"), boom_1],
        )
        shoulder_pitch = mojo.Joint(
            name=mojo.JointName("shoulder_pitch"),
            type=mojo.JointType.HINGE,
            axis=np.array((0, 1, 0)),
        )
        pitch_body.joints.append(shoulder_pitch)
        yaw_body.bodies.append(pitch_body)

        # the elbow body sits at the end of the first boom, and carries the second boom and the elbow's housing, a cylinder along its pitch axis
        elbow_body = mojo.Body(
            name=mojo.BodyName("elbow_pitch"),
            pose=mojo.PoseQuat(pos=np.array((ARM.boom_1.LENGTH, 0, 0))),
            geoms=[
                mojo.GeomCylinder(
                    name=mojo.GeomName("elbow_geom"),
                    size=ARM.elbow.RADIUS,
                    fromto=np.array(
                        (0, -ARM.elbow.LENGTH / 2, 0, 0, ARM.elbow.LENGTH / 2, 0)
                    ),
                    mass=ARM.elbow.MASS,
                    rgba=PITCH_COLOR,
                ),
                boom_2,
            ],
        )
        elbow_pitch = mojo.Joint(
            name=mojo.JointName("elbow_pitch"),
            type=mojo.JointType.HINGE,
            axis=np.array((0, 1, 0)),
        )
        elbow_body.joints.append(elbow_pitch)
        pitch_body.bodies.append(elbow_body)

        # the wrist's three axes meet at the end of the second boom, so its bodies sit there: pitch, then yaw, then roll, with the same housings as the shoulder
        wrist_pitch_body = mojo.Body(
            name=mojo.BodyName("wrist_pitch"),
            pose=mojo.PoseQuat(pos=np.array((ARM.boom_2.LENGTH, 0, 0))),
            geoms=[pitch_housing("wrist_pitch_geom")],
        )
        wrist_pitch = mojo.Joint(
            name=mojo.JointName("wrist_pitch"),
            type=mojo.JointType.HINGE,
            axis=np.array((0, 1, 0)),
        )
        wrist_pitch_body.joints.append(wrist_pitch)
        elbow_body.bodies.append(wrist_pitch_body)

        wrist_yaw_body = mojo.Body(
            name=mojo.BodyName("wrist_yaw"),
            geoms=[yaw_housing("wrist_yaw_geom")],
        )
        wrist_yaw = mojo.Joint(
            name=mojo.JointName("wrist_yaw"),
            type=mojo.JointType.HINGE,
            axis=np.array((0, 0, 1)),
        )
        wrist_yaw_body.joints.append(wrist_yaw)
        wrist_pitch_body.bodies.append(wrist_yaw_body)

        # the roll body holds the roll housing, a drum from the wrist out along the arm like the shoulder's, and the free end effector is mounted at its far end, so the roll turns both
        wrist_roll_body = mojo.Body(
            name=mojo.BodyName("wrist_roll"),
            geoms=[roll_housing("wrist_roll_geom")],
        )
        free_effector = EndEffector.new(
            mojo_model, "free", mojo.PoseQuat(pos=np.array((ARM.roll.LENGTH, 0, 0)))
        )
        wrist_roll_body.frames.append(free_effector.frame)

        # the camera is only on the free end effector, in its frame so the roll turns it too: it sits just behind the tip and off the axis, and looks along the end effector (+X in its frame, with +Z up), so the grapple fixture grows in the picture as the end effector closes in
        eye = np.array((END_EFFECTOR.LENGTH - ARM.camera.SETBACK, 0, ARM.camera.HEIGHT))
        camera = mojo.Camera(
            name=mojo.CameraName("arm_camera"),
            fovy=ARM.camera.FOVY,
            pose=mojo.PoseQuat.look_at(
                target=eye + np.array((1, 0, 0)), eye=eye, roll=-90
            ),
        )
        free_effector.frame.cameras.append(camera)
        wrist_roll = mojo.Joint(
            name=mojo.JointName("wrist_roll"),
            type=mojo.JointType.HINGE,
            axis=np.array((1, 0, 0)),
        )
        wrist_roll_body.joints.append(wrist_roll)
        wrist_yaw_body.bodies.append(wrist_roll_body)

        # the shoulder hangs off the fixture, which is in the station's body, so it is fixed to the station
        base.frame.bodies.append(roll_body)

        return cls(
            body=roll_body,
            shoulder_roll=shoulder_roll,
            shoulder_yaw=shoulder_yaw,
            shoulder_pitch=shoulder_pitch,
            elbow_pitch=elbow_pitch,
            boom_1=boom_1,
            boom_2=boom_2,
            wrist_pitch=wrist_pitch,
            wrist_yaw=wrist_yaw,
            wrist_roll=wrist_roll,
            base_effector=base_effector,
            free_effector=free_effector,
            reach=reach,
            camera=camera,
        )


# --8<-- [end:arm]
