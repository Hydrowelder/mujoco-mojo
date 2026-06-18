from __future__ import annotations

from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.flex_attr.contact import FlexContact

__all__ = ["FlexCompContact"]


class FlexCompContact(FlexContact):
    """This is basically a FlexContact."""

    attributes = (
        "internal",
        "selfcollide",
        "activelayers",
        "contype",
        "conaffinity",
        "condim",
        "priority",
        "friction",
        "solmix",
        "solimp",
        "margin",
        "gap",
    )

    # inherited from FlexContact but not part of the flexcomp contact element's schema
    non_xml_fields = ("solref", "passive")
