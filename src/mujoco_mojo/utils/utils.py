from __future__ import annotations

import ctypes
import ctypes.util
import hashlib
import importlib.util
import os
import random
import socket
import sys
import threading
import time
from importlib.resources import files
from pathlib import Path
from typing import Any
from xml.dom import minidom
from xml.etree.ElementTree import tostring

from mujoco_mojo.utils.log import get_logger

__all__ = [
    "display_answers",
    "display_listens",
    "display_problem",
    "get_checksum",
    "get_local_ip",
    "headless_reason",
    "is_empty_list",
    "to_pretty_xml",
    "web_client_available",
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


def display_listens(
    display: str, socket_dir: str = "/tmp/.X11-unix", timeout: float = 0.5
) -> bool | None:
    """
    Whether something accepts connections on the X `display`, such as `:0` or `localhost:10.0`, or `None` for a display of a kind that is not checked here.

    This is only a connection. An SSH forward accepts one even when nothing is behind it, so it does not mean that windows can be opened.
    """
    host, _, rest = display.rpartition(":")
    number = rest.split(".")[0]
    if not number.isdigit() or "/" in host:
        return None
    try:
        if host in ("", "unix"):
            with socket.socket(socket.AF_UNIX) as unix:
                unix.settimeout(timeout)
                unix.connect(f"{socket_dir}/X{number}")
        else:
            socket.create_connection(
                (host.strip("[]"), 6000 + int(number)), timeout
            ).close()
    except OSError:
        return False
    return True


def _x_library_opens(display: str, timeout: float) -> bool:
    """Whether the X library can open `display`, with the login, which is all a native window needs. Counts as opening when the library is not installed, since that cannot be told."""
    name = ctypes.util.find_library("X11")
    if name is None:
        return True
    try:
        x11 = ctypes.CDLL(name)
    except OSError:
        return True
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    outcome: list[bool] = []

    def attempt() -> None:
        handle = x11.XOpenDisplay(display.encode())
        if handle:
            x11.XCloseDisplay(handle)
        outcome.append(bool(handle))

    # the library has no time limit of its own, and a server that accepts but never replies would otherwise hold up whatever asked
    opener = threading.Thread(target=attempt, daemon=True)
    opener.start()
    opener.join(timeout)
    return bool(outcome and outcome[0])


def display_answers(
    display: str,
    socket_dir: str = "/tmp/.X11-unix",
    timeout: float = 0.5,
    open_timeout: float = 1.0,
) -> bool:
    """Whether windows can be opened on the X `display`: something listens on it, and the X library gets a connection from it. Displays of a kind that is not checked here count as answering."""
    listens = display_listens(display, socket_dir, timeout)
    if listens is None:
        return True
    return listens and _x_library_opens(display, open_timeout)


def display_problem() -> str | None:
    """
    Says why a window cannot be opened on this machine's own display, or returns `None` if one probably can.

    Only Linux is checked, because macOS and Windows always have a display. A `DISPLAY` is believed only if something answers on it: an old value left in a shell profile, or the address of an SSH forward that has since gone, makes native viewers give up at once.
    """
    if not sys.platform.startswith("linux") or os.environ.get("WAYLAND_DISPLAY"):
        return None
    display = os.environ.get("DISPLAY")
    if not display:
        return "no display was found"
    if not display_answers(display):
        return f"nothing answers on the display `{display}`"
    return None


def headless_reason() -> str | None:
    """
    Says why a native window probably cannot be shown on this machine, or returns `None` if one can.

    A machine reached over SSH counts as headless even with X forwarding, since the viewer is then far better served in a browser. Otherwise the display is checked, on Linux only.
    """
    if is_ssh_session():
        return "this is an SSH session"
    return display_problem()


def web_client_available() -> bool:
    """
    Whether the browser viewer can run: MuJoCo has its native `state_payload` bindings, and there is a client to serve, either the one built into the MuJoCo package or the one `MUJOCO_WEB_VIEWER_DIST` points at.

    Some builds (e.g. the 4.0.0 Windows wheel) have neither, and a client from `MUJOCO_WEB_VIEWER_DIST` cannot make up for missing bindings.

    The bindings are imported, not looked up with `find_spec`. They are a submodule of MuJoCo's compiled extension that `mujoco.studio.web` registers in `sys.modules` when it is first imported, so there is no file for `find_spec` to find, and it only reports them once something else has imported that package (the first call here used to say no and the second yes).
    """
    try:
        importlib.import_module("mujoco.studio.web.state_payload")
    except ImportError:
        return False
    override = os.environ.get("MUJOCO_WEB_VIEWER_DIST")
    if override and Path(override).is_dir():
        return True
    spec = importlib.util.find_spec("mujoco.studio.web")
    if spec is None:
        return False
    return any(
        (Path(location) / "dist").is_dir()
        for location in spec.submodule_search_locations or []
    )


def get_local_ip() -> str:
    """Returns the actual local IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually need to connect to 8.8.8.8 to work
        s.connect(("8.8.8.8", 1))
        ip: str = s.getsockname()[0]
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


def is_ssh_session() -> bool:
    """
    Returns if the current session is connected via SSH.

    Returns:
        bool: True if connected with SSH.

    """
    return any(var in os.environ for var in ("SSH_CLIENT", "SSH_CONNECTION", "SSH_TTY"))
