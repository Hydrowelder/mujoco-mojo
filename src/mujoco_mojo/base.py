from __future__ import annotations

from typing import ClassVar, Dict, Tuple
from xml.etree.ElementTree import Element

from pydantic import BaseModel

__all__ = ["XMLModel"]


def _tuple_string(v: Tuple[float, ...]) -> str:
    return " ".join(map(str, v))


class XMLModel(BaseModel):
    tag: ClassVar[str]
    attributes: ClassVar[set[str]] = set()
    children_map: ClassVar[Dict[str, str]] = {}

    def to_xml(self) -> Element:
        el = Element(self.tag)

        # attributes
        for field in self.attributes:
            value = getattr(self, field, None)
            if value is not None:
                if isinstance(value, tuple):
                    value = _tuple_string(value)
                el.set(field, str(value))

        # children
        for field, tag_name in self.children_map.items():
            value = getattr(self, field, None)

            if value is None:
                continue

            if isinstance(value, list):
                for item in value:
                    el.append(item.to_xml())
            else:
                el.append(value.to_xml())

        return el
