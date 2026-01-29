from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar
from xml.etree.ElementTree import Element

import numpy as np
from pydantic import BaseModel, model_validator

__all__ = ["XMLModel"]


def _tuple_string(v) -> str:
    """
    Convert a sequence or array of numbers into a space-separated string.
    Works with list, tuple, or NumPy ndarray.
    """
    return " ".join(map(str, v))


def _format_value(value) -> str:
    """
    Convert a Python value into a string suitable for XML attributes.
    - Booleans become "true"/"false"
    - Sequences (list, tuple, np.ndarray) become space-separated strings
    - Everything else is cast to str
    """
    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (Sequence, np.ndarray)) and not isinstance(value, str):
        return _tuple_string(value)

    return str(value)


class XMLModel(BaseModel):
    tag: ClassVar[str]
    """Tag name of the XML tag."""
    attributes: ClassVar[tuple[str, ...]] = ()
    """Attributes of the XML tag."""
    children: ClassVar[tuple[str, ...]] = ()
    """Children of the XML tag."""
    __exclusive_groups__: tuple[tuple[str, ...], ...] = ()
    """Attributes which if defined simultaneously will result in an error."""

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

    @model_validator(mode="after")
    def enforce_exclusive_groups(cls, model):
        for group in cls.__exclusive_groups__:
            count = sum(getattr(model, field) is not None for field in group)

            if count > 1:
                raise ValueError(
                    f"{cls.__name__}: Only one of {group} may be specified"
                )

        return model
