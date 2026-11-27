import dataclasses
import math
import sys

import mujoco
from mujoco.studio import messages, plugin, sim
from mujoco.studio.dear_imgui import dear_imgui as imgui

from mujoco_mojo.utils.color import Color
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.visualization import ArrowConfig, LineConfig

from ..controller import (
    ControllerStatus,
    Outcome,
    RunState,
    control_states,
    read_run_target,
    speed_label,
)
from ..theme import ACCENT, DANGER, LINK, ON_ACCENT, SUCCESS, WARNING
from .base import ViewerControls

__all__ = [
    "MAX_OVERLAY_GEOMS",
    "PANEL_TITLE",
    "PANEL_WIDTH_EM",
    "SPEED_PRESETS",
    "UNTIL_CHOICES",
    "MojoCommandEvent",
    "MojoCommands",
    "MojoOverlay",
    "MojoOverlaySnapshot",
    "MojoPanel",
    "MojoStatusSnapshot",
    "MojoStepControl",
    "PanelRow",
    "fit_grid",
    "mojo_speed",
    "run_command",
    "seed_command",
    "step_command",
    "studio_speed",
    "trial_command",
]

logger = get_logger(__name__)


def _browser_geom_cap() -> int:
    """
    How many extra geoms the browser viewer can draw.

    Some mujoco builds (e.g. the 4.0.0 Windows wheel) ship Studio without the browser viewer and its `state_payload` module. The browser viewer is the only one with a cap, so without it there is none.
    """
    try:
        from mujoco.studio.web import state_payload
    except ImportError:
        return sys.maxsize
    return int(state_payload.MAX_EXTRA_GEOMS)


MAX_OVERLAY_GEOMS: int = _browser_geom_cap()
"""How many extra geoms the browser viewer draws. Anything past it is dropped. Unlimited when this mujoco build has no browser viewer."""

_REAL_TIME_PERCENT = 100.0
"""Studio writes its speed as a percentage of real time, where Reloaded writes a multiple."""
_SLOWEST_PERCENT = 0.1

PANEL_TITLE = "Reloaded"
"""The title of Reloaded's own window in the viewer."""

PANEL_WIDTH_EM = 26.0
"""How wide Reloaded's window opens, in multiples of the font size, so it suits any font. Dragging its edge changes it."""

SPEED_PRESETS: tuple[tuple[str, float], ...] = (
    ("0.25x", 0.25),
    ("0.5x", 0.5),
    ("1x", 1.0),
    ("2x", 2.0),
    ("5x", 5.0),
    ("10x", 10.0),
    ("Max", math.inf),
)
"""The speeds Reloaded's window offers, each a label and a multiple of real time. Studio's own slider stops at real time."""

# Font Awesome 4 code points: Studio merges that font into its own, so they draw inside any label
_ICON_TERMINAL = "\uf120"
_ICON_TACHOMETER = "\uf0e4"
_ICON_COG = "\uf013"
_ICON_INFO = "\uf05a"
_ICON_GEN = "\uf021"
_ICON_PLAY = "\uf04b"
_ICON_PAUSE = "\uf04c"
_ICON_STEP = "\uf051"
_ICON_STOP = "\uf04d"
_ICON_FLAG = "\uf024"
_ICON_DOT = "\uf111"
_ICON_DOT_RING = "\uf192"
_ICON_RANDOM = "\uf074"
_ICON_HASHTAG = "\uf292"
_ICON_EYE = "\uf06e"
_ICON_VIDEO = "\uf03d"
_ICON_HISTORY = "\uf1da"
_ICON_CLOCK = "\uf017"
_ICON_FINISH = "\uf11e"
_ICON_COMMENT = "\uf0e5"
_ICON_CHECK = "\uf058"
_ICON_WARNING = "\uf071"
_ICON_STOPPED = "\uf28d"
_ICON_FAILED = "\uf057"

