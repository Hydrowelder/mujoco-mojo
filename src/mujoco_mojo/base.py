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
                # I use a trailing underscore to get around python's special names
                # i.e., "class" is reserved for python so I use "class_" instead
                field = field.rstrip("_")
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

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        """
        Validates that XML attribute and child names exist on the model.

        This runs after Pydantic has finished building model fields and ensures that all entries in `attributes` and `children` reference actual fields or class variables. Errors are raised at class definition time to prevent invalid XML schemas from being created.
        """
        super().__pydantic_init_subclass__(**kwargs)

        # Pydantic fields (includes inherited)
        model_fields = set(cls.model_fields.keys())

        # Class-level attributes (ClassVars, constants, etc)
        class_vars = set(vars(cls).keys())

        valid_names = model_fields | class_vars

        # Validate attributes
        for name in cls.attributes:
            if name not in valid_names:
                raise TypeError(
                    f"{cls.__name__}: attribute '{name}' is not defined "
                    f"as a field or class variable"
                )

        # Validate children
        for name in cls.children:
            if name not in valid_names:
                raise TypeError(
                    f"{cls.__name__}: child '{name}' is not defined "
                    f"as a field or class variable"
                )
