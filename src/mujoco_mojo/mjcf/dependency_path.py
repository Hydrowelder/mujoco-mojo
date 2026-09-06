"""
`DepPath` marks a model attribute as a filesystem dependency that `XMLModel.bundle_assets` should copy into a shared bundle directory. The rest of this module is the bundling pipeline that walks a model tree, decides where each dependency lands, copies the files, and rewrites the model to point at the new locations - including disambiguating two different source files that happen to share a filename.

```mermaid
flowchart TD
    A[bundle_assets] --> B[collect_asset_slots]
    B --> C[(AssetSlot list)]
    C --> D[compute_asset_destinations]
    D --> E{Basename used by only one source?}
    E -->|yes| F[destination = basename]
    E -->|no| G{All sources with this basename share one MD5?}
    G -->|yes, true duplicate| F
    G -->|no, real conflict| H[_disambiguate: widen parent dirs]
    H --> I[destination = parent/.../basename]
    F --> J[(AssetPlan.destinations)]
    I --> J
    J --> K[copy_asset per unique destination]
    K --> L[(files under target_dir)]
    C --> M[apply_asset_destinations]
    J --> M
    M --> N[(model attributes rewritten)]
```
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from filelock import FileLock
from pydantic import GetCoreSchemaHandler

from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.utils import get_checksum

if TYPE_CHECKING:
    from mujoco_mojo.mjcf.xml_model import XMLModel

logger = get_logger(__name__)

__all__ = [
    "AssetPlan",
    "AssetSlot",
    "DepPath",
    "apply_asset_destinations",
    "collect_asset_slots",
    "compute_asset_destinations",
    "copy_asset",
]


class DepPath(Path):
    """Filesystem path to a dependency. MuJoCo Mojo will copy this file."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler):
        """Tells pydantic to validate/serialize a `DepPath` field exactly like a plain `Path`."""
        return handler.generate_schema(Path)


@dataclass
class AssetSlot:
    """One (object, attribute) pair on the model tree whose value contains at least one `DepPath` pointing at a file that exists on disk."""

    obj: XMLModel
    """The XMLModel instance that owns this attribute."""

    attr_name: str
    """Name of the attribute on `obj` holding the DepPath(s)."""

    collection_type: type | None
    """Original container type (`list`, `tuple`, or `set`) if the attribute holds a collection of items, otherwise `None` for a scalar attribute."""

    items: list[Any]
    """The attribute's original, unresolved items, in their original order - `DepPath` entries and anything else, verbatim. Resolved again on demand by `compute_asset_destinations` and `apply_asset_destinations`, so a source `Path` never needs to be tracked positionally."""


@dataclass
class AssetPlan:
    """Output of `compute_asset_destinations`."""

    destinations: dict[Path, Path]
    """Every resolved source `Path` referenced anywhere in the tree, mapped to its bundle-relative destination (e.g. `Path("texture.png")` or `Path("wood/texture.png")`)."""

    source_checksums: dict[Path, str] = field(default_factory=dict)
    """MD5 checksum already computed for a source `Path` that shared a basename with at least one other source, cached so `copy_asset` does not need to recompute it."""


def collect_asset_slots(root: XMLModel) -> list[AssetSlot]:
    """
    Walks the model tree rooted at `root` and collects every attribute slot that references an on-disk asset.

    Args:
        root: The XMLModel instance to crawl, together with everything reachable through its `attributes` and `children`.

    Returns:
        One `AssetSlot` per (object, attribute) pair whose value contains at least one `DepPath` pointing at a file that exists on disk. A `DepPath` pointing at a missing file is logged as an error; if it is the only `DepPath` on that attribute, no `AssetSlot` is created and the attribute is left untouched entirely, matching the pre-existing behavior of this crawler.

    """
    slots: list[AssetSlot] = []

    for obj in root._iter_tree():
        for attr_name in obj.attributes:
            value = getattr(obj, attr_name, None)
            is_collection = isinstance(value, (list, tuple, set))
            items = list(value) if is_collection else [value]

            has_existing_asset = False
            for item in items:
                if isinstance(item, DepPath):
                    resolved = item.resolve()
                    if resolved.exists():
                        has_existing_asset = True
                    else:
                        logger.error(f"Asset file not found: {resolved}")

            if has_existing_asset:
                slots.append(
                    AssetSlot(
                        obj=obj,
                        attr_name=attr_name,
                        collection_type=type(value) if is_collection else None,
                        items=items,
                    )
                )

    return slots


