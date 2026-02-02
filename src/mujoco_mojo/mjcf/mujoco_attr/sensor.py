from typing import Optional, Sequence

from pydantic import Field

from mujoco_mojo.base import XMLModel
from mujoco_mojo.utils import is_empty_list

# import a bunch of stuff
from .sensor_attr.accelerometer import SensorAccelerometer
from .sensor_attr.actuatorfrc import SensorActuatorfrc
from .sensor_attr.actuatorpos import SensorActuatorpos
from .sensor_attr.actuatorvel import SensorActuatorvel
from .sensor_attr.ballangvel import SensorBallangvel
from .sensor_attr.ballquat import SensorBallquat
from .sensor_attr.camprojection import SensorCamprojection
from .sensor_attr.clock import SensorClock
from .sensor_attr.contact import SensorContact
from .sensor_attr.distance import SensorDistance
from .sensor_attr.e_kinetic import SensorEKinetic
from .sensor_attr.e_potential import SensorEPotential
from .sensor_attr.force import SensorForce
from .sensor_attr.frameangacc import SensorFrameangacc
from .sensor_attr.frameangvel import SensorFrameangvel
from .sensor_attr.framelinacc import SensorFramelinacc
from .sensor_attr.framelinvel import SensorFramelinvel
from .sensor_attr.framepos import SensorFramepos
from .sensor_attr.framequat import SensorFramequat
from .sensor_attr.framexaxis import SensorFramexaxis
from .sensor_attr.frameyaxis import SensorFrameyaxis
from .sensor_attr.framezaxis import SensorFramezaxis
from .sensor_attr.fromto import SensorFromto
from .sensor_attr.gyro import SensorGyro
from .sensor_attr.insidesite import SensorInsidesite
from .sensor_attr.jointactuatorfrc import SensorJointactuatorfrc
from .sensor_attr.jointlimitfrc import SensorJointlimitfrc
from .sensor_attr.jointlimitpos import SensorJointlimitpos
from .sensor_attr.jointlimitvel import SensorJointlimitvel
from .sensor_attr.jointpos import SensorJointpos
from .sensor_attr.jointvel import SensorJointvel
from .sensor_attr.magnetometer import SensorMagnetometer
from .sensor_attr.normal import SensorNormal
from .sensor_attr.plugin import SensorPlugin
from .sensor_attr.rangefinder import SensorRangefinder
from .sensor_attr.subtreeangmom import SensorSubtreeangmom
from .sensor_attr.subtreecom import SensorSubtreecom
from .sensor_attr.subtreelinvel import SensorSubtreelinvel
from .sensor_attr.tactile import SensorTactile
from .sensor_attr.tendonactuatorfrc import SensorTendonactuatorfrc
from .sensor_attr.tendonlimitfrc import SensorTendonlimitfrc
from .sensor_attr.tendonlimitpos import SensorTendonlimitpos
from .sensor_attr.tendonlimitvel import SensorTendonlimitvel
from .sensor_attr.tendonpos import SensorTendonpos
from .sensor_attr.tendonvel import SensorTendonvel
from .sensor_attr.torque import SensorTorque
from .sensor_attr.touch import SensorTouch
from .sensor_attr.user import SensorUser
from .sensor_attr.velocimeter import SensorVelocimeter

__all__ = ["Sensor"]


