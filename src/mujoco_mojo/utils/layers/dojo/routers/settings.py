"""Global mujoco-mojo settings API for the Dojo dashboard."""

from __future__ import annotations

import ipaddress
from typing import Any, get_args

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import AnyUrl, BaseModel, RootModel, SecretStr, ValidationError

from mujoco_mojo.settings import GenerateJsonSchemaWithDefaults, MujocoMojoSettings
from mujoco_mojo.utils.color import Color

router = APIRouter()


def _is_localhost(request: Request) -> bool:
    """Whether the request's direct TCP peer is the loopback interface, regardless of which interface the server itself is bound to."""
    host = request.client.host if request.client else None
    if host is None:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _require_localhost(request: Request) -> None:
    if not _is_localhost(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Settings can only be changed from the machine running Dojo.",
        )


def _walk_value_meta(model: BaseModel, prefix: str = "") -> dict[str, dict[str, Any]]:
    """
    Recursively walks a settings model instance, returning display metadata keyed by dotted field path for any leaf that needs it. Currently this is just `is_url` for a leaf whose current value is an `AnyUrl` instance - detected from the value's runtime type rather than the field name, so a future url-or-path field is covered automatically.
    """
    meta: dict[str, dict[str, Any]] = {}
    for name in type(model).model_fields:
        value = getattr(model, name)
        path = f"{prefix}{name}"
        if isinstance(value, RootModel):
            continue
        if isinstance(value, BaseModel):
            meta.update(_walk_value_meta(value, prefix=f"{path}."))
        elif isinstance(value, AnyUrl):
            meta[path] = {"is_url": True}
    return meta


def _merge_preserving_secrets(
    current: BaseModel, posted: dict[str, Any]
) -> dict[str, Any]:
    """
    Overlays `posted` (the full settings tree as returned by the client, which always started from a `GET`) onto a dump of `current`, except for a `SecretStr` leaf whose posted value still equals its own masked display - there, the live, unmasked value is kept instead. This is what lets a secret field stay untouched in the UI without its real value getting clobbered by the mask string on save.
    """
    merged = current.model_dump(mode="python", exclude_none=True)
    _overlay(type(current), current, merged, posted)
    return merged


def _overlay(
    model_cls: type[BaseModel],
    current: BaseModel,
    merged: dict[str, Any],
    posted: dict[str, Any],
) -> None:
    for name in model_cls.model_fields:
        if name not in posted:
            continue
        current_value = getattr(current, name)
        if isinstance(current_value, BaseModel) and not isinstance(
            current_value, RootModel
        ):
            if isinstance(posted[name], dict):
                merged.setdefault(name, {})
                _overlay(type(current_value), current_value, merged[name], posted[name])
            continue
        if isinstance(current_value, SecretStr) and posted[name] == str(current_value):
            continue  # unchanged in the UI - keep the live, unmasked value
        merged[name] = posted[name]


def _validate_replacing[ModelT: BaseModel](
    model_cls: type[ModelT], data: dict[str, Any]
) -> ModelT:
    """
    Validates `data` against `model_cls` one top-level field at a time - each against its own declared type - then assembles the result via `model_construct`, rather than a single `model_cls.model_validate(data)` call.

    This matters specifically for `model_cls=MujocoMojoSettings`, a `pydantic_settings.BaseSettings` subclass: its `model_validate` (like `__init__`) re-runs the same source layering `settings_customise_sources` defines (env vars, then settings.toml), and pydantic-settings deep-*merges* a dict-shaped field's value across sources rather than replacing it wholesale. That's correct for a field genuinely left unset, but wrong here - a field the client explicitly posted a full new value for (e.g. `slurm`, after deleting an entry in the Dojo settings panel) needs a real replace, or the deleted entry silently reappears, merged back in from whatever's still on disk. Each nested field here is validated against its own (plain `BaseModel`, not `BaseSettings`) type directly - which carries no such merging behavior - then the whole is assembled via `model_construct`, which (like `set_project_value`'s use of it elsewhere in settings.py) skips `BaseSettings`' own init/source-layering entirely, giving the wholesale-replace semantics an explicit POST body implies.
    """
    validated: dict[str, Any] = {}
    for name, info in model_cls.model_fields.items():
        if name not in data:
            continue
        annotation = info.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            validated[name] = annotation.model_validate(data[name])
        else:
            validated[name] = data[name]
    return model_cls.model_construct(**validated)


def _is_secret_annotation(annotation: Any) -> bool:
    """Whether `annotation` is `SecretStr`, possibly wrapped in `Optional`/a union (e.g. `SecretStr | None`) - unwrapped via `get_args` rather than checking a runtime value, since a field's declared type doesn't depend on whatever it's currently set to (unlike an `isinstance(value, SecretStr)` check, which misses a field like `password` whose default is `None`)."""
    args = get_args(annotation)
    candidates = args if args else (annotation,)
    return any(isinstance(a, type) and issubclass(a, SecretStr) for a in candidates)


def _secret_exclude_spec(model_cls: type[BaseModel]) -> dict[str, Any]:
    """
    Recursively builds a pydantic-style nested `exclude` spec marking every `SecretStr`-typed field anywhere in `model_cls` - e.g. `{"dojo": {"password": True, "sensai": {"api_key": True}}}` - suitable for `model_dump(exclude=...)`.

    Type-based (via `_is_secret_annotation`) rather than value-based, so a field defaulting to `None` (like `dojo.password`) is still caught.
    """
    spec: dict[str, Any] = {}
    for name, info in model_cls.model_fields.items():
        annotation = info.annotation
        if _is_secret_annotation(annotation):
            spec[name] = True
            continue
        args = get_args(annotation)
        candidates = args if args else (annotation,)
        for candidate in candidates:
            if (
                isinstance(candidate, type)
                and issubclass(candidate, BaseModel)
                and not issubclass(candidate, RootModel)
            ):
                nested = _secret_exclude_spec(candidate)
                if nested:
                    spec[name] = nested
                break
    return spec