def _folder_token(part: str) -> str:
    """
    Maps one raw `Path.parts` component to a name safe for use as a plain relative path segment.

    Args:
        part: A single component from `Path.parts`, e.g. an ordinary directory name, or `Path.parts[0]` when the path is absolute (a POSIX '/' root or a Windows drive letter).

    Returns:
        `part` unchanged if it is already a safe directory name, otherwise a synthetic token (e.g. "_root", "C_drive") standing in for a filesystem anchor, so a rebuilt Path made only of these tokens can never become absolute again.

    """
    if part in ("\\", "/"):
        return "_root"
    if len(part) in (2, 3) and part[1] == ":" and (len(part) == 2 or part[2] in "\\/"):
        return f"{part[0]}_drive"
    return part


def _disambiguate(paths: list[Path]) -> dict[Path, Path]:
    """
    Builds a minimal, unique nested destination for each of several files that share a basename but differ in content.

    Widens the number of nearest parent-directory names folded into the destination, one level at a time, until every path's parent chain is pairwise unique across the group. Two genuinely different files can never share an identical full parent chain, so widening always terminates.

    Args:
        paths: 2 or more distinct absolute file paths that share a basename but have different content; typically one representative path per distinct-content subgroup.

    Returns:
        Each input path mapped to a relative destination `Path` of the form `parentN/.../parent1/basename`, unique across the whole group. Falls back to appending a numbered `_conflict_{i}` folder in the practically unreachable case where anchor sanitization alone still leaves two chains identical.

    """
    basename = paths[0].name
    chains = [[_folder_token(part) for part in reversed(p.parent.parts)] for p in paths]

    depth = 1
    max_depth = max(len(chain) for chain in chains)
    candidates = [tuple(chain[:depth]) for chain in chains]
    while len(set(candidates)) != len(paths) and depth < max_depth:
        depth += 1
        candidates = [tuple(chain[:depth]) for chain in chains]

    if len(set(candidates)) != len(paths):
        logger.error(
            f"Could not disambiguate {len(paths)} distinct-content assets named '{basename}' by directory name alone; using numbered subfolders as a fallback."
        )
        candidates = [(*c, f"_conflict_{i}") for i, c in enumerate(candidates)]

    return {
        path: Path(*reversed(candidate), basename)
        for path, candidate in zip(paths, candidates)
    }


def compute_asset_destinations(slots: list[AssetSlot]) -> AssetPlan:
    """
    Decides one bundle-relative destination for every distinct source Path referenced across `slots`.

    A basename used by only one source keeps a flat destination. A basename shared by several sources is only a real conflict if their content differs (compared by MD5 via `get_checksum`); sources sharing a basename with byte-identical content are duplicates of each other and collapse to one destination. Real conflicts are nested under real source-directory names via `_disambiguate`.

    Args:
        slots: The `AssetSlot` list returned by `collect_asset_slots`.

    Returns:
        An `AssetPlan` mapping every distinct resolved source `Path` to a bundle-relative destination, plus any source checksums computed along the way.

    """
    all_sources: set[Path] = set()
    for slot in slots:
        for item in slot.items:
            if isinstance(item, DepPath):
                resolved = item.resolve()
                if resolved.exists():
                    all_sources.add(resolved)

    by_basename: dict[str, list[Path]] = {}
    for src in all_sources:
        by_basename.setdefault(src.name, []).append(src)

    destinations: dict[Path, Path] = {}
    source_checksums: dict[Path, str] = {}

    for basename, sources in by_basename.items():
        if len(sources) == 1:
            destinations[sources[0]] = Path(basename)
            continue

        by_checksum: dict[str, list[Path]] = {}
        for src in sorted(sources, key=str):
            checksum = get_checksum(src)
            source_checksums[src] = checksum
            by_checksum.setdefault(checksum, []).append(src)

        if len(by_checksum) == 1:
            for src in sources:
                destinations[src] = Path(basename)
            continue

        groups = sorted(by_checksum.values(), key=lambda g: str(g[0]))
        rep_destinations = _disambiguate([g[0] for g in groups])
        logger.warning(
            f"{len(groups)} distinct-content assets share the filename '{basename}'; "
            "disambiguating by source directory: "
            + ", ".join(f"{rep} -> {dest}" for rep, dest in rep_destinations.items())
        )
        for group in groups:
            dest = rep_destinations[group[0]]
            for src in group:
                destinations[src] = dest

    return AssetPlan(destinations=destinations, source_checksums=source_checksums)