class Sensor(XMLModel):
    tag = "sensor"

    children = (
        "touches",
        "accelerometers",
        "velocimeters",
        "gyros",
        "forces",
        "torques",
        "magnetometers",
        "rangefinders",
        "camprojections",
        "jointposes",
        "jointvels",
        "tendonposes",
        "tendonvels",
        "actuatorposes",
        "actuatorvels",
        "actuatorfrcs",
        "jointactuatorfrcs",
        "tendonactuatorfrcs",
        "ballquats",
        "ballangvels",
        "jointlimitposes",
        "jointlimitvels",
        "jointlimitfrcs",
        "tendonlimitposes",
        "tendonlimitvels",
        "tendonlimitfrcs",
        "frameposes",
        "framequats",
        "framexaxes",
        "frameyaxes",
        "framezaxes",
        "framelinvels",
        "frameangvels",
        "framelinaccs",
        "frameangaccs",
        "subtreecoms",
        "subtreelinvels",
        "subtreeangmoms",
        "insidesites",
        "distances",
        "normals",
        "fromtos",
        "contacts",
        "tactiles",
        "e_potentials",
        "e_kinetics",
        "clocks",
        "users",
        "plugin",
    )

    touches: Sequence[SensorTouch] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorTouch."""

    accelerometers: Sequence[SensorAccelerometer] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorAccelerometer."""

    velocimeters: Sequence[SensorVelocimeter] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorVelocimeter."""

    gyros: Sequence[SensorGyro] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorGyro."""

    forces: Sequence[SensorForce] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorForce."""

    torques: Sequence[SensorTorque] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorTorque."""

    magnetometers: Sequence[SensorMagnetometer] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorMagnetometer."""

    rangefinders: Sequence[SensorRangefinder] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorRangefinder."""

    camprojections: Sequence[SensorCamprojection] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorCamprojection."""

    jointposes: Sequence[SensorJointpos] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorJointpos."""

    jointvels: Sequence[SensorJointvel] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorJointvel."""

    tendonposes: Sequence[SensorTendonpos] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorTendonpos."""

    tendonvels: Sequence[SensorTendonvel] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorTendonvel."""

    actuatorposes: Sequence[SensorActuatorpos] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorActuatorpos."""

    actuatorvels: Sequence[SensorActuatorvel] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorActuatorvel."""

    actuatorfrcs: Sequence[SensorActuatorfrc] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorActuatorfrc."""

    jointactuatorfrcs: Sequence[SensorJointactuatorfrc] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorJointactuatorfrc."""

    tendonactuatorfrcs: Sequence[SensorTendonactuatorfrc] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorTendonactuatorfrc."""

    ballquats: Sequence[SensorBallquat] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorBallquat."""

    ballangvels: Sequence[SensorBallangvel] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorBallangvel."""

    jointlimitposes: Sequence[SensorJointlimitpos] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorJointlimitpos."""

    jointlimitvels: Sequence[SensorJointlimitvel] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorJointlimitvel."""

    jointlimitfrcs: Sequence[SensorJointlimitfrc] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorJointlimitfrc."""

    tendonlimitposes: Sequence[SensorTendonlimitpos] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorTendonlimitpos."""

    tendonlimitvels: Sequence[SensorTendonlimitvel] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorTendonlimitvel."""

    tendonlimitfrcs: Sequence[SensorTendonlimitfrc] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorTendonlimitfrc."""

    frameposes: Sequence[SensorFramepos] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorFramepos."""

    framequats: Sequence[SensorFramequat] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorFramequat."""

    framexaxes: Sequence[SensorFramexaxis] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorFramexaxis."""

    frameyaxes: Sequence[SensorFrameyaxis] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorFrameyaxis."""

    framezaxes: Sequence[SensorFramezaxis] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorFramezaxis."""

    framelinvels: Sequence[SensorFramelinvel] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorFramelinvel."""

    frameangvels: Sequence[SensorFrameangvel] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorFrameangvel."""

    framelinaccs: Sequence[SensorFramelinacc] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorFramelinacc."""

    frameangaccs: Sequence[SensorFrameangacc] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorFrameangacc."""

    subtreecoms: Sequence[SensorSubtreecom] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorSubtreecom."""

    subtreelinvels: Sequence[SensorSubtreelinvel] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorSubtreelinvel."""

    subtreeangmoms: Sequence[SensorSubtreeangmom] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorSubtreeangmom."""

    insidesites: Sequence[SensorInsidesite] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorInsidesite."""

    distances: Sequence[SensorDistance] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorDistance."""
    normal: Sequence[SensorNormal] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorNormal."""

    fromto: Sequence[SensorFromto] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorFromto."""

    contact: Sequence[SensorContact] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorContact."""

    tactile: Sequence[SensorTactile] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorTactile."""

    e_potential: Sequence[SensorEPotential] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorEPotential."""

    e_kinetic: Sequence[SensorEKinetic] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorEKinetic."""

    clock: Sequence[SensorClock] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorClock."""

    user: Sequence[SensorUser] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """Grouping of SensorUser."""

    plugin: Optional[SensorPlugin] = None
    """Sensor plugin."""
