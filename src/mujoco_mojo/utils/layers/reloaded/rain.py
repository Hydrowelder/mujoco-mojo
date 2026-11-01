"""
The digital rain Reloaded plays as it closes.

Every drop spells the word, so a trail reads "mojo" from top to bottom, each column starting at a different letter. It is kept calm on purpose. A letter is set once, when a drop reaches it, and then holds still as the trail fades, and the trail fades from the accent color into the background. A fresh random glyph in every cell on every frame is what makes rain look blotchy.
"""

import random
from dataclasses import dataclass, field

from rich.segment import Segment
from rich.style import Style
from textual.app import ComposeResult
from textual.color import Color as TextualColor
from textual.screen import Screen
from textual.strip import Strip
from textual.widget import Widget

from .theme import CANVAS, INK_STRONG, LINK

__all__ = ["TRAIL_STYLES", "MatrixRain", "Rain", "RainScreen"]

WORD: str = "mujoco-mojo"
"""What the drops spell, over and over down each trail."""
COLUMN_SPACING: int = 2
"""Only every this many columns carries a drop, so 2 leaves a blank column between drops."""
TRAIL_LENGTH: tuple[int, int] = (6, 16)
"""The shortest and longest trail a drop can have."""
RESTART_WITHIN: float = 1 / 3
"""A drop that has left the screen starts again within this fraction of the screen height above it, which sets how closely one follows another."""
FRAMES_PER_SECOND: int = 20


def _trail_styles(steps: int = 12) -> tuple[Style, ...]:
    """Styles from just behind the head, the link color, to the tail, the background, so a trail dissolves instead of stopping."""
    start = TextualColor.parse(str(LINK))
    end = TextualColor.parse(str(CANVAS))
    return tuple(
        Style(
            color=start.blend(end, step / (steps - 1)).hex,
            bgcolor=str(CANVAS),
        )
        for step in range(steps)
    )


TRAIL_STYLES = _trail_styles()
HEAD_STYLE = Style(color=str(INK_STRONG), bgcolor=str(CANVAS), bold=True)
BLANK_STYLE = Style(bgcolor=str(CANVAS))


@dataclass
class Drop:
    """One falling trail."""

    head: int
    """Row of the leading letter. Negative while it is still above the screen."""
    length: int
    """How many letters trail behind the head."""
    period: int
    """It falls one row every this many steps, so some drops are slower than others."""
    phase: int = 0
    """Which letter of the word sits on row 0, so neighboring columns do not spell it in step."""


@dataclass(eq=False)
class Rain:
    """The falling letters as plain data, so the animation can be checked without a screen."""

    width: int
    height: int
    rng: random.Random = field(default_factory=random.Random)
    drops: dict[int, Drop] = field(init=False)
    """The drop in each column that has one."""
    letters: list[list[str]] = field(init=False)
    """The letter at each row and column, fixed until a drop's head next reaches that cell. A cell no drop has reached holds a space."""
    _step: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        # the first drops start anywhere above the screen, so they do not all fall as one curtain
        self.drops = {
            column: self._new_drop(self.height)
            for column in range(0, self.width, COLUMN_SPACING)
        }
        self.letters = [[" "] * self.width for _ in range(self.height)]

    def _new_drop(self, within: int) -> Drop:
        """A drop waiting above the screen, at most `within` rows from the top. Its head is always off the screen, so every row it lights is a row its head has set a letter in."""
        return Drop(
            head=-self.rng.randint(1, max(1, within)),
            length=self.rng.randint(*TRAIL_LENGTH),
            period=self.rng.choice((1, 1, 2)),
            phase=self.rng.randrange(len(WORD)),
        )

    def step(self) -> None:
        """Moves every drop down, setting the next letter of the word where a head arrives and sending a drop that has left the screen back above it."""
        self._step += 1
        for column, drop in self.drops.items():
            if self._step % drop.period:
                continue
            drop.head += 1
            if 0 <= drop.head < self.height:
                self.letters[drop.head][column] = WORD[
                    (drop.head + drop.phase) % len(WORD)
                ]
            if drop.head - drop.length > self.height:
                self.drops[column] = self._new_drop(int(self.height * RESTART_WITHIN))

    def trail(self, row: int, column: int) -> tuple[int, int] | None:
        """How far behind its drop's head the cell is and how long that drop's trail is, or `None` for an empty cell. A head is 0 behind."""
        drop = self.drops.get(column)
        if drop is None:
            return None
        behind = drop.head - row
        return (behind, drop.length) if 0 <= behind <= drop.length else None


class MatrixRain(Widget):
    """Draws a `Rain` over the whole widget and keeps it falling."""

    def __init__(self, rng: random.Random | None = None) -> None:
        super().__init__()
        self._rng = rng or random.Random()
        self._rain: Rain | None = None

    def on_mount(self) -> None:
        self.set_interval(1 / FRAMES_PER_SECOND, self._advance)

    def _advance(self) -> None:
        width, height = self.size
        if width <= 0 or height <= 0:
            return
        if self._rain is None or (self._rain.width, self._rain.height) != (
            width,
            height,
        ):
            self._rain = Rain(width, height, self._rng)
        else:
            self._rain.step()
        self.refresh()

    def render_line(self, y: int) -> Strip:
        width = self.size.width
        rain = self._rain
        if rain is None or y >= rain.height:
            return Strip([Segment(" " * width, BLANK_STYLE)], width)

        segments: list[Segment] = []
        for column in range(width):
            trail = rain.trail(y, column)
            if trail is None:
                text, style = " ", BLANK_STYLE
            else:
                behind, length = trail
                text = rain.letters[y][column]
                style = (
                    HEAD_STYLE
                    if behind == 0
                    else TRAIL_STYLES[behind * len(TRAIL_STYLES) // (length + 1)]
                )
            # neighbors in the same style share a segment
            if segments and segments[-1].style == style:
                segments[-1] = Segment(segments[-1].text + text, style)
            else:
                segments.append(Segment(text, style))
        return Strip(segments, width)


class RainScreen(Screen[None]):
    """Fills the terminal with rain for a moment, then dismisses itself."""

    def __init__(self, seconds: float) -> None:
        super().__init__()
        self._seconds = seconds

    def compose(self) -> ComposeResult:
        yield MatrixRain()

    def on_mount(self) -> None:
        self.set_timer(self._seconds, self._finish)

    def _finish(self) -> None:
        self.dismiss()
