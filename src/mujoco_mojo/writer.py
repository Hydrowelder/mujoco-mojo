from __future__ import annotations

from xml.dom import minidom
from xml.etree.ElementTree import tostring

__all__ = ["to_pretty_xml"]


def to_pretty_xml(element) -> str:
    rough = tostring(element, "utf-8")
    reparsed = minidom.parseString(rough)
    return reparsed.toprettyxml(indent="  ")
