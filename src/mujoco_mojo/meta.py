import logging
import shutil
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Final

import platformdirs
from pydantic import HttpUrl

from mujoco_mojo.__about__ import __url__

logger = logging.getLogger(__name__)

REPO_URL = HttpUrl(url=__url__)
"""Link to the remote repo for use with reporting elements."""

DOCS_SOURCE_DIR: Path = Path(__file__).parent / "docs_source"
"""The source of the documentation site that ships with the package: a copy of `mkdocs.yml` and the pages (`docs/`), without the images, and with each page's code includes already filled in. `scripts/gen_docs_source.py` writes it, `mujoco-mojo docs build` builds the site from it, `mujoco-mojo docs path` prints this folder, and SensAI reads the guides from it."""

DOCS_ASSETS_DIR: Path = DOCS_SOURCE_DIR / "docs" / "assets"
"""The logos of the docs site, in the bundled docs source. The Dojo serves its light and dark logo from here, and makes its favicons from the light one, so the package carries one copy of each."""

# where the user's files are kept. every path below comes from these four folders, so moving them is a change here

APP_NAME: Final = "mujoco-mojo"
"""The name of Mojo's folder in each of the platform's user folders."""

CONFIG_DIR: Final[Path] = platformdirs.user_config_path(APP_NAME, appauthor=False)
r"""The platform's user config folder, which holds the global settings: `~/.config/mujoco-mojo` on Linux (under `$XDG_CONFIG_HOME` when it is set), `~/Library/Application Support/mujoco-mojo` on macOS and `%LOCALAPPDATA%\mujoco-mojo` on Windows."""

DATA_DIR: Final[Path] = platformdirs.user_data_path(APP_NAME, appauthor=False)
r"""The platform's user data folder, which holds what the user made and cannot be made again: `~/.local/share/mujoco-mojo` on Linux (under `$XDG_DATA_HOME` when it is set), `~/Library/Application Support/mujoco-mojo` on macOS and `%LOCALAPPDATA%\mujoco-mojo` on Windows."""

CACHE_DIR: Final[Path] = platformdirs.user_cache_path(APP_NAME, appauthor=False)
r"""The platform's user cache folder, which holds what Mojo can make again, so it is safe to delete: `~/.cache/mujoco-mojo` on Linux (under `$XDG_CACHE_HOME` when it is set), `~/Library/Caches/mujoco-mojo` on macOS and `%LOCALAPPDATA%\mujoco-mojo\Cache` on Windows."""

STATE_DIR: Final[Path] = platformdirs.user_state_path(APP_NAME, appauthor=False)
r"""The platform's user state folder, which holds what Mojo remembers between runs: `~/.local/state/mujoco-mojo` on Linux (under `$XDG_STATE_HOME` when it is set), `~/Library/Application Support/mujoco-mojo` on macOS and `%LOCALAPPDATA%\mujoco-mojo` on Windows."""

USER_DIR_VARIABLES: Final = (
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "XDG_STATE_HOME",
)
"""The environment variables that move the folders above on Linux. Something that keeps the user's files out by giving a process an empty home has to clear these too."""

SETTINGS_FILENAME: Final = "settings.toml"
"""The name of a settings file, the global one in `CONFIG_DIR` and a project's in its `.mujoco-mojo` folder."""

SCHEMA_FILENAME: Final = "settings.schema.json"
"""The JSON schema written beside a settings file, for a TOML editor's completion."""

TAPLO_FILENAME: Final = ".taplo.toml"
"""The Taplo config written beside a settings file, which points the editor at the schema."""

PROFILES_DIR: Final[Path] = DATA_DIR / "profiles"
"""The Dojo's saved plot profiles."""

LAB_DIR: Final[Path] = DATA_DIR / "lab"
"""The Signal Lab's saved labs."""

DOCS_SITES_DIR: Final[Path] = CACHE_DIR / "docs"
"""The docs sites `mujoco-mojo docs build` builds, a folder for each version (`v2.8.6`)."""

FAVICONS_DIR: Final[Path] = CACHE_DIR / "favicons"
"""The Dojo's favicons, made from the light logo of the docs."""

