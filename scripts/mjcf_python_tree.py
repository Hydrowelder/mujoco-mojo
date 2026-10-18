"""
The MJCF element tree that mojo models, read off the `children` fields of the XMLModel classes.

Shared by `check_mjcf_schema_coverage.py` (which compares it with the schema) and `gen_mjcf_tags.py` (which writes it out as the checklist on the MJCF reference page), so both agree on what is nested where.
"""

from __future__ import annotations

import typing

from mujoco_mojo.mjcf.xml_model import XMLModel

__all__ = ["child_fields", "xml_model_classes_in"]


def xml_model_classes_in(annotation: object) -> list[type[XMLModel]]:
    """Every `XMLModel` subclass named by a field annotation, in the order written and without repeats, looking through `list`, `tuple`, optionals, unions, and `Annotated` (so a discriminated union of geoms resolves to all of its geom classes)."""
    found: list[type[XMLModel]] = []

    def walk(node: object) -> None:
        if typing.get_origin(node) is typing.Annotated:
            walk(typing.get_args(node)[0])
        elif typing.get_origin(node) is not None:
            for arg in typing.get_args(node):
                walk(arg)
        elif (
            isinstance(node, type) and issubclass(node, XMLModel) and node not in found
        ):
            found.append(node)

    walk(annotation)
    return found


def child_fields(cls: type[XMLModel]) -> list[tuple[str, list[type[XMLModel]]]]:
    """
    Each field `cls` lists in `children`, in that order, with the tagged `XMLModel` classes its annotation names.

    A field that resolves to no tagged class has an empty list, which is how a typo in `children` or an unresolved forward reference shows up instead of silently dropping a child.
    """
    fields: list[tuple[str, list[type[XMLModel]]]] = []
    for field_name in getattr(cls, "children", ()):
        field_info = cls.model_fields.get(field_name)
        classes = xml_model_classes_in(field_info.annotation) if field_info else []
        fields.append((field_name, [c for c in classes if getattr(c, "tag", "")]))
    return fields
