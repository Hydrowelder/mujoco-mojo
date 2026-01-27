from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar
from xml.etree.ElementTree import Element

from pydantic import BaseModel

__all__ = ["XMLModel"]


def _tuple_string(v: Sequence[float]) -> str:
    return " ".join(map(str, v))


def _format_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (tuple, list)):
        return _tuple_string(value)

    return str(value)


class XMLModel(BaseModel):
    tag: ClassVar[str]
    """Tag name of the XML tag."""
    attributes: ClassVar[tuple[str, ...]] = ()
    """Attributes of the XML tag."""
    children: ClassVar[tuple[str, ...]] = ()
    """Children of the XML tag."""

    def to_xml(self) -> Element:
        el = Element(self.tag)

        # attributes (deterministic)
        for field in tuple(self.attributes):
            value = getattr(self, field, None)
            if value is not None:
                if field == "class_":
                    field = "class"
                el.set(field, _format_value(value))

        # children (deterministic)
        for field in tuple(self.children):
            value = getattr(self, field, None)

            if value is None:
                continue

            if isinstance(value, list):
                for item in value:
                    el.append(item.to_xml())
            else:
                el.append(value.to_xml())

        return el


class BuiltIn(BaseModel):
    pass