CHANGELOG_CACHE_FILE: Final[Path] = CACHE_DIR / "changelog_cache.md"
"""The last changelog fetched successfully from GitHub, kept as the raw text so a later parser change still reads it. `load_changelog` falls back to it, marked as possibly out of date, when GitHub cannot be reached."""

LAST_SEEN_VERSION_FILE: Final[Path] = STATE_DIR / "last_seen_changelog_version.txt"
"""The latest changelog version the user has acknowledged, by closing the Dojo's What's Changed window on it. Read fresh on every `GET /changelog/data` request, not cached in memory, so marking it seen takes effect at once, for a later page load and across a restart of the Dojo."""

LEGACY_DIR: Final[Path] = Path.home() / ".mujoco-mojo"
"""Where Mojo kept all of its user files before version 2.8.6. `move_legacy_files` moves them out of it once."""

LEGACY_FILES: Final[Mapping[str, Path]] = {
    SETTINGS_FILENAME: CONFIG_DIR / SETTINGS_FILENAME,
    SCHEMA_FILENAME: CONFIG_DIR / SCHEMA_FILENAME,
    TAPLO_FILENAME: CONFIG_DIR / TAPLO_FILENAME,
    "profiles": PROFILES_DIR,
    "lab": LAB_DIR,
    "docs": DOCS_SITES_DIR,
    "cache": FAVICONS_DIR,
    "changelog_cache.md": CHANGELOG_CACHE_FILE,
    "last_seen_changelog_version.txt": LAST_SEEN_VERSION_FILE,
}
"""Each file and folder Mojo kept in `LEGACY_DIR`, by its name there, and where it goes."""

LEGACY_LEFTOVERS: Final[Collection[str]] = (f"{SETTINGS_FILENAME}.lock",)
"""Files of `LEGACY_DIR` that are deleted and not moved: the settings file's lock, which is made again beside the file."""


def home_relative(path: Path) -> str:
    """`path` the way it is best shown to the user: from `~/` when it is in the home folder, and whole when it is not."""
    try:
        return f"~/{path.relative_to(Path.home()).as_posix()}"
    except ValueError:
        return str(path)


def move_legacy_files(
    legacy_dir: Path = LEGACY_DIR,
    destinations: Mapping[str, Path] = LEGACY_FILES,
    leftovers: Collection[str] = LEGACY_LEFTOVERS,
    lock_dir: Path = STATE_DIR,
) -> list[str]:
    """
    Moves the files Mojo kept in `legacy_dir` to where each one now belongs, and removes the folder once nothing is left in it. It runs when this module is imported, so every process finds the files where it looks for them, and it does nothing once they are moved.

    Nothing is overwritten or lost: a file whose new place is taken already stays where it is, as does anything Mojo does not know, and both are logged. Processes that start together (a job's workers) take turns through a lock in `lock_dir`.

    Returns:
        The names of what is left in `legacy_dir`, which is empty when the folder was removed or was not there.

    """
    if not legacy_dir.is_dir():
        return []
    if not any((legacy_dir / name).exists() for name in (*destinations, *leftovers)):
        return sorted(p.name for p in legacy_dir.iterdir())

    from filelock import FileLock

    lock_dir.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    taken: list[str] = []
    with FileLock(lock_dir / "move-legacy-files.lock"):
        # another process may have moved everything while this one waited for the lock
        if not legacy_dir.is_dir():
            return []
        for name, destination in destinations.items():
            source = legacy_dir / name
            if not source.exists():
                continue
            if destination.exists():
                taken.append(name)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(source, destination)
            moved.append(f"{name} to {home_relative(destination)}")
        for name in leftovers:
            (legacy_dir / name).unlink(missing_ok=True)
        left = sorted(p.name for p in legacy_dir.iterdir())
        if not left:
            legacy_dir.rmdir()

    if moved:
        logger.info(
            f"Moved Mojo's files out of {home_relative(legacy_dir)}: {', '.join(moved)}."
        )
    if taken:
        logger.warning(
            f"Left {', '.join(taken)} in {home_relative(legacy_dir)}, since a newer copy is already where Mojo now keeps it. Delete the old one when you no longer need it."
        )
    return left


move_legacy_files()
