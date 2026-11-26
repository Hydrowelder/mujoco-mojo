from __future__ import annotations

import types
from collections import Counter
from dataclasses import dataclass, field
from functools import cache
from typing import (
    Annotated,
    Any,
    Literal,
    Union,
    get_args,
    get_origin,
)
from xml.etree.ElementTree import Element

import numpy as np
from numpydantic import NDArray
from pydantic.fields import FieldInfo

from mujoco_mojo.mjcf.defaults import DEFAULT_ANGLE, DEFAULT_EULERSEQ
from mujoco_mojo.mjcf.dependency_path import DepPath
from mujoco_mojo.mjcf.orientation import OrientationBase
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import Angle, EulerSeq
from mujoco_mojo.utils.log import get_logger

logger = get_logger(__name__)

__all__ = ["read_xml"]

# attributes that MuJoCo lets take fewer numbers than they hold (`gear="100"`), the rest staying at their defaults, where it refuses that for others (`pos="1 2"`)
_MAY_BE_SHORT = ("gear", "friction", "solref", "solimp")


@dataclass
class _Context:
    """What reading one document carries along."""

    angle: Angle
    eulerseq: EulerSeq
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Child:
    """The model field that a child element of some tag is stored in."""

    field: str
    members: tuple[type[XMLModel], ...]
    discriminator: str | None
    many: bool


def _leaves(annotation: Any) -> tuple[Any, ...]:
    """The types an annotation allows, with `Annotated`, unions and `None` removed. Lists and tuples are kept whole."""
    origin = get_origin(annotation)
    if origin is Annotated:
        return _leaves(get_args(annotation)[0])
    if origin in (Union, types.UnionType):
        return tuple(leaf for arg in get_args(annotation) for leaf in _leaves(arg))
    if annotation is type(None):
        return ()
    return (annotation,)


def _models(annotation: Any) -> tuple[type[XMLModel], ...]:
    """The `XMLModel` classes an annotation allows."""
    return tuple(
        leaf
        for leaf in _leaves(annotation)
        if isinstance(leaf, type) and issubclass(leaf, XMLModel)
    )


def _discriminator(annotation: Any) -> str | None:
    """The discriminator that the `Field` of an `Annotated` anywhere in the annotation names."""
    origin = get_origin(annotation)
    if origin is Annotated:
        inner, *metadata = get_args(annotation)
        for item in metadata:
            if isinstance(item, FieldInfo) and isinstance(item.discriminator, str):
                return item.discriminator
        return _discriminator(inner)
    if origin in (Union, types.UnionType, list):
        for arg in get_args(annotation):
            found = _discriminator(arg)
            if found is not None:
                return found
    return None


def _field_discriminator(info: FieldInfo) -> str | None:
    """The discriminator of the union a field holds, whether the field or a type inside its annotation names it."""
    found = _discriminator(info.annotation)
    if found is None and isinstance(info.discriminator, str):
        return info.discriminator
    return found


@cache
def _children(cls: type[XMLModel]) -> dict[str, _Child]:
    """The child elements `cls` accepts, by tag."""
    table: dict[str, _Child] = {}
    for name in cls.children:
        info = cls.model_fields[name]
        many = get_origin(info.annotation) is list
        members = _models(get_args(info.annotation)[0] if many else info.annotation)
        table[members[0].tag] = _Child(
            field=name,
            members=members,
            discriminator=_field_discriminator(info),
            many=many,
        )
    return table


def _variant(
    members: tuple[type[XMLModel], ...],
    discriminator: str | None,
    attrs: dict[str, str],
) -> type[XMLModel]:
    """The member of a union that an element with these XML attributes is."""
    if len(members) == 1:
        return members[0]
    if discriminator is None:
        msg = f"{members[0].__name__} is in a union with no discriminator. Please contact a MuJoCo Mojo developer."
        logger.error(msg)
        raise TypeError(msg)
    wanted = members[0]._xml_variant(attrs)
    for member in members:
        if member.model_fields[discriminator].default == wanted:
            return member
    allowed = ", ".join(
        str(member.model_fields[discriminator].default) for member in members
    )
    msg = f"{discriminator} {wanted!r} is not one of: {allowed}"
    raise ValueError(msg)


def _convert(annotation: Any, text: str) -> Any:
    """An attribute's text as the value its field expects: the text itself for a scalar, a list of the words for a sequence, which pydantic then coerces."""
    leaves = _leaves(annotation)
    words = text.split()
    sequences = [leaf for leaf in leaves if _is_sequence(leaf)]
    if not sequences or (len(words) == 1 and len(sequences) < len(leaves)):
        for leaf in leaves:
            # pydantic would make a plain `Path` of the text, which asset bundling does not treat as a file the model depends on
            if isinstance(leaf, type) and issubclass(leaf, DepPath):
                return DepPath(text)
            # pydantic does not read "3" as an int for `Literal[1, 3]`
            if get_origin(leaf) is Literal and all(
                isinstance(value, int) for value in get_args(leaf)
            ):
                return int(text)
        return text
    sequence = sequences[0]
    if _is_array(sequence):
        return [float(word) for word in words]
    if get_origin(sequence) is tuple:
        args = get_args(sequence)
        # a variable length tuple of fixed length tuples is one flat list in XML
        if len(args) == 2 and args[1] is Ellipsis and get_origin(args[0]) is tuple:
            size = len(get_args(args[0]))
            return [words[i : i + size] for i in range(0, len(words), size)]
    return words


