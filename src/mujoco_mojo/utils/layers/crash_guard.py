"""
Keeps the terminal usable when Reloaded dies without a chance to clean up after itself, e.g. a crash in native code, and saves where a crash happened.

The terminal UI switches the terminal to its own screen, turns mouse reporting on, and reads keys raw. A process that is killed outright never switches any of that back. Nothing inside the dead process can fix that, and nothing outside it can do it quickly enough: a shell started from a script sees the script exit normally, so it keeps the terminal as it finds it, raw, and starts its line editor there. The line editor takes a terminal with echo off to mean that echo is wanted off, so it shows nothing that is typed, and it keeps that state for every later prompt. A helper process woken the instant Reloaded died still lost that race to the shell.

So the command runs Reloaded as a child process and waits for it. The parent is part of the job the shell is waiting for, so it can put the terminal right before the shell gets it back.

It also turns on Python's fault handler, so a crash writes the Python stack of every thread to a file, which is what is needed to find out where it happened.
"""

import faulthandler
import os
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

__all__ = [
    "RESET_TERMINAL",
    "SUPERVISED",
    "CrashGuard",
    "current_tty",
    "restore_terminal",
    "run_supervised",
]

RESET_TERMINAL = (
    "\x1b[?1049l"  # leave the alternate screen
    "\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1005l\x1b[?1006l\x1b[?1015l"  # mouse reporting off
    "\x1b[?1004l"  # focus reporting off
    "\x1b[?2004l"  # bracketed paste off
    "\x1b[?2026l"  # synchronized output off
    "\x1b[<9u"  # drop any keyboard protocol the UI asked for
    "\x1b[?1l\x1b>"  # plain cursor keys and keypad
    "\x1b[?7h"  # wrap long lines again
    "\x1b[?25h"  # show the cursor
    "\x1b[0m"  # plain colors
)
"""What to send a terminal to undo everything the terminal UI turns on."""

SUPERVISED = "MOJO_RELOADED_SUPERVISED"
"""Set in the environment of the process that does the work, so it does not supervise itself."""


def current_tty() -> str | None:
    """The path of the terminal Reloaded is running in, or `None` when there is no terminal to look after (output is piped, or this is not a Unix system)."""
    if os.name != "posix":
        return None
    try:
        return os.ttyname(sys.stdin.fileno())
    except (OSError, ValueError):
        return None


def restore_terminal(tty_path: str, saved: Any, message: str = "") -> None:
    """Puts the terminal at `tty_path` back the way it was: its input settings as `saved` (from `termios.tcgetattr`), and its screen modes reset. Prints `message` afterwards, if there is one."""
    import termios

    fd = os.open(tty_path, os.O_RDWR | os.O_NOCTTY)
    try:
        termios.tcsetattr(fd, termios.TCSANOW, saved)
        os.write(fd, (RESET_TERMINAL + message).encode())
    finally:
        os.close(fd)


def crash_message(crash_path: Path) -> str:
    """What to tell the user after Reloaded was killed, including where the stacks went if a crash left any."""
    message = "\r\nReloaded stopped without cleaning up after itself, so the terminal was reset.\r\n"
    try:
        if crash_path.stat().st_size > 0:
            message += f"Python's stack for every thread was saved to {crash_path}\r\n"
    except OSError:
        pass
    return message


def run_supervised(crash_path: Path) -> int | None:
    """
    Runs the command that is running now again, as a child process, waits for it, and gives the status to exit with. If the child was killed, the terminal is put right first.

    Gives `None` when that is not wanted, which means the caller should just carry on and do the work: this already is the child, or there is no terminal to look after.
    """
    tty_path = current_tty()
    if os.environ.get(SUPERVISED) or tty_path is None:
        return None
    import termios

    try:
        fd = os.open(tty_path, os.O_RDWR | os.O_NOCTTY)
        saved = termios.tcgetattr(fd)
        os.close(fd)
    except (OSError, termios.error):
        return None

    # the very command line, so the child is exactly what would have run
    child = subprocess.Popen(sys.orig_argv, env={**os.environ, SUPERVISED: "1"})
    # a Ctrl+C reaches both, and what it means is for the child to decide. set after the child starts,
    # because an ignored signal stays ignored in a process that is started from this one
    previous = {signal.SIGINT: signal.signal(signal.SIGINT, signal.SIG_IGN)}
    for forwarded in (signal.SIGTERM, signal.SIGHUP):
        previous[forwarded] = signal.signal(
            forwarded, lambda number, frame: child.send_signal(number)
        )
    try:
        status = child.wait()
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)

    if status < 0:
        try:
            restore_terminal(tty_path, saved, crash_message(crash_path))
        except OSError:
            # the terminal itself is gone, e.g. the window was closed, and there is nothing left to restore
            pass
        return 128 - status
    return status


@dataclass(eq=False)
class CrashGuard:
    """Around the terminal UI: saves the stack of every thread to `crash_path` if the process crashes. Leaves no file behind after a normal exit."""

    crash_path: Path
    """Where the stacks of a crash are written."""
    _file: IO[str] | None = field(default=None, init=False, repr=False)
    _faulthandler_was_on: bool = field(default=False, init=False, repr=False)

    def __enter__(self) -> "CrashGuard":
        self._faulthandler_was_on = faulthandler.is_enabled()
        self.crash_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.crash_path.open("w")
        faulthandler.enable(self._file, all_threads=True)
        return self

    def __exit__(self, *exc_info: object) -> None:
        # none of this may raise, or it would hide whatever is already being raised
        try:
            self._restore_faulthandler()
        finally:
            if self._file is not None:
                self._file.close()
                self._file = None
            try:
                if self.crash_path.stat().st_size == 0:
                    self.crash_path.unlink()
            except OSError:
                pass

    def _restore_faulthandler(self) -> None:
        faulthandler.disable()
        # the original stderr, since `sys.stderr` may be a stand-in without a file behind it
        stderr = sys.__stderr__
        if self._faulthandler_was_on and stderr is not None:
            try:
                faulthandler.enable(stderr, all_threads=True)
            except (OSError, ValueError):
                pass
