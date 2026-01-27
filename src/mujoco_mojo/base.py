from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar
from xml.etree.ElementTree import Element

from pydantic import BaseModel

__all__ = ["XMLModel"]


def _tuple_string(v: Sequence[float]) -> str:
    return " ".join(map(str, v))


class XMLModel(BaseModel):
    tag: ClassVar[str]
    attributes: ClassVar[tuple[str, ...]] = ()
    children: ClassVar[tuple[str, ...]] = ()

    def to_xml(self) -> Element:
        el = Element(self.tag)

        # attributes (deterministic)
        for field in tuple(self.attributes):
            value = getattr(self, field, None)
            if value is not None:
                if isinstance(value, (tuple, list)):
                    value = _tuple_string(value)

                el.set(field, value if isinstance(value, str) else str(value))

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
