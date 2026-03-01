from pydantic import model_validator

from mujoco_mojo.mjcf.mujoco_attr.sensor_attr.base import SensorBase
from mujoco_mojo.typing import BodyName, ContactData, ContactReduce, GeomName, SiteName
from mujoco_mojo.utils.logging import get_logger

logger = get_logger(__name__)

__all__ = ["SensorContact"]


class SensorContact(SensorBase):
    """
    !!! quote "Motivation"
        The array of contacts which occur during the main dynamics pipeline is inherently variable-sized. The purpose of the contact sensor is to report contact-related information in a fixed-size array. This is useful as input to learning-based agents and in environment logic.

        Unlike the purely geometric collision sensors that act independently of the dynamics pipeline, the contact sensor reports information that was discovered during the collision and constraint steps, extracting data from mjData.{contact, efc_force}, ignoring contacts that were filtered out by the standard mechanism and produce no force.

        Contact sensor output involves three stages: matching, reduction and extraction.

    !!! quote "Matching"
        Selects a set of contacts from mjData.contact using criteria defined by geom1, geom2, body1, body2, subtree1, subtree2 and site. Matching applies an intersection of criteria, for example setting body1 and body2 will match contacts that involve both bodies, while setting only geom1 will match any contacts involving that geom. Setting site will match contacts that are inside the volume defined by the site; this matching criterion can be used with {geom2, body2, subtree2}. The subtree attributes take a body name and match all contacts involving the body's subtree i.e., the body and all of its descendants. Setting subtree1 and subtree2 to the same body will match self-collisions in the subtree. Specifying no matching criterion will match all contacts.

    !!! quote "Reduction"
        Reduces the number of matched contacts to exactly num sub-arrays, or "slots". If less than num contacts match, the remaining slots are set to be identically zero. Note that the default, "unsorted" reduction criterion is potentitally non-deterministic. See reduce below.

    !!! quote "Extraction"
        Copies the set of fields specified by the user into each slot, see data.
    """

    tag = "contact"

    attributes = (
        *SensorBase.attributes,
        "geom1",
        "geom2",
        "body1",
        "body2",
        "subtree1",
        "subtree2",
        "site",
        "num",
        "data",
        "reduce",
    )

    geom1: GeomName | None = None
    """Name of a geom participating in a contact. See matching above."""

    geom2: GeomName | None = None
    """Name of a geom participating in a contact. See matching above."""

    body1: BodyName | None = None
    """Name of a body participating in a contact. See matching above."""

    body2: BodyName | None = None
    """Name of a body participating in a contact. See matching above."""

    subtree1: BodyName | None = None
    """Name of a body whose subtree is participating in a contact. See matching above."""

    subtree2: BodyName | None = None
    """Name of a body whose subtree is participating in a contact. See matching above."""

    site: SiteName | None = None
    """Name of a site within whose volume the contact position must be found in order to match. See matching above."""

    num: int = 1
    """Number of contacts to report. The sensor will always report num sequential data arrays ("slots") per contact. The order in which contacts are reported depends on the reduce attribute."""

    data: tuple[ContactData, ...] = (ContactData.FOUND,)
    """Specification of which data field(s) to report from the selected contacts."""

    reduce: ContactReduce = ContactReduce.NONE
    """Reduction criterion to use. Also see reduction above."""

    @model_validator(mode="after")
    def validate_contact_sensor(self):
        if self.num < 1:
            msg = "num must be >= 1"
            logger.error(msg)
            raise ValueError(msg)

        # data must be ordered correctly
        order = [
            ContactData.FOUND,
            ContactData.FORCE,
            ContactData.TORQUE,
            ContactData.DIST,
            ContactData.POS,
            ContactData.NORMAL,
            ContactData.TANGENT,
        ]

        # remove duplicates
        if len(set(self.data)) != len(self.data):
            msg = "Duplicate entries in contact data"
            logger.error(msg)
            raise ValueError(msg)

        # normalize order
        self.data = tuple(sorted(self.data, key=lambda d: order.index(d)))

        if self.cutoff:
            print(
                "WARNING: The cutoff attribute is ignored for the SensorContact class."
            )
        return self
