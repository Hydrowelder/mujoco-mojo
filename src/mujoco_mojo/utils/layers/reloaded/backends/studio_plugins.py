import dataclasses
import math
import sys

import mujoco
from mujoco.studio import messages, plugin, sim

from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.visualization import ArrowConfig, LineConfig

from .base import ViewerControls

__all__ = [
    "MAX_OVERLAY_GEOMS",
    "MojoOverlay",
    "MojoOverlaySnapshot",
    "MojoStepControl",
    "mojo_speed",
    "studio_speed",
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
        if event.path:
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
