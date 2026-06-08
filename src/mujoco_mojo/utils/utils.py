from __future__ import annotations

import hashlib
import os
import random
import socket
import time
from importlib.resources import files
from pathlib import Path
from typing import Any
from xml.dom import minidom
from xml.etree.ElementTree import tostring

from mujoco_mojo.utils.log import get_logger

__all__ = [
    "get_checksum",
    "get_local_ip",
    "is_empty_list",
    "to_pretty_xml",
    "write_dojo_script",
]

logger = get_logger(__name__)


def to_pretty_xml(element) -> str:
    rough = tostring(element, "utf-8")
    reparsed = minidom.parseString(rough)
    return reparsed.toprettyxml(indent="  ")


def is_empty_list(v: Any) -> bool:
    return not len(v)


def get_checksum(path: Path, retries: int = 5) -> str:
    """Returns MD5 hash of a file using a buffer to stay memory-efficient."""
    for i in range(retries):
        try:
            hash_md5 = hashlib.md5()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except (PermissionError, OSError):
            if i == retries - 1:  # last attempt
                msg = f"Failed to get checksum for {path} after {retries} attempts"
                logger.error(msg)
                raise
            time.sleep(0.1 + random.uniform(0, 0.1))
    msg = "I have no clue how you got here, I didnt think that was possible..."
    logger.error(msg)
    raise Exception(msg)


def write_dojo_script(workdir: Path) -> None:
    """Writes a `dojo.sh` launcher into a freshly-created workdir, so results can be browsed with `mujoco-mojo dojo`."""
    dest = workdir / "dojo.sh"
    if dest.exists():
        return

    tmpl = files("mujoco_mojo.templates")
    dest.write_text(
        tmpl.joinpath("dojo.sh").read_text(encoding="utf-8"), encoding="utf-8"
    )
    os.chmod(dest, 0o755)


def get_local_ip():
    """Returns the actual local IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually need to connect to 8.8.8.8 to work
        s.connect(("8.8.8.8", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip
