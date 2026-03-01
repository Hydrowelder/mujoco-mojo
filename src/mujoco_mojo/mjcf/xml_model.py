from __future__ import annotations

from collections.abc import Sequence
from typing import (
    ClassVar,
    Literal,
    Protocol,
    get_origin,
    runtime_checkable,
)
from xml.etree.ElementTree import Element

import mujoco
import numpy as np
from pydantic import model_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.utils.logging import get_logger

logger = get_logger(__name__)

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


@runtime_checkable
class NamedXMLObject(Protocol):
    """A protocol that matches any object with a name and an mjt_obj."""

    name: str | None
    mjt_obj: ClassVar[mujoco.mjtObj | None]


class XMLModel(MojoBaseModel):
    """Base class for most MuJoCo Mojo MJCF objects."""

    tag: ClassVar[str]
    """Tag name of the XML tag."""

    attributes: ClassVar[tuple[str, ...]] = ()
    """Attributes of the XML tag."""

    children: ClassVar[tuple[str, ...]] = ()
    """Children of the XML tag."""

    __exclusive_groups__: ClassVar[tuple[tuple[str, ...], ...]] = ()
    """Attributes which if defined simultaneously will result in an error."""

    mjt_obj: ClassVar[mujoco.mjtObj | None] = None

    def to_xml(self, exclude_default: bool = True) -> Element:
        el = Element(self.tag)

        # attributes (deterministic)
        for field in self.attributes:
            value = getattr(self, field, None)

            field_info = type(self).model_fields[field]
            annotation = field_info.annotation
            is_literal = get_origin(annotation) is Literal

            if exclude_default and not is_literal:
                # determine default value
                default = type(self).model_fields[field].default

                # determine if its equal to value
                if isinstance(value, np.ndarray):
                    is_default = np.array_equal(value, default)
                else:
                    is_default = value == default

                if is_default:
                    continue

            if value is None:
                continue

            field_name = field.rstrip("_")

            # attribute is an XMLModel (to be flattened)
            if isinstance(value, XMLModel):
                # safety checks
                if value.children:
                    raise ValueError(
                        f"{value.__class__.__name__} cannot be used as an attribute because it defines children",
                    )

                # recursively extract attributes
                sub_attrs = value._collect_xml_attributes()

                # collision detection
                for k in sub_attrs:
                    if k in el.attrib:
                        raise ValueError(
                            f"Attribute collision while flattening {value.__class__.__name__}: '{k}' already exists",
                        )

                el.attrib.update(sub_attrs)
                continue

            # normal attribute
            el.set(field_name, _format_value(value))

        # children
        for field in self.children:
            value = getattr(self, field, None)

            if value is None:
                continue

            # turn single items into a list so we only write the logic once
            items = value if isinstance(value, list) else [value]
            for item in items:
                if isinstance(item, XMLModel):
                    el.append(item.to_xml(exclude_default=exclude_default))
                else:
                    raise TypeError(
                        f"Field '{field}' in {self.__class__.__name__} contains an object "
                        f"of type {type(item).__name__} which is not an XMLModel (missing to_xml)."
                    )

        return el

    def _collect_xml_attributes(self) -> dict[str, str]:
        """
        Recursively collect attributes for XML flattening.

        Only valid for XMLModels that define attributes but no children.
        """
        if self.children:
            raise ValueError(
                f"{self.__class__.__name__} has children and cannot be flattened",
            )

        attrs: dict[str, str] = {}
        for field in self.attributes:
            value = getattr(self, field, None)

            if value is None:
                continue

            key = field.rstrip("_")

            if isinstance(value, XMLModel):
                nested = value._collect_xml_attributes()

                for k in nested:
                    if k in attrs:
                        msg = f"Attribute collision while flattening nested XMLModel: '{k}'"
                        logger.error(msg)
                        raise ValueError(msg)

                attrs.update(nested)

            else:
                attrs[key] = _format_value(value)

        return attrs

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
                    f"as a field or class variable",
                )

        # Validate children
        for name in cls.children:
            if name not in valid_names:
                raise TypeError(
                    f"{cls.__name__}: child '{name}' is not defined "
                    f"as a field or class variable",
                )

        if (
            "name" in cls.model_fields
            and cls.mjt_obj is None
            and cls.tag != "worldbody"
        ):
            # only warning if some named objects truly don't have a MuJoCo counterpart
            logger.debug(
                f"{cls.__name__}: class has a name attribute but no mjtObj definition. This may be an error on behalf of the MuJoCo Mojo developer."
            )

    @model_validator(mode="after")
    def enforce_exclusive_groups(self) -> XMLModel:
        """Ensures that only one attribute in each exclusive group is set."""
        for group in self.__exclusive_groups__:
            count = sum(getattr(self, field) is not None for field in group)
            if count > 1:
                raise ValueError(
                    f"{type(self).__name__}: Only one of {group} may be specified",
                )
        return self

    def get_id(self, mj_model: mujoco.MjModel) -> int:
        """
        Generic ID lookup that works for any subclass defining mjt_obj and name.
        """
        # 1. Check if this specific class supports ID lookup
        if self.mjt_obj is None:
            raise TypeError(
                f"Class '{self.__class__.__name__}' does not map to a MuJoCo runtime object."
            )

        # 2. Get the name (supporting your custom TypeHints)
        name = getattr(self, "name", None)

        if name is None:
            # Special case for 'worldbody' which MuJoCo implicitly calls "world"
            if self.tag == "worldbody":
                name = "world"
            else:
                raise ValueError(
                    f"Instance of {self.__class__.__name__} has no name defined."
                )

        # 3. Perform the MuJoCo lookup
        obj_id = mujoco.mj_name2id(mj_model, self.mjt_obj, name)

        if obj_id == -1:
            msg = f"Could not find {self.mjt_obj.name} '{name}' in MjModel."
            logger.error(msg)
            raise ValueError(msg)

        return obj_id