def _fill_from_default(value: Any, default: Any) -> Any:
    """Gives a short list the numbers it left out, which come from the field's default as in MuJoCo."""
    if (
        isinstance(value, list)
        and isinstance(default, np.ndarray)
        and len(value) < default.size
    ):
        return [*value, *default.ravel()[len(value) :].tolist()]
    return value


def _is_array(leaf: Any) -> bool:
    # `NDArray` is a protocol, which `issubclass` refuses, and its shaped versions (`Vec3`) are told by their metaclass
    return isinstance(leaf, type(NDArray))


def _is_sequence(leaf: Any) -> bool:
    return _is_array(leaf) or get_origin(leaf) in (list, tuple, set)


def _attributes(
    cls: type[XMLModel],
    attrs: dict[str, str],
    ctx: _Context,
    path: str,
    used: set[str],
) -> dict[str, Any]:
    """The fields of `cls` that the XML attributes give, with the names of the attributes read added to `used`."""
    out: dict[str, Any] = {}
    for name in cls.attributes:
        key = name.rstrip("_")
        info = cls.model_fields.get(name)
        try:
            if info is None:
                if key in attrs:
                    used.add(key)
                    out.update(cls._xml_unpack(key, attrs[key]))
            elif _models(info.annotation):
                nested = _flattened(info, attrs, ctx, path, used)
                if nested is not None:
                    out[name] = nested
            elif key in attrs:
                used.add(key)
                value = _convert(info.annotation, attrs[key])
                out[name] = (
                    _fill_from_default(value, info.default)
                    if key in _MAY_BE_SHORT
                    else value
                )
        except ValueError as error:
            ctx.problems.append(f"{path}: attribute '{key}': {error}")
    return out


def _flattened(
    info: FieldInfo,
    attrs: dict[str, str],
    ctx: _Context,
    path: str,
    used: set[str],
) -> dict[str, Any] | None:
    """A field holding a model whose attributes are written on the element that holds it (a pose), or `None` when the element has none of them, which leaves the field its default."""
    members = _models(info.annotation)
    if not {a.rstrip("_") for m in members for a in m.attributes} & attrs.keys():
        return None
    discriminator = _field_discriminator(info)
    member = _variant(members, discriminator, attrs)
    out = _attributes(member, attrs, ctx, path, used)
    if discriminator is not None:
        out[discriminator] = member.model_fields[discriminator].default
    # the orientation classes hold the compiler's settings for the angle and Euler sequence the XML is written in
    if issubclass(member, OrientationBase):
        for name, value in (("angle", ctx.angle), ("eulerseq", ctx.eulerseq)):
            if name in member.model_fields:
                out[name] = value
    return out


def _label(element: Element, index: int) -> str:
    name = element.get("name")
    return f"{element.tag} '{name}'" if name else f"{element.tag}[{index}]"


def _read(
    cls: type[XMLModel], element: Element, ctx: _Context, path: str
) -> dict[str, Any]:
    """The dict that `cls.model_validate` takes for `element`, with what could not be read added to `ctx.problems`."""
    used: set[str] = set()
    out = _attributes(cls, element.attrib, ctx, path, used)
    for key in element.attrib:
        if key not in used and key not in cls.xml_ignored_attributes:
            ctx.problems.append(f"{path}: unsupported attribute '{key}'")

    table = _children(cls)
    seen: Counter[str] = Counter()
    for child in element:
        child_path = f"{path}/{_label(child, seen[child.tag])}"
        seen[child.tag] += 1
        slot = table.get(child.tag)
        if slot is None:
            ctx.problems.append(f"{child_path}: unsupported element")
            continue
        try:
            member = _variant(slot.members, slot.discriminator, child.attrib)
        except ValueError as error:
            ctx.problems.append(f"{child_path}: {error}")
            continue
        value = _read(member, child, ctx, child_path)
        if slot.discriminator is not None:
            value[slot.discriminator] = member.model_fields[slot.discriminator].default
        if slot.many:
            out.setdefault(slot.field, []).append(value)
        elif slot.field in out:
            ctx.problems.append(f"{child_path}: only one is allowed")
        else:
            out[slot.field] = value
    return out


def read_xml[T: XMLModel](
    cls: type[T],
    root: Element,
    *,
    angle: Angle = DEFAULT_ANGLE,
    eulerseq: EulerSeq = DEFAULT_EULERSEQ,
    strict: bool = True,
) -> T:
    """
    Builds a model from an XML element, the inverse of `XMLModel.to_xml`.

    Args:
        cls: The model for the element, whose `tag` the root has to carry.
        root: The element to read.
        angle: The unit of the angles in the XML, which is the compiler's `angle`.
        eulerseq: The Euler sequence of the angles in the XML, which is the compiler's `eulerseq`.
        strict: Whether an element or attribute that no model holds (a `default` element, say) raises. Left as it is, `strict=False` drops it and logs a warning.

    Returns:
        The model.

    Raises:
        ValueError: If the root has the wrong tag, or in strict mode something in the XML could not be read. The message lists everything.

    """
    if root.tag != cls.tag:
        msg = f"Expected a <{cls.tag}> element but found <{root.tag}>."
        logger.error(msg)
        raise ValueError(msg)

    ctx = _Context(angle=angle, eulerseq=eulerseq)
    data = _read(cls, root, ctx, root.tag)
    if ctx.problems:
        if strict:
            lines = "\n".join(f"- {problem}" for problem in ctx.problems)
            msg = f"Could not read the XML as {cls.__name__}:\n{lines}\nPass strict=False to drop what cannot be read."
            logger.error(msg)
            raise ValueError(msg)
        for problem in ctx.problems:
            logger.warning(f"Dropped from the XML: {problem}")
    return cls.model_validate(data)
