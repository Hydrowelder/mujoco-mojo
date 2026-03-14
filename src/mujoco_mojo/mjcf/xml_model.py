from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import (
    ClassVar,
    Literal,
    Protocol,
    Self,
    get_origin,
    runtime_checkable,
)
from xml.etree.ElementTree import Element

import mujoco
import numpy as np
from pydantic import PrivateAttr, model_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.mjcf.dependency_path import DepPath
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.utils import get_checksum

logger = get_logger(__name__)

__all__ = ["XMLModel"]


def _tuple_string(v) -> str:
    """
    Convert a sequence or array of numbers into a space-separated string.

    Works with list, tuple, or NumPy ndarray.
    """

    def flatten(items):
        for item in items:
            if isinstance(item, (list, tuple, np.ndarray)):
                yield from flatten(item)
            else:
                yield str(item)

    return " ".join(flatten(v))


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

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = None
    """Attribute used to perform MjModel ID lookups."""

    _id_cache: int = PrivateAttr(-1)
    """MuJoCo runtime ID."""

    @model_validator(mode="after")
    def warn_rgba(self) -> Self:

        rgba: np.ndarray | None = getattr(self, "rgba", None)
        if rgba is not None:
            if max(rgba) > 1:
                logger.warning(
                    f"{self.__class__.__name__} {getattr(self, 'name', 'unnamed')}: MuJoCo rgba values range from 0 to 1, not 0 to 255. You entered {rgba=}."
                )
        return self

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
                    msg = f"{value.__class__.__name__} cannot be used as an attribute because it defines children"
                    logger.error(msg)
                    raise ValueError(msg)

                # recursively extract attributes
                sub_attrs = value._collect_xml_attributes()

                # collision detection
                for k in sub_attrs:
                    if k in el.attrib:
                        msg = f"Attribute collision while flattening {value.__class__.__name__}: '{k}' already exists"
                        logger.error(msg)
                        raise ValueError(msg)

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
                    msg = f"Field '{field}' in {self.__class__.__name__} contains an object of type {type(item).__name__} which is not an XMLModel (missing to_xml)."
                    logger.error(msg)
                    raise TypeError(msg)

        return el

    def _collect_xml_attributes(self) -> dict[str, str]:
        """
        Recursively collect attributes for XML flattening.

        Only valid for XMLModels that define attributes but no children.
        """
        if self.children:
            msg = f"{self.__class__.__name__} has children and cannot be flattened"
            logger.error(msg)
            raise ValueError(msg)

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
                msg = f"{cls.__name__}: attribute '{name}' is not defined as a field or class variable. Please contact a MuJoCo Mojo developer."
                logger.error(msg)
                raise TypeError(msg)

        # Validate children
        for name in cls.children:
            if name not in valid_names:
                msg = f"{cls.__name__}: child '{name}' is not defined as a field or class variable. Please contact a MuJoCo Mojo developer."
                logger.error(msg)
                raise TypeError(msg)

        if (
            "name" in cls.model_fields
            and cls._mjt_obj is None
            and cls.tag != "worldbody"
        ):
            # only warning if some named objects truly don't have a MuJoCo counterpart
            msg = f"{cls.__name__}: class has a name attribute but no mjtObj definition. This may be an error on behalf of the MuJoCo Mojo developer."
            logger.error(msg)
            raise TypeError(msg)

    @model_validator(mode="after")
    def enforce_exclusive_groups(self) -> XMLModel:
        """Ensures that only one attribute in each exclusive group is set."""
        for group in self.__exclusive_groups__:
            count = sum(getattr(self, field) is not None for field in group)
            if count > 1:
                msg = f"{type(self).__name__}: Only one of {group} may be specified"
                logger.error(msg)
                raise ValueError(msg)
        return self

    def get_id(self, mj_model: mujoco.MjModel) -> int:
        """
        Generic ID lookup that works for any subclass defining mjt_obj and name.
        """
        # early exit if the ID has already been found
        if self._id_cache != -1:
            return self._id_cache

        # 1. Check if this specific class supports ID lookup
        if self._mjt_obj is None:
            msg = f"Class '{self.__class__.__name__}' does not map to a MuJoCo runtime object."
            logger.error(msg)
            raise TypeError(msg)

        # 2. Get the name (supporting your custom TypeHints)
        name = getattr(self, "name", None)

        if name is None:
            # Special case for 'worldbody' which MuJoCo implicitly calls "world"
            if self.tag == "worldbody":
                name = "world"
            else:
                msg = f"Instance of {self.__class__.__name__} has no name defined."
                logger.error(msg)
                raise ValueError(msg)

        # 3. Perform the MuJoCo lookup
        obj_id = mujoco.mj_name2id(mj_model, self._mjt_obj, name)

        if obj_id == -1:
            msg = f"Could not find {self._mjt_obj.name} '{name}' in MjModel."
            logger.error(msg)
            raise ValueError(msg)

        self._id_cache = obj_id
        return obj_id

    def _iter_tree(
        self,
    ):  # doesnt this need to determine if there is a list/dict/tuple/array which contains paths too?
        """Yields this model and all its XMLModel children recursively."""
        yield self
        for field in self.children:
            value = getattr(self, field, None)
            if value is None:
                continue
            items = value if isinstance(value, list) else [value]
            for item in items:
                if isinstance(item, XMLModel):
                    yield from item._iter_tree()

    def bundle_assets(self, target_dir: Path, rel_to_xml: Path) -> None:
        """
        Crawls the entire XMLModel tree. Any attribute that is a Path object is copied to target_dir/assets and the model is updated to a relative path.
        """
        target_dir.mkdir(parents=True, exist_ok=True)

        # get objects in the tree
        for obj in self._iter_tree():
            for attr_name in obj.attributes:
                value = getattr(obj, attr_name, None)

                is_collection = isinstance(value, (list, tuple, set))

                # type is cast to list here. Will need to uncast later.
                items = list(value) if is_collection else [value]

                new_values = []
                changed = False

                # loop over attribute as a list of items
                for item in items:
                    if isinstance(item, DepPath):
                        item = item.resolve()
                        if not item.exists():
                            logger.error(f"Asset file not found: {item}")
                            new_values.append(item)
                            continue

                        # copy the file
                        dest_file = target_dir / item.name

                        should_copy = True
                        if dest_file.exists():
                            # files already in the destination skipped
                            if get_checksum(item) == get_checksum(dest_file):
                                should_copy = False
                                logger.debug(
                                    f"Dependency asset {item.resolve()} was already in the shared asset directory {target_dir.resolve()} (as identified by filename and MD5 hash) so the file will be skipped from being copied."
                                )
                            else:
                                logger.warning(
                                    f"Asset file {value} already in assets bundle. Old file will be overwritten."
                                )

                        if should_copy:
                            logger.debug(
                                f"Copying dependency asset from {item.resolve()} to {dest_file.resolve()}"
                            )
                            shutil.copy2(item, dest_file)

                        new_values.append(rel_to_xml / item.name)
                        changed = True
                    else:
                        new_values.append(item)

                if changed:
                    # cast back to previous type
                    final_val = (
                        type(value)(new_values) if is_collection else new_values[0]
                    )
                    setattr(obj, attr_name, final_val)
