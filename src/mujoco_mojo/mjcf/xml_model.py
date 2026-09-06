from __future__ import annotations

from abc import ABC
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
from mujoco_mojo.mjcf.dependency_path import (
    apply_asset_destinations,
    collect_asset_slots,
    compute_asset_destinations,
    copy_asset,
)
from mujoco_mojo.settings import MujocoMojoSettings
from mujoco_mojo.typing import Angle, EulerSeq
from mujoco_mojo.utils.log import get_logger

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

    non_xml_fields: ClassVar[tuple[str, ...]] = ()
    """Fields that exist on this model but are intentionally not written to XML as an attribute or child (e.g. an attribute documented as never being saved to XML). Every field not covered by `attributes`, `children`, or this tuple is treated as a missed schema entry. Each entry should be accompanied by a comment explaining why it is exempt."""

    __exclusive_groups__: ClassVar[tuple[tuple[str, ...], ...]] = ()
    """Attributes which if defined simultaneously will result in an error."""

    color_fields: ClassVar[tuple[str, ...]] = ("rgba",)
    """Names of fields on this model that hold MuJoCo colors, whose components are expected in the range [0, 1] rather than [0, 255]. `warn_out_of_range_colors` checks each of these after validation and logs a warning if any component exceeds 1. Most MJCF elements only have a single color field, named `rgba`, which is the default here; override this in a subclass that has differently-named and/or multiple color fields (e.g. `VisualRGBA`, `Texture`, `Light`)."""

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = None
    """Attribute used to perform MjModel ID lookups."""

    _id_cache: int = PrivateAttr(-1)
    """MuJoCo runtime ID."""

    @model_validator(mode="after")
    def warn_out_of_range_colors(self) -> Self:
        for field in self.color_fields:
            value = getattr(self, field, None)
            if isinstance(value, (np.ndarray, list, tuple)) and max(value) > 1:
                logger.warning(
                    f"{self.__class__.__name__} {getattr(self, 'name', 'unnamed')}.{field}: "
                    f"MuJoCo colors range from 0 to 1, not 0 to 255. You entered {field}={value!r}."
                )
        return self

    @model_validator(mode="after")
    def validate_name(self):
        name = getattr(self, "name", None)
        if isinstance(name, str):
            if ":" in name or "/" in name:
                msg = f"Invalid name for {name}. Characters ':' and '/' are reserved for database output organization."
                logger.error(msg)
                raise ValueError(msg)
        return self

    def to_xml(
        self,
        compiler_degrees: Angle,
        compiler_eulerseq: EulerSeq,
        exclude_default: bool = True,
    ) -> Element:
        el = Element(self.tag)

        # attributes (deterministic)
        for field in self.attributes:
            value = getattr(self, field, None)

            if value is None:
                continue

            # `field` is usually a real pydantic field, but it can also be a plain `@property`
            # that assembles its value from other fields (e.g. a mesh shape's `params`, packed
            # from friendlier per-shape fields like `radius`/`nvert`). Properties have no entry
            # in `model_fields` and no sensible "default" to exclude against, so they're always
            # written once non-None.
            field_info = type(self).model_fields.get(field)
            is_literal = (
                field_info is not None and get_origin(field_info.annotation) is Literal
            )

            if (
                field_info is not None
                and exclude_default
                and not is_literal
                and not isinstance(value, XMLModel)
            ):
                # determine default value
                default = field_info.default

                # determine if its equal to value
                if isinstance(value, np.ndarray):
                    if np.array_equal(value, default):
                        continue
                else:
                    if value == default:
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
                sub_attrs = value._collect_xml_attributes(
                    compiler_degrees=compiler_degrees,
                    compiler_eulerseq=compiler_eulerseq,
                )

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
                    el.append(
                        item.to_xml(
                            exclude_default=exclude_default,
                            compiler_degrees=compiler_degrees,
                            compiler_eulerseq=compiler_eulerseq,
                        )
                    )
                else:
                    msg = f"Field '{field}' in {self.__class__.__name__} contains an object of type {type(item).__name__} which is not an XMLModel (missing to_xml)."
                    logger.error(msg)
                    raise TypeError(msg)

        return el

    def _collect_xml_attributes(
        self,
        compiler_degrees: Angle,
        compiler_eulerseq: EulerSeq,
    ) -> dict[str, str]:
        """
        Recursively collect attributes for XML flattening.

        Only valid for XMLModels that define attributes but no children.
        """
        if self.children:
            msg = f"{self.__class__.__name__} has children and cannot be flattened"
            logger.error(msg)
            raise ValueError(msg)

        attrs: dict[str, str] = {}
        # to prevent circular import since OrientationBase is an XMLModel
        from mujoco_mojo.mjcf.orientation import OrientationBase

        for field in self.attributes:
            value = getattr(self, field, None)

            if value is None:
                continue

            key = field.rstrip("_")

            if isinstance(self, OrientationBase) and field == self._rotation_attr:
                xml_val = self.get_xml_value(
                    target_degrees=compiler_degrees,
                    target_eulerseq=compiler_eulerseq,
                )
                attrs[key] = _format_value(xml_val)
                continue

            if isinstance(value, XMLModel):
                nested = value._collect_xml_attributes(
                    compiler_degrees=compiler_degrees,
                    compiler_eulerseq=compiler_eulerseq,
                )

                for k in nested:
                    if k in attrs:
                        msg = f"Attribute collision while flattening nested XMLModel: '{k}'"
                        logger.error(msg)
                        raise ValueError(msg)

                attrs.update(nested)
                continue

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

        # Validate non_xml_fields
        for name in cls.non_xml_fields:
            if name not in valid_names:
                msg = f"{cls.__name__}: non_xml_fields entry '{name}' is not defined as a field or class variable. Please contact a MuJoCo Mojo developer."
                logger.error(msg)
                raise TypeError(msg)

        # Every class must explicitly define its own tag (an empty string is fine for
        # classes that only ever get flattened into a parent's attributes via
        # `_collect_xml_attributes`), so that `to_xml` never fails with a confusing
        # AttributeError deep in serialization.
        if not hasattr(cls, "tag"):
            msg = f"{cls.__name__}: must define 'tag' (use an empty string if this class is never rendered as its own XML element). Please contact a MuJoCo Mojo developer."
            logger.error(msg)
            raise TypeError(msg)

        # Classes that exist purely to be inherited from (never directly serialized)
        # opt out of the field-coverage check below by directly subclassing ABC.
        if ABC not in cls.__bases__:
            accounted = (
                set(cls.attributes) | set(cls.children) | set(cls.non_xml_fields)
            )
            for name, field_info in cls.model_fields.items():
                if name in accounted:
                    continue
                if get_origin(field_info.annotation) is Literal:
                    # discriminator fields are never real XML attributes
                    continue
                msg = f"{cls.__name__}: field '{name}' is not listed in attributes, children, or non_xml_fields. Please contact a MuJoCo Mojo developer."
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

    def _iter_tree(self):
        """Yields this model and all its XMLModel children recursively."""
        yield self

        for field in self.attributes:
            value = getattr(self, field, None)
            if isinstance(value, XMLModel):
                yield from value._iter_tree()

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

        Two different source files sharing a basename (e.g. textures/wood/texture.png and textures/steel/texture.png) are disambiguated by nesting them under real parent directory names; byte-identical files sharing a basename are treated as duplicates and collapse to one destination/one copy. This only covers collisions discovered within this call - a pre-existing, unrelated file already in target_dir from an earlier bundle_assets() call keeps the existing warn-and-overwrite behavior.
        """
        target_dir.mkdir(parents=True, exist_ok=True)

        slots = collect_asset_slots(self)
        if not slots:
            return

        plan = compute_asset_destinations(slots)
        prefer_symlinks = MujocoMojoSettings().assets.symlink

        # copy once per unique destination, not once per source - true duplicates
        # (same content, same basename) share one destination and should only be
        # locked/hashed/copied once
        first_source_for_dest: dict[Path, Path] = {}
        for source, dest in plan.destinations.items():
            first_source_for_dest.setdefault(dest, source)

        for dest, source in first_source_for_dest.items():
            copy_asset(
                source,
                target_dir / dest,
                known_checksum=plan.source_checksums.get(source),
                prefer_symlinks=prefer_symlinks,
            )

        apply_asset_destinations(slots, plan.destinations, rel_to_xml)