def _link_asset(source: Path, dest_file: Path) -> None:
    """
    Points `dest_file` at `source` with a symlink, replacing whatever is currently there if it does not already point at `source`.

    Skips the copy path's size/hash comparison entirely: checking whether an existing symlink already targets `source` is a single, cheap path comparison, so there is no expensive work here to shortcut around.

    Args:
        source: Absolute path of the file to link to.
        dest_file: Destination path within the bundle's target directory.

    """
    if dest_file.is_symlink():
        if dest_file.resolve() == source:
            logger.debug(
                f"Dependency asset {source} is already symlinked at {dest_file}."
            )
            return
        dest_file.unlink()
    elif dest_file.exists():
        logger.warning(
            f"Asset file {source} already in assets bundle. Old file will be replaced with a symlink."
        )
        dest_file.unlink()

    logger.debug(f"Symlinking dependency asset from {source} to {dest_file}")
    dest_file.symlink_to(source)


def copy_asset(
    source: Path,
    dest_file: Path,
    known_checksum: str | None = None,
    prefer_symlinks: bool = False,
) -> None:
    """
    Copies `source` to `dest_file`, skipping the copy if `dest_file` already holds identical content.

    Creates `dest_file`'s parent directories first, since a destination may be nested to resolve a same-basename conflict. Compares `source` only against whatever already sits at `dest_file` - it does not know or care whether that pre-existing file came from this bundling pass or an earlier, separate one, so a genuine mismatch there keeps the existing behavior: warn and overwrite.

    If `prefer_symlinks` is set and the current platform is POSIX, `dest_file` is symlinked to `source` instead of copied, and the size/hash comparison below is skipped entirely - see `_link_asset`. Windows does not reliably allow unprivileged symlink creation, so `prefer_symlinks` is ignored there and a normal copy is always made.

    Args:
        source: Absolute path of the file to copy.
        dest_file: Destination path within the bundle's target directory.
        known_checksum: `get_checksum(source)` if already computed by the caller, to avoid rehashing the source; computed on demand if `None`.
        prefer_symlinks: Requests a symlink instead of a copy. See `MujocoMojoSettings.assets.symlink`.

    """
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    lock_path = dest_file.with_suffix(dest_file.suffix + ".lock")

    with FileLock(lock_path):
        if prefer_symlinks and os.name == "posix":
            _link_asset(source, dest_file)
            return

        needs_update = True
        if dest_file.exists():
            same_size = source.stat().st_size == dest_file.stat().st_size
            if same_size:
                src_checksum = (
                    known_checksum
                    if known_checksum is not None
                    else get_checksum(source)
                )
                if src_checksum == get_checksum(dest_file):
                    needs_update = False
                    logger.debug(
                        f"Dependency asset {source} was already in the shared asset directory {dest_file.parent} "
                        "(as identified by filename and MD5 hash) so the file will be skipped from being copied."
                    )

            if needs_update:
                logger.warning(
                    f"Asset file {source} already in assets bundle. Old file will be overwritten."
                )

        if needs_update:
            logger.debug(f"Copying dependency asset from {source} to {dest_file}")
            shutil.copy2(source, dest_file)


def apply_asset_destinations(
    slots: list[AssetSlot], destinations: dict[Path, Path], rel_to_xml: Path
) -> None:
    """
    Rewrites each slot's attribute in place with the resolved bundle destinations.

    Every `DepPath` item is resolved again and looked up directly in `destinations`; a `DepPath` with no entry there (a missing file, never bundled) is left as its resolved absolute path, matching the pre-existing behavior of this crawler. Non-`DepPath` items pass through untouched.

    Args:
        slots: The `AssetSlot` list returned by `collect_asset_slots`.
        destinations: Mapping from resolved source `Path` to bundle-relative destination, as produced by `compute_asset_destinations`.
        rel_to_xml: Path prefix (relative to the eventual XML file) to prepend to each destination when writing it back onto the model.

    """
    for slot in slots:
        new_items = []
        for item in slot.items:
            if isinstance(item, DepPath):
                resolved = item.resolve()
                dest = destinations.get(resolved)
                new_items.append(rel_to_xml / dest if dest is not None else resolved)
            else:
                new_items.append(item)

        if slot.collection_type is not None:
            final_val = slot.collection_type(new_items)
        else:
            final_val = new_items[0]
        setattr(slot.obj, slot.attr_name, final_val)
