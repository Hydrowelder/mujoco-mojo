import faulthandler
import os
import pty
import select
import shutil
import subprocess
import sys
import termios
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

import mujoco_mojo.utils.layers.crash_guard as crash_guard_module

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="looks after a Unix terminal"
)

GUARD = Path(crash_guard_module.__file__)

# a command that supervises itself the way `mujoco-mojo reloaded` does. run again as the child, it puts the
# terminal in the raw mode the terminal UI uses and then does `work`
_PROGRAM = """
import importlib.util, os, pathlib, signal, sys, time, tty
spec = importlib.util.spec_from_file_location("crash_guard", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules["crash_guard"] = module
spec.loader.exec_module(module)
crash = pathlib.Path(sys.argv[2])
status = module.run_supervised(crash)
if status is not None:
    sys.exit(status)
with module.CrashGuard(crash):
    tty.setraw(0)
    {work}
"""


class Terminal:
    """A pseudo terminal standing in for the user's. It starts as an ordinary terminal, and the program under test turns it raw, as the terminal UI does."""

    def __init__(self) -> None:
        self.master, self.slave = pty.openpty()
        self.path = os.ttyname(self.slave)
        self.cooked = termios.tcgetattr(self.slave)

    def settings_restored(self) -> bool:
        return termios.tcgetattr(self.slave) == self.cooked

    def output(self, until: str | None = None, timeout: float = 5.0) -> str:
        """What has been written to the terminal, waiting until `until` shows up or the time is out."""
        text = ""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and (until is None or until not in text):
            if select.select([self.master], [], [], 0.05)[0]:
                text += os.read(self.master, 4096).decode(errors="replace")
        return text

    def close(self) -> None:
        os.close(self.master)
        os.close(self.slave)


@pytest.fixture
def terminal() -> Iterator[Terminal]:
    terminal = Terminal()
    yield terminal
    terminal.close()


def program(tmp_path: Path, work: str) -> Path:
    script = tmp_path / "program.py"
    script.write_text(_PROGRAM.format(work=work))
    return script


def run_on(terminal: Terminal, script: Path, crash: Path) -> int:
    """Runs the program with the terminal as its own, and gives its exit status."""
    return subprocess.run(
        [sys.executable, str(script), str(GUARD), str(crash)],
        stdin=terminal.slave,
        stdout=terminal.slave,
        stderr=terminal.slave,
        timeout=30,
    ).returncode


def test_a_segfault_leaves_the_stack_of_every_thread_and_a_usable_terminal(
    terminal: Terminal, tmp_path: Path
) -> None:
    crash = tmp_path / "crash.log"
    script = program(tmp_path, "os.kill(os.getpid(), signal.SIGSEGV)")

    status = run_on(terminal, script, crash)

    # the way a shell reports a program killed by signal 11
    assert status == 128 + 11
    shown = terminal.output(until="saved to")
    assert crash_guard_module.RESET_TERMINAL in shown
    assert "stopped without cleaning up" in shown
    assert f"saved to {crash}" in shown
    assert "Segmentation fault" in crash.read_text()
    assert terminal.settings_restored()


def test_a_program_killed_without_a_trace_still_gets_the_terminal_put_right(
    terminal: Terminal, tmp_path: Path
) -> None:
    crash = tmp_path / "crash.log"
    script = program(tmp_path, "os.kill(os.getpid(), signal.SIGKILL)")

    status = run_on(terminal, script, crash)

    assert status == 128 + 9
    assert "stopped without cleaning up" in terminal.output(
        until="stopped without cleaning up"
    )
    # there is no stack to point to
    assert "saved to" not in terminal.output(timeout=0.2)
    assert terminal.settings_restored()


def test_a_normal_exit_touches_nothing_and_its_status_is_passed_on(
    terminal: Terminal, tmp_path: Path
) -> None:
    """The terminal UI puts the terminal back itself on the way out, so a program that ends by itself is left alone."""
    crash = tmp_path / "crash.log"
    script = program(tmp_path, "sys.exit(3)")

    status = run_on(terminal, script, crash)

    assert status == 3
    assert terminal.output(timeout=0.3) == ""
    assert not terminal.settings_restored()
    assert not crash.exists()


def test_the_program_that_does_the_work_does_not_supervise_itself(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(crash_guard_module.SUPERVISED, "1")

    assert crash_guard_module.run_supervised(tmp_path / "crash.log") is None


def test_without_a_terminal_there_is_nothing_to_supervise(tmp_path: Path) -> None:
    """Under pytest, stdin is not a terminal."""
    assert crash_guard_module.current_tty() is None
    assert crash_guard_module.run_supervised(tmp_path / "crash.log") is None


def test_the_stacks_of_a_crash_are_kept_and_nothing_is_left_after_a_normal_exit(
    tmp_path: Path,
) -> None:
    crash = tmp_path / "logs" / "crash.log"
    was_on = faulthandler.is_enabled()

    with crash_guard_module.CrashGuard(crash):
        assert crash.exists()
        assert faulthandler.is_enabled()

    assert not crash.exists()
    assert faulthandler.is_enabled() == was_on


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_what_is_typed_at_the_prompt_after_a_crash_is_shown(
    tmp_path: Path,
) -> None:
    """
    The bug that matters, set up as it happens: an interactive bash, a script as the job, and a program that dies while the terminal is raw.

    The shell sees the script exit normally, so it keeps the raw terminal and starts its line editor on it, which then shows nothing that is typed.
    """
    crash = tmp_path / "crash.log"
    script = program(tmp_path, "os.kill(os.getpid(), signal.SIGSEGV)")
    wrapper = tmp_path / "run.sh"
    wrapper.write_text(f"#!/bin/bash\n{sys.executable} {script} {GUARD} {crash}\n")

    pid, master = pty.fork()
    if pid == 0:
        os.environ.update(PS1="PROMPT> ", TERM="xterm-256color")
        os.execv("/bin/bash", ["bash", "--noprofile", "--norc", "-i"])

    def read_until(text: str, timeout: float) -> str:
        data = ""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and text not in data:
            if select.select([master], [], [], 0.05)[0]:
                try:
                    data += os.read(master, 4096).decode(errors="replace")
                except OSError:
                    break
        return data

    try:
        read_until("PROMPT> ", 5)
        os.write(master, f"bash {wrapper}\n".encode())
        # the crash has happened once the stacks are written, and a moment later the program is gone and the
        # shell has drawn its next prompt. neither the message nor a "Segmentation fault" line is relied on,
        # because which of them appear depends on how the program was run
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not (
            crash.exists() and crash.stat().st_size > 0
        ):
            read_until("never appears", 0.1)
        settled = read_until("never appears", 1.5)
        assert settled.rstrip().endswith("PROMPT>") or "PROMPT> " in settled

        os.write(master, b"hel")

        assert "hel" in read_until("hel", 3)
    finally:
        os.write(master, b"\x03exit\n")
        os.close(master)
        os.waitpid(pid, 0)
