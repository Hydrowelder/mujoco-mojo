"""
Colors for the Reloaded terminal UI.

Every value comes from the shared `Color` palette (Tailwind) and each role mirrors a dark mode token in the Dojo's `theme.css`, so the terminal and the browser read as the same product. Pick a role from here instead of a color name or a hex value.
"""

from rich.terminal_theme import TerminalTheme
from textual.theme import Theme

from mujoco_mojo.utils.color import Color

__all__ = [
    "ACCENT",
    "CANVAS",
    "DANGER",
    "INFO",
    "INK_BODY",
    "INK_MUTED",
    "INK_SECONDARY",
    "INK_STRONG",
    "LINE",
    "LINK",
    "MOJO_ANSI_THEME",
    "MOJO_THEME",
    "ON_ACCENT",
    "SCRIM",
    "SECONDARY",
    "SUCCESS",
    "SURFACE",
    "SURFACE_INSET",
    "WARNING",
]

CANVAS = Color.SLATE_900
"""Page background."""
SURFACE = Color.SLATE_800
"""Panels and bars sitting on the canvas."""
SURFACE_INSET = Color.SLATE_950
"""Deeply nested inputs."""
LINE = Color.SLATE_700
"""Structural borders and dividers."""
SCRIM = Color.SLATE_950
"""Backdrop behind a modal."""

INK_STRONG = Color.SLATE_200
"""Emphasized text."""
INK_BODY = Color.SLATE_300
"""Default text."""
INK_SECONDARY = Color.SLATE_400
"""Labels and de-emphasized text."""
INK_MUTED = Color.SLATE_500
"""Timestamps, disabled and empty states."""

ACCENT = Color.CYAN_500
"""The brand color."""
LINK = Color.CYAN_400
"""The accent step used for text on a dark background."""
ON_ACCENT = Color.SLATE_950
"""Readable text over a filled accent, success, warning, or danger surface."""

SUCCESS = Color.EMERALD_500
DANGER = Color.ROSE_500
WARNING = Color.AMBER_500
INFO = Color.INDIGO_500
SECONDARY = Color.VIOLET_500


def _rgb(color: Color) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


MOJO_ANSI_THEME = TerminalTheme(
    _rgb(CANVAS),
    _rgb(INK_BODY),
    normal=[
        _rgb(c)
        for c in (LINE, DANGER, SUCCESS, WARNING, INFO, SECONDARY, ACCENT, INK_BODY)
    ],
    bright=[
        _rgb(c)
        for c in (
            INK_MUTED,
            Color.ROSE_400,
            Color.EMERALD_400,
            Color.AMBER_400,
            Color.INDIGO_400,
            Color.VIOLET_400,
            LINK,
            Color.SLATE_50,
        )
    ],
)
"""What the 16 named terminal colors (`green`, `bold red`, `cyan`, and so on) mean inside the UI. This is what lets markup like `[bold green]` in controller messages and in user code come out in the Mojo palette."""

MOJO_THEME = Theme(
    name="mojo",
    primary=ACCENT,
    secondary=SECONDARY,
    accent=LINK,
    warning=WARNING,
    error=DANGER,
    success=SUCCESS,
    foreground=INK_BODY,
    background=CANVAS,
    surface=SURFACE,
    panel=SURFACE,
    dark=True,
    variables={
        # a focused control gets the accent ring and every other border the structural line color, as in the Dojo
        "border": ACCENT,
        "border-blurred": LINE,
        "input-cursor-background": ACCENT,
        "input-cursor-foreground": ON_ACCENT,
        "input-selection-background": f"{ACCENT} 35%",
        "footer-background": SURFACE,
        "footer-key-foreground": LINK,
        "footer-description-foreground": INK_SECONDARY,
        "scrollbar": Color.SLATE_600,
        "scrollbar-hover": INK_MUTED,
        "scrollbar-active": ACCENT,
        "scrollbar-background": CANVAS,
        "scrollbar-corner-color": CANVAS,
        "link-color": LINK,
        # roles the stylesheet uses that Textual has no variable for
        "surface-inset": SURFACE_INSET,
        "scrim": SCRIM,
    },
)
"""The Textual theme, registered and selected by `ReloadedApp`."""
