import sys

import pytest

from mujoco_mojo.settings import ReloadedSettings, default_user_interface
from mujoco_mojo.typing import UserInterface
from mujoco_mojo.utils.utils import headless_reason


def set_environment(
    monkeypatch: pytest.MonkeyPatch,
    *,
    platform: str,
    ssh: str | None = None,
    display: str | None = None,
    wayland: str | None = None,
) -> None:
    """Makes this machine look like the one described, whatever it really is."""
    monkeypatch.setattr(sys, "platform", platform)
    for name in (
        "SSH_CONNECTION",
        "SSH_CLIENT",
        "SSH_TTY",
        "DISPLAY",
        "WAYLAND_DISPLAY",
    ):
        monkeypatch.delenv(name, raising=False)
    if ssh is not None:
        monkeypatch.setenv("SSH_CONNECTION", ssh)
    if display is not None:
        monkeypatch.setenv("DISPLAY", display)
    if wayland is not None:
        monkeypatch.setenv("WAYLAND_DISPLAY", wayland)


def test_a_linux_desktop_can_show_a_window(monkeypatch: pytest.MonkeyPatch) -> None:
    set_environment(monkeypatch, platform="linux", display=":0")

    assert headless_reason() is None


def test_a_wayland_desktop_can_show_a_window(monkeypatch: pytest.MonkeyPatch) -> None:
    set_environment(monkeypatch, platform="linux", wayland="wayland-0")

    assert headless_reason() is None


def test_linux_without_a_display_is_headless(monkeypatch: pytest.MonkeyPatch) -> None:
    set_environment(monkeypatch, platform="linux")

    assert headless_reason() == "no display was found"


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_macos_and_windows_always_have_a_display(
    monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    set_environment(monkeypatch, platform=platform)

    assert headless_reason() is None


@pytest.mark.parametrize("variable", ["SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"])
def test_an_ssh_session_is_headless_even_with_x_forwarding(
    monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    set_environment(monkeypatch, platform="linux", display="localhost:10.0")
    monkeypatch.setenv(variable, "1")

    assert headless_reason() == "this is an SSH session"


def test_ssh_wins_on_machines_that_always_have_a_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_environment(monkeypatch, platform="darwin", ssh="10.0.0.2 5000 10.0.0.3 22")

    assert headless_reason() == "this is an SSH session"


def test_the_viewer_is_studio_on_a_machine_that_can_show_a_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_environment(monkeypatch, platform="linux", display=":0")

    assert default_user_interface() is UserInterface.STUDIO
    assert ReloadedSettings().ui is UserInterface.STUDIO


@pytest.mark.parametrize(
    ("ssh", "display"), [("10.0.0.2 5000 10.0.0.3 22", ":0"), (None, None)]
)
def test_the_viewer_is_web_on_a_headless_machine(
    monkeypatch: pytest.MonkeyPatch, ssh: str | None, display: str | None
) -> None:
    set_environment(monkeypatch, platform="linux", ssh=ssh, display=display)

    assert default_user_interface() is UserInterface.WEB
    assert ReloadedSettings().ui is UserInterface.WEB


@pytest.mark.parametrize("ui", list(UserInterface))
def test_a_viewer_chosen_in_settings_beats_the_machine(
    monkeypatch: pytest.MonkeyPatch, ui: UserInterface
) -> None:
    set_environment(monkeypatch, platform="linux")

    assert ReloadedSettings.model_validate({"ui": ui.value}).ui is ui