_PANEL_COMMANDS = (
    ("gen", _ICON_GEN, "Gen", "Generate the model without running it"),
    (
        "run",
        _ICON_PLAY,
        "Run",
        "Generate and run the runtime, or carry a paused run on",
    ),
    ("pause", _ICON_PAUSE, "Pause", "Hold the run where it is"),
    ("step", _ICON_STEP, "Step", "Advance the run by the step count below"),
    ("stop", _ICON_STOP, "Stop", "Abort the run"),
)
"""The buttons of Reloaded's window, the same as the terminal's: the command each types, its icon, its label, and what it does."""

_REFUSED = {
    "run": "Pause at needs a time or a whole step count of 0 or more",
    "step": "The step count needs to be a whole number of 1 or more",
}
"""Why a button is greyed out when it is because of what was typed in the window, by its command."""

UNTIL_CHOICES: tuple[tuple[str, str | None, str], ...] = (
    ("Never", None, ""),
    ("Time", "time", "timestamp"),
    ("Step", "step", "step number"),
)
"""Where a run started from Reloaded's window pauses itself: a label, the word `run until` takes (or `None` for not at all), and what its field asks for."""

_STATE_COLORS = {
    RunState.IDLE: SUCCESS,
    RunState.RUNNING: WARNING,
    RunState.PAUSED: LINK,
    RunState.STOPPING: DANGER,
}
"""The colors of the terminal's state badge, so the window and the terminal agree."""

_OUTCOME_LOOKS = {
    Outcome.SUCCESS: (_ICON_CHECK, SUCCESS),
    Outcome.SATISFIED: (_ICON_CHECK, SUCCESS),
    Outcome.TERMINATED: (_ICON_WARNING, WARNING),
    Outcome.STOPPED: (_ICON_STOPPED, WARNING),
    Outcome.FAILED: (_ICON_FAILED, DANGER),
}
"""The icon and the terminal's color for each way a run can end."""

_FILL = -1.17549435e-38
"""An item width that reaches the right edge of the window or table cell: Dear ImGui's `-FLT_MIN`. Its widths are 32-bit floats, so the smallest 64-bit float would round to 0 and the item would be drawn 0 wide."""


