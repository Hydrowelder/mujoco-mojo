from __future__ import annotations

from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.flex_attr.contact import FlexContact

__all__ = ["FlexCompContact"]


class FlexCompContact(FlexContact):
    """Same as in flex/contact. All attributes are passed through to the automatically-generated flex."""

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
