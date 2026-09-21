from __future__ import annotations

import hashlib
import os
import random
import socket
import sys
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


def find_free_port(host: str, start_port: int, max_tries: int = 50) -> int:
    """
    Returns the first free port at or after `start_port` on `host`.

    Sets OS-appropriate socket reuse options (`SO_REUSEADDR` on POSIX, `SO_EXCLUSIVEADDRUSE` on Windows) so that ports sitting in `TIME_WAIT` from a recently closed server instance do not trigger false "occupied" readings.

    Args:
        host: Host/interface to probe on (e.g. `"127.0.0.1"`, `"0.0.0.0"`).
        start_port: First port to try.
        max_tries: How many consecutive ports to try before giving up.

    Returns:
        The first port in `[start_port, start_port + max_tries)` that accepted a bind.

    Raises:
        RuntimeError: If no port in that range was free.

    """
    for port in range(start_port, start_port + max_tries):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if sys.platform == "win32":
                # On Windows, SO_EXCLUSIVEADDRUSE prevents other processes from hijacking
                # active ports while allowing clean re-binds after process closure.
                s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                # On POSIX, SO_REUSEADDR allows binding over TIME_WAIT sockets from
                # recently closed processes without allowing active listening hijacking.
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            s.bind((host, port))
            return port
        except OSError:
            continue
        finally:
            s.close()

    msg = f"No free port found in [{start_port}, {start_port + max_tries}) on {host}"
    raise RuntimeError(msg)