def fit_grid(
    count: int, cell: float, available: float, spacing: float
) -> tuple[int, float]:
    """
    Lays `count` equal cells, each at least `cell` wide, across a line `available` wide with `spacing` between them.

    Returns how many go on each line and how wide each is drawn, which stretches a full line to the width. The cells of a last, shorter line keep that width, so the columns line up.
    """
    columns = max(1, min(count, int((available + spacing) // (cell + spacing))))
    width = max(cell, (available - spacing * (columns - 1)) / columns)
    return columns, width


def run_command(until: str | None, value: str) -> str | None:
    """The command the Run button types: `run`, or `run until time <N>` or `run until step <N>` when `until` is `time` or `step`. `None` when `value` is not a target the terminal takes."""
    if until is None:
        return "run"
    words = ["until", until, value.strip()]
    if read_run_target(words) is None:
        return None
    return "run " + " ".join(words)


def step_command(count: str) -> str | None:
    """The command the Step button types, or `None` when `count` is not a whole number of 1 or more."""
    try:
        steps = int(count.strip())
    except ValueError:
        return None
    return f"step {steps}" if steps >= 1 else None


def seed_command(text: str) -> str | None:
    """The command that sets the seed typed in Reloaded's window, where an empty field clears it. `None` when `text` is not a whole number."""
    if not text.strip():
        return "seed none"
    try:
        return f"seed {int(text.strip())}"
    except ValueError:
        return None


def trial_command(text: str) -> str | None:
    """The command that sets the trial number typed in Reloaded's window, or `None` when `text` is not a whole number."""
    try:
        return f"trial {int(text.strip())}"
    except ValueError:
        return None


def _vec4(color: Color) -> imgui.Vec4:
    red, green, blue, alpha = (float(v) for v in color.rgba)
    return imgui.Vec4(red, green, blue, alpha)


def _button_grid(labels: list[str]) -> tuple[int, float]:
    """How many of the buttons labeled `labels` go on each line of the window, and how wide each is, so the lines fill the width."""
    style = imgui.GetStyle()
    cell = (
        max(imgui.CalcTextSize(label).x for label in labels) + 2 * style.FramePadding.x
    )
    return fit_grid(
        len(labels), cell, imgui.GetContentRegionAvail().x, style.ItemSpacing.x
    )


def _label_cell(icon: str, label: str) -> None:
    """The left cell of a row in one of the window's tables, lined up with a field beside it."""
    imgui.TableNextColumn()
    imgui.AlignTextToFramePadding()
    imgui.TextDisabled(f"{icon}  {label}")
    imgui.TableNextColumn()


def _begin_rows(name: str) -> bool:
    """Starts one of the window's two column tables, labels on the left and values filling the rest. Call `imgui.EndTable` only when it returns `True`."""
    if not imgui.BeginTable(name, 2, int(imgui.TableFlags.BordersInnerH)):
        return False
    imgui.TableSetupColumn("", int(imgui.TableColumnFlags.WidthFixed))
    imgui.TableSetupColumn("", int(imgui.TableColumnFlags.WidthStretch))
    return True


def studio_speed(speed: float) -> float:
    """
    The speed to show on Studio's slider for a Reloaded `speed`.

    Studio's slider runs from 0.1 to 100 percent of real time, so anything faster than real time shows as 100 and manual stepping, which has no speed of its own, does too.
    """
    if speed <= 0:
        return _REAL_TIME_PERCENT
    return min(max(speed * _REAL_TIME_PERCENT, _SLOWEST_PERCENT), _REAL_TIME_PERCENT)


def mojo_speed(percent: float) -> float:
    """The Reloaded speed, a multiple of real time, for a Studio slider reading in percent."""
    return percent / _REAL_TIME_PERCENT


class MojoStepControl(plugin.SimPlugin):
    """
    Stands in for Studio's step control and history plugins, neither of which can be used: they would step the physics themselves, and Mojo's runtime does that.

    It passes what the viewer's buttons ask for to Reloaded's controller, and shows the controller's pause and speed on the viewer's widgets, so Studio and the terminal agree. It consumes the viewer's reset and reload requests, because the built in handlers would replace or reset the model that the runtime is stepping.
    """

    def __init__(self, controls: ViewerControls) -> None:
        self._controls = controls
        self._shown: tuple[bool, float] | None = None
        """The pause and speed last sent to the viewer, so they are only sent again when they change."""
        self._warned_noise = False
        self._noise = (0.0, 0.0)
        """The control noise the viewer's panel holds. Reloaded adds none, but the panel's own value is sent back as it is, so the slider does not snap back under the hand that is dragging it."""

    def _snapshot(self, paused: bool, speed: float) -> messages.StepControlSnapshot:
        # going through Studio's own object keeps its clamping and float precision, so a reading that comes
        # back from the slider unchanged compares equal to what was sent
        control = sim.StepControl()
        control.set_pause_state(
            sim.PauseState.NORMAL_PAUSED if paused else sim.PauseState.UNPAUSED
        )
        control.set_speed(studio_speed(speed))
        control.set_noise_parameters(*self._noise)
        return messages.StepControlSnapshot.from_step_control(control)

    def _apply_pause_state(self, pause_state: sim.PauseState) -> None:
        if pause_state == sim.PauseState.NORMAL_PAUSED:
            self._controls.pause()
        else:
            self._controls.resume()

    @messages.handler
    def _on_step_control(self, event: messages.StepControlSnapshot) -> bool:
        # the viewer only sends one when something on its panel changed, so whatever differs from the
        # controller's own state is what the user just did
        wanted = self._snapshot(self._controls.paused, self._controls.speed)
        if event.pause_state != wanted.pause_state:
            self._apply_pause_state(event.pause_state)
        if not math.isclose(event.speed, wanted.speed, rel_tol=1e-4):
            self._controls.set_speed(f"{mojo_speed(event.speed):g}")
        self._noise = (event.noise_scale, event.noise_rate)
        if self._noise != (0.0, 0.0) and not self._warned_noise:
            self._warned_noise = True
            logger.info(
                "Reloaded does not add control noise, so that setting has no effect."
            )
        # sent again at the next step, so a change that was refused does not stay on the widgets
        self._shown = None
        return True

    @messages.handler
    def _on_request_pause(self, event: messages.RequestPauseEvent) -> bool:
        self._apply_pause_state(event.pause_state)
        return True

    @messages.handler
    def _on_single_step(self, _: messages.SingleStepEvent) -> bool:
        self._controls.step("1")
        return True

    @messages.handler
    def _on_reset(self, _: messages.ResetEvent) -> bool:
        self._controls.rerun()
        return True

    @messages.handler
    def _on_load_model(self, event: messages.LoadModelEvent) -> bool:
        # the Reload button sends the shown model's path, which is the trial's xml, so only another path is a dropped file
        if event.path and event.path != self._shown_path():
            logger.warning(
                f"Reloaded builds the model with your generator, so '{event.path}' was not loaded."
            )
        else:
            self._controls.rerun()
        return True

    @messages.handler
    def _on_post_model(self, _: messages.PostModelEvent) -> None:
        # a model with a new path resets the viewer's step control, so what it shows has to be sent again
        self._shown = None

    @messages.handler
    def _on_step(self, _: messages.StepEvent) -> None:
        # nothing is stepped here. this runs once per sync, which is the moment to show a pause or speed
        # that was changed from the terminal
        shown = (self._controls.paused, self._controls.speed)
        if shown != self._shown:
            self._send(self._snapshot(*shown))
            self._shown = shown

    def _send(self, snapshot: messages.StepControlSnapshot) -> None:
        self.handle.send_to_viewer(snapshot)

    def _shown_path(self) -> str:
        """The path of the model the viewer shows, which is what its Reload button sends."""
        return self.handle.model_path


@dataclasses.dataclass(frozen=True)
class MojoCommandEvent(messages.Event):
    """A button of Reloaded's window was pressed, on its way from the viewer to the simulation thread."""

    text: str
    """The command, as it would be typed in the terminal."""


@dataclasses.dataclass(frozen=True)
class PanelRow:
    """One line of the Session section of Reloaded's window."""

    icon: str
    label: str
    value: str
    color: Color | None = None
    """The theme color the value is drawn in, or `None` for the window's own text color."""


@dataclasses.dataclass(frozen=True)
class MojoStatusSnapshot(messages.Snapshot):
    """What Reloaded's window shows about the session, on its way from the simulation thread to the viewer."""

    status: ControllerStatus
    has_runtime: bool
    position: tuple[float, int] = (0.0, 0)
    """The simulation time and step count of the run in progress, or where the last run ended."""

    @property
    def rows(self) -> tuple[PanelRow, ...]:
        """The Session section: what the session is doing and where the run is, what Enter or Reload repeats, and how the last run ended and why, worded as the terminal words them."""
        status = self.status
        sim_time, steps = self.position
        rows = [
            PanelRow(
                _ICON_DOT_RING,
                "State",
                f"{_ICON_DOT}  {status.state.value.upper()}",
                _STATE_COLORS[status.state],
            ),
            PanelRow(_ICON_CLOCK, "Time", f"{sim_time:.3f} s"),
            PanelRow(_ICON_STEP, "Step", f"{steps:,}"),
            PanelRow(_ICON_TACHOMETER, "Speed", speed_label(status.playback_speed)),
            PanelRow(_ICON_HISTORY, "Last command", status.last_command),
        ]
        if status.last_duration is not None and status.last_outcome is not None:
            icon, color = _OUTCOME_LOOKS[status.last_outcome]
            rows.append(
                PanelRow(
                    _ICON_FINISH,
                    "Last run",
                    f"{icon}  {status.last_duration:.2f}s {status.last_outcome.value}",
                    color,
                )
            )
            if status.last_detail:
                rows.append(PanelRow(_ICON_COMMENT, "Why", status.last_detail, color))
        return tuple(rows)


class MojoCommands(plugin.SimPlugin):
    """Links Reloaded's window to Reloaded's controller: carries out what its buttons ask for, and sends it what the session is doing."""

    def __init__(self, controls: ViewerControls) -> None:
        self._controls = controls
        self._shown: MojoStatusSnapshot | None = None

    @messages.handler
    def _on_command(self, event: MojoCommandEvent) -> bool:
        self._controls.submit(event.text)
        return True

    @messages.handler
    def _on_step(self, _: messages.StepEvent) -> None:
        # runs once per sync, idle or not, so a change made from the terminal shows within a frame
        snapshot = MojoStatusSnapshot(
            self._controls.status(),
            self._controls.has_runtime,
            self._controls.position,
        )
        if snapshot != self._shown:
            self._send(snapshot)
            self._shown = snapshot

    def _send(self, snapshot: MojoStatusSnapshot) -> None:
        self.handle.send_to_viewer(snapshot)


class MojoPanel(plugin.ViewerPlugin):
    """Reloaded's own window in the viewer, for what Studio's panels have no place for: the terminal's commands, speeds past real time, the session's settings, and what the session is doing."""

    def __init__(self) -> None:
        self._latest: MojoStatusSnapshot | None = None
        self._width: float | None = None
        """The window's width as it was last drawn, which the user may have dragged, since its height is set again every frame."""
        self._until = 0
        """Which of `UNTIL_CHOICES` a run started from the window pauses at."""
        self._until_value = ""
        """The time or step a run started from the window pauses at, as typed."""
        self._step_count = "1"
        """How many steps the Step button takes, as typed."""
        self._drafts: dict[str, str] = {}
        """What is being typed into a setting's field, by setting, while the field is being edited."""

    @messages.handler
    def _on_status(self, snapshot: MojoStatusSnapshot) -> None:
        self._latest = snapshot

    @messages.handler
    def _on_build_gui(self, _: messages.BuildGuiEvent) -> None:
        width = self._width or PANEL_WIDTH_EM * imgui.GetFontSize()
        # a height of 0 fits the contents, and fitting it every frame makes room for rows that wrap
        imgui.SetNextWindowSize(imgui.Vec2(width, 0), int(imgui.Cond.Always))
        if imgui.Begin(PANEL_TITLE, flags=int(imgui.WindowFlags.NoScrollbar))[0]:
            self.build_gui()
        self._width = imgui.GetWindowWidth()
        imgui.End()

    def build_gui(self) -> None:
        """Submits the window's widgets. Everything it changes is sent as the command the terminal would be typed, so the window and the terminal cannot behave differently."""
        latest = self._latest
        if latest is None:
            imgui.TextDisabled("Waiting for Reloaded...")
            return
        self._build_commands_gui(latest)
        self._build_speed_gui(latest.status.playback_speed)
        self._build_settings_gui(latest.status)
        self._build_session_gui(latest)

    def _build_commands_gui(self, latest: MojoStatusSnapshot) -> None:
        imgui.SeparatorText(f"{_ICON_TERMINAL}  Commands")
        enabled = control_states(latest.status.state, latest.has_runtime)
        typed = {
            "gen": "gen",
            "run": run_command(UNTIL_CHOICES[self._until][1], self._until_value),
            "pause": "pause",
            "step": step_command(self._step_count),
            "stop": "stop",
        }
        labels = [f"{icon}  {label}" for _, icon, label, _ in _PANEL_COMMANDS]
        columns, width = _button_grid(labels)
        for i, ((command, _, _, tooltip), label) in enumerate(
            zip(_PANEL_COMMANDS, labels, strict=True)
        ):
            if i % columns:
                imgui.SameLine()
            text = typed[command]
            imgui.BeginDisabled(not enabled[command] or text is None)
            if imgui.Button(label, imgui.Vec2(width, 0)) and text is not None:
                self._send(text)
            imgui.EndDisabled()
            imgui.SetItemTooltip(tooltip if text is not None else _REFUSED[command])

        if not _begin_rows("##run-options"):
            return
        _label_cell(_ICON_FLAG, "Pause at")
        pausing = UNTIL_CHOICES[self._until][1] is not None
        imgui.SetNextItemWidth(
            imgui.GetContentRegionAvail().x / 2 if pausing else _FILL
        )
        changed, self._until = imgui.Combo(
            "##until", self._until, [label for label, _, _ in UNTIL_CHOICES]
        )
        _, word, hint = UNTIL_CHOICES[self._until]
        if word is not None:
            imgui.SameLine()
            if changed:
                # a place to pause was just picked, so its field is ready to type in
                imgui.SetKeyboardFocusHere()
            imgui.SetNextItemWidth(_FILL)
            self._until_value = imgui.InputTextWithHint(
                "##until-value",
                hint,
                self._until_value,
                int(imgui.InputTextFlags.CharsDecimal),
            )[1]
        _label_cell(_ICON_STEP, "Step by")
        imgui.SetNextItemWidth(_FILL)
        self._step_count = imgui.InputText(
            "##step-count",
            self._step_count,
            int(imgui.InputTextFlags.CharsDecimal),
        )[1]
        imgui.EndTable()

    def _build_speed_gui(self, speed: float) -> None:
        imgui.SeparatorText(f"{_ICON_TACHOMETER}  Speed")
        columns, width = _button_grid([label for label, _ in SPEED_PRESETS])
        for i, (label, preset) in enumerate(SPEED_PRESETS):
            if i % columns:
                imgui.SameLine()
            chosen = speed == preset
            if chosen:
                imgui.PushStyleColor(int(imgui.Col.Button), _vec4(ACCENT))
                imgui.PushStyleColor(int(imgui.Col.ButtonHovered), _vec4(LINK))
                imgui.PushStyleColor(int(imgui.Col.ButtonActive), _vec4(LINK))
                imgui.PushStyleColor(int(imgui.Col.Text), _vec4(ON_ACCENT))
            clicked = imgui.Button(label, imgui.Vec2(width, 0))
            if chosen:
                imgui.PopStyleColor(4)
            elif clicked:
                self._send(f"speed {preset:g}")
            if math.isinf(preset):
                imgui.SetItemTooltip("As fast as the machine goes")

    def _build_settings_gui(self, status: ControllerStatus) -> None:
        imgui.SeparatorText(f"{_ICON_COG}  Settings")
        idle = status.state is RunState.IDLE
        imgui.BeginDisabled(not idle)
        if _begin_rows("##settings"):
            _label_cell(_ICON_RANDOM, "Seed")
            seed = self._setting_field(
                "seed", "" if status.seed is None else str(status.seed), hint="none"
            )
            if seed is not None and (command := seed_command(seed)) is not None:
                self._send(command)
            _label_cell(_ICON_HASHTAG, "Trial")
            trial = self._setting_field("trial", str(status.trial_num))
            if trial is not None and (command := trial_command(trial)) is not None:
                self._send(command)
            _label_cell(_ICON_EYE, "Watch")
            self._toggle("watch", status.watch, "Reload when a *.py file changes")
            _label_cell(_ICON_VIDEO, "Record")
            self._toggle("record", status.record, "Record telemetry and video")
            imgui.EndTable()
        imgui.EndDisabled()
        if not idle:
            imgui.TextDisabled("These change between runs.")

    def _setting_field(self, name: str, shown: str, hint: str = "") -> str | None:
        """
        Draws the text field of the setting `name`, which shows `shown`, and returns what was typed once the user leaves the field after changing it (with Enter, Tab or a click elsewhere), or `None` before then.

        While the field is being typed in it keeps what is typed, not what the session says.
        """
        imgui.SetNextItemWidth(_FILL)
        text = imgui.InputTextWithHint(
            f"##{name}",
            hint,
            self._drafts.get(name, shown),
            int(imgui.InputTextFlags.CharsDecimal),
        )[1]
        if imgui.IsItemActive():
            self._drafts[name] = text
            return None
        self._drafts.pop(name, None)
        return text if imgui.IsItemDeactivatedAfterEdit() else None

    def _toggle(self, command: str, on: bool, tooltip: str) -> None:
        """A checkbox for a setting the terminal turns on and off by typing `command`."""
        if imgui.Checkbox(f"{'on' if on else 'off'}###{command}", on)[0]:
            self._send(command)
        imgui.SetItemTooltip(tooltip)

    def _build_session_gui(self, latest: MojoStatusSnapshot) -> None:
        imgui.SeparatorText(f"{_ICON_INFO}  Session")
        if not _begin_rows("##session"):
            return
        for row in latest.rows:
            _label_cell(row.icon, row.label)
            if row.color is not None:
                imgui.PushStyleColor(int(imgui.Col.Text), _vec4(row.color))
            imgui.TextWrapped(row.value)
            if row.color is not None:
                imgui.PopStyleColor()
        imgui.EndTable()

    def _send(self, text: str) -> None:
        self.viewer.send_to_sim(MojoCommandEvent(text))


@dataclasses.dataclass(frozen=True, eq=False)
class MojoOverlaySnapshot(messages.Snapshot):
    """The arrows and lines Mojo's runtime wants drawn over the model, on their way from the simulation thread to the viewer."""

    arrows: tuple[ArrowConfig, ...] = ()
    lines: tuple[LineConfig, ...] = ()


class MojoOverlay(plugin.ViewerPlugin):
    """Draws Mojo's force arrows, lines, and traces. The viewer thread owns the viewer's extra geoms, so they are made here, from the latest `MojoOverlaySnapshot`."""

    def __init__(self) -> None:
        self._latest = MojoOverlaySnapshot()
        self._drawn: MojoOverlaySnapshot | None = None
        """What the geoms this plugin put in the viewer were made from."""
        self._geoms: list[mujoco.MjvGeom] = []
        """The geoms this plugin put in the viewer, so it only ever takes out its own."""
        self._warned_full = False

    @messages.handler
    def _on_overlay(self, snapshot: MojoOverlaySnapshot) -> None:
        self._latest = snapshot

    @messages.handler
    def _on_post_model(self, _: messages.PostModelEvent) -> None:
        # the viewer empties its extra geoms when a model is loaded
        self._geoms = []
        self._drawn = None

    @messages.handler
    def _on_update(self, _: messages.UpdateEvent) -> None:
        viewer = self.viewer
        if viewer.model is not None:
            self.refresh(viewer.extra_geoms, viewer.model)

    def refresh(self, extra_geoms: list[mujoco.MjvGeom], model: mujoco.MjModel) -> None:
        """Brings the geoms this plugin put in `extra_geoms` up to date with the latest overlay, leaving any other plugin's geoms where they are. Does nothing when the overlay has not changed since."""
        if self._latest is self._drawn:
            return
        mine = {id(geom) for geom in self._geoms}
        extra_geoms[:] = [g for g in extra_geoms if id(g) not in mine]
        self._geoms = []
        self._drawn = self._latest

        room = max(MAX_OVERLAY_GEOMS - len(extra_geoms), 0)
        wanted = len(self._latest.arrows) + len(self._latest.lines)
        if wanted > room and not self._warned_full:
            self._warned_full = True
            logger.warning(
                f"The viewer can draw {MAX_OVERLAY_GEOMS} extra shapes and {wanted} were asked for, so the oldest trail segments are left out."
            )
        for arrow in self._latest.arrows[:room]:
            geom = mujoco.MjvGeom()
            arrow.fill_geom(geom, model)
            self._geoms.append(geom)
        # lines include the trails of tracers, oldest segment first, so when there is no room for all of
        # them it is the oldest that go and the trail still reaches the current position
        room_for_lines = room - len(self._geoms)
        lines = self._latest.lines
        for line in lines[max(len(lines) - room_for_lines, 0) :]:
            geom = mujoco.MjvGeom()
            line.fill_geom(geom)
            self._geoms.append(geom)
        extra_geoms.extend(self._geoms)