def _flatten_exclude_spec(spec: dict[str, Any]) -> set[str]:
    """The leaf field names marked `True` in a nested exclude spec (e.g. `{"password", "api_key"}`) - not the intermediate keys used purely to recurse (e.g. `"dojo"`, `"sensai"`), which aren't themselves secret fields and must not be stripped from the schema."""
    names: set[str] = set()
    for key, value in spec.items():
        if value is True:
            names.add(key)
        elif isinstance(value, dict):
            names |= _flatten_exclude_spec(value)
    return names


def _strip_keys_recursively(node: Any, keys: set[str]) -> Any:
    """Recursively deletes any dict key in `keys`, anywhere in `node` (a JSON-like tree of dicts/lists), in place. Safe to apply blanket-wide here since `keys` only ever holds this model's own SecretStr field names (`password`, `api_key`) - not general-purpose enough to reuse for anything that isn't this specific "these names must never appear in a browser-facing payload" guarantee."""
    if isinstance(node, dict):
        for key in list(node.keys()):
            if key in keys:
                del node[key]
            else:
                _strip_keys_recursively(node[key], keys)
    elif isinstance(node, list):
        for item in node:
            _strip_keys_recursively(item, keys)
    return node


_SECRET_EXCLUDE_SPEC = _secret_exclude_spec(MujocoMojoSettings)
_SECRET_FIELD_NAMES = _flatten_exclude_spec(_SECRET_EXCLUDE_SPEC)


def _dojo_settings_schema() -> dict[str, Any]:
    """
    The JSON Schema served to the Dojo web settings panel - every `SecretStr` field name (`password`, `api_key`) deleted entirely, wherever it appears anywhere in the schema tree (property definitions in `$defs`, and any nested-model field's whole-object `default` that would otherwise re-embed it), for the same "the browser has no need to know" reason as `_settings_payload` below.

    Deliberately separate from `write_schema_files`'s `settings.schema.json` (used for local TOML/taplo editor intellisense) - that file is never served over a network and a user has every reason to see `password`/`api_key` there to configure them by hand, so it keeps the full, unmodified schema.
    """
    schema = MujocoMojoSettings.model_json_schema(
        schema_generator=GenerateJsonSchemaWithDefaults
    )
    return _strip_keys_recursively(schema, _SECRET_FIELD_NAMES)


def _settings_payload(settings: MujocoMojoSettings) -> dict[str, Any]:
    return {
        "values": settings.model_dump(mode="json", exclude=_SECRET_EXCLUDE_SPEC),
        "value_meta": _walk_value_meta(settings),
    }


@router.get("")
async def get_settings(request: Request) -> dict[str, Any]:
    """Returns the current settings, their JSON Schema, per-leaf display metadata, the Color name-to-hex table, and whether this request is allowed to edit them. Every SecretStr field (dojo.password, dojo.sensai.api_key) is stripped entirely from both the schema and the values - not masked, removed - since the Dojo web frontend has no legitimate need to know these fields exist at all."""
    settings = MujocoMojoSettings()
    return {
        "schema": _dojo_settings_schema(),
        "color_choices": {member.name: member.value for member in Color},
        "is_localhost": _is_localhost(request),
        **_settings_payload(settings),
    }


@router.post("")
async def post_settings(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    """Validates and persists a full settings tree posted by the client."""
    _require_localhost(request)
    current = MujocoMojoSettings()
    merged = _merge_preserving_secrets(current, body)
    try:
        updated = _validate_replacing(MujocoMojoSettings, merged)
    except ValidationError as exc:
        # surfaces a schema violation (e.g. a width scale below its `ge=0`
        # minimum, an invalid Color name/hex) as a clean 422 with the
        # specific field/message instead of an unhandled 500 - a
        # ValidationError raised here, inside the handler body rather than
        # during FastAPI's own request parsing, isn't caught by its default
        # RequestValidationError handling
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.errors()
        ) from exc
    updated.save()
    return _settings_payload(updated)


@router.post("/reset")
async def post_settings_reset(request: Request) -> dict[str, Any]:
    """Resets every setting to its code-level default."""
    _require_localhost(request)
    updated = MujocoMojoSettings.defaults()
    updated.save()
    return _settings_payload(updated)


@router.get("/color/resolve")
async def resolve_color(value: str = "") -> dict[str, Any]:
    """
    Resolves arbitrary color input (a `Color` enum member name in any case, or a `#rrggbb` hex code) to its canonical hex and, if it matches one, `Color` member name - a read-only, general-purpose endpoint, not tied to a specific settings field, so any color picker in Dojo can resolve what a user typed against `Color.parse`'s normalization instead of re-implementing name/case matching client-side.

    Not localhost-gated, unlike the write endpoints above - this never modifies anything.
    """
    try:
        parsed = Color.parse(value)
    except ValueError:
        return {"valid": False, "hex": None, "name": None, "hidden": False}
    if parsed is None:
        return {"valid": True, "hex": None, "name": None, "hidden": True}
    if parsed in Color.__members__:
        return {
            "valid": True,
            "hex": Color[parsed].value,
            "name": parsed,
            "hidden": False,
        }
    return {"valid": True, "hex": parsed, "name": None, "hidden": False}
