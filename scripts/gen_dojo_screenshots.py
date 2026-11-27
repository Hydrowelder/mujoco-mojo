"""
Takes the Dojo screenshots in the docs with Playwright, in the light and the dark theme, so they can be made again whenever the Dojo changes.

It runs `scripts/dojo_screenshots_job.py` to make a Monte Carlo job and an optimization job, starts a Dojo on each with an empty home (so no setting, profile or saved lab of the machine shows), and writes `docs/assets/user-guides/<theme>-<name>.jpg` for each shot. A shot that fails is reported and the rest carry on, so a Dojo that changed under one shot does not stop the others.

The shots are dealt out to several worker processes (`--workers`), each with its own Dojo, home and browser, because the shots are independent and one after another they take minutes.

`--changed-only` takes every shot into a scratch folder and replaces an image in the docs only when it shows something different, so a rerun does not rewrite every image (a Dojo draws the time of each job, and the same page is never quite the same pixels twice). It exits 1 when it replaced any.

The finished jobs are cached (see `--cache-dir`), because they do not depend on the Dojo: changing the Dojo and taking the shots again reuses them. A job runs again when the scripts that define it change, or with `--refresh-jobs`, which is what to do after changing how the library records a run.

The Dojo ships its own sans font (Roboto), so that does not depend on the machine. Its monospace font does (the Dojo asks for the system's), so `FONT_MONO` pins one for the images.

Setup, once (Playwright's browser is not part of the Python package):

    uv sync
    uv run playwright install chromium

Usage:

    python scripts/gen_dojo_screenshots.py                       # every shot, both themes
    python scripts/gen_dojo_screenshots.py --list                # the shots and what each shows
    python scripts/gen_dojo_screenshots.py --only monitor-view plot-editor
    python scripts/gen_dojo_screenshots.py --theme dark
    python scripts/gen_dojo_screenshots.py --scale 2             # twice the pixels, for sharper text
    python scripts/gen_dojo_screenshots.py --workers 1           # one process, to watch a shot with --headed
    python scripts/gen_dojo_screenshots.py --refresh-jobs        # run the jobs again
    python scripts/gen_dojo_screenshots.py --changed-only        # rewrite only the images that changed
    python scripts/gen_dojo_screenshots.py --headed              # watch it work

The docs pages name each image, so a new shot is a function below with the `shot` decorator, and a figure on the page that points at `<theme>-<name>.jpg`. Everything here reads the Dojo's own markup (button titles, headings, element ids), so a shot that stops working after a UI change is fixed by finding the new title or heading.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Protocol

from PIL import Image, ImageChops
from playwright.sync_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    FloatRect,
    Locator,
    Page,
    Request,
    ViewportSize,
    sync_playwright,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from mujoco_mojo.meta import APP_NAME, LAB_DIR, PROFILES_DIR, USER_DIR_VARIABLES
from mujoco_mojo.meta import CACHE_DIR as USER_CACHE_DIR

ROOT = Path(__file__).parents[1]
ASSETS = ROOT / "docs" / "assets" / "user-guides"
JOB_SCRIPT = Path(__file__).parent / "dojo_screenshots_job.py"


class Save(Protocol):
    """What a shot is given to take its picture. It saves a whole page, or one element, as the image of the shot, or the area that holds an element and the others given after it (with `CROP_PADDING` around it). `in_view` takes that area from what the window shows now, which an element fixed to the window (a tooltip) needs, and all of it has to be on screen. Without it the area is taken from the whole page, which can be taller than the window."""

    def __call__(
        self, what: Page | Locator, *also: Locator, in_view: bool = False
    ) -> None: ...


Runner = Callable[[Page, Save], None]
"""A shot: it brings the page to the state to show, then saves it."""

Theme = Literal["light", "dark"]
THEMES: tuple[Theme, ...] = ("light", "dark")
Job = Literal["monte-carlo", "optimize"]

EXAMPLES = ROOT / "src" / "mujoco_mojo" / "examples"

JOB_INPUTS: dict[Job, tuple[Path, ...]] = {
    "monte-carlo": (JOB_SCRIPT, EXAMPLES / "boxes_and_springs" / "simulation.py"),
    "optimize": (
        JOB_SCRIPT,
        EXAMPLES / "boxes_and_springs_optimization" / "simulation.py",
    ),
}
"""The files a job is made from. A cached job is reused only while these are unchanged."""

CACHE_DIR = USER_CACHE_DIR / "dojo-screenshots"
"""Where the finished jobs are kept between runs."""

COMPLETE_MARKER = ".complete"
"""Written beside a cached job once it has finished, so a run that was stopped halfway is never mistaken for one."""

VIEWPORT: ViewportSize = {"width": 1280, "height": 900}
JPEG_QUALITY = 88
STARTUP_SECONDS = 120
JOB_SECONDS = 1200

FONT_MONO = '"Liberation Mono", Cousine, "DejaVu Sans Mono", Menlo, Consolas, monospace'
"""The monospace font of every shot. The Dojo ships its sans font, but for monospace it asks for the system's (Menlo, Consolas and so on), so a machine that has none of them would otherwise show whichever font its settings point at, and the images would differ from machine to machine."""

PAGE_CSS = f"""
:root {{
  --font-mono: {FONT_MONO};
  --default-mono-font-family: {FONT_MONO};
}}
kbd, .number-input {{ font-family: {FONT_MONO}; }}
.js-plotly-plot text {{ font-family: {FONT_MONO} !important; }}
button[title="SensAI"] {{ visibility: hidden !important; }}
"""
"""The style added to every page. The theme's monospace variables are set on the root, `kbd` and the number inputs name a font of their own, and Plotly draws its text in the generic `monospace` family, which only a rule on its text can change. The SensAI button floats in a corner of the window, so it would land inside any tall or whole-page picture; the chat shot shows it again."""

STYLE_SCRIPT = (
    "if (window.top === window) {"
    "document.addEventListener('DOMContentLoaded', () => {"
    "const style = document.createElement('style');"
    f"style.textContent = {json.dumps(PAGE_CSS)};"
    "document.head.appendChild(style);"
    "}); }"
)
"""Adds `PAGE_CSS` to the page before the Dojo draws anything. It skips frames inside the page, so the Optuna Dashboard in the Morph tab keeps its own look."""

PIXEL_TOLERANCE = 32
"""How many levels (of 255) a pixel's color has to change by to count as changed."""

CHANGED_PIXELS = 64
"""How many changed pixels make an image a different one. A rerun of an unchanged Dojo changes a few at most (an edge drawn a hair differently); a changed label or a moved element changes hundreds."""

VERSION_SCRIPT = (
    "if (window.top === window) {"
    "document.addEventListener('DOMContentLoaded', () => {"
    "for (const el of document.querySelectorAll('span')) {"
    "const m = el.children.length === 0 && /^v(\\d+\\.\\d+\\.\\d+)[.+-]\\S+$/.exec(el.textContent.trim());"
    "if (m) el.textContent = 'v' + m[1];"
    "}}); }"
)
"""Shows the footer's version as the release it is heading to (`v2.8.2`, not `v2.8.2.dev2+gf354c449a.d20261111`), so an image does not change with every commit. A release version, with nothing after it, is left as it is, and so is a longer number (`v2.8.10`)."""

CROP_PADDING = 12
"""Pixels added around the area of several elements, so the shadow of a panel and the edge of a button are not cut off."""

CELEBRATED_SCRIPT = (
    "(() => {"
    "const getItem = Storage.prototype.getItem;"
    "Storage.prototype.getItem = function (key) {"
    "return typeof key === 'string' && key.startsWith('mojo_celebrated_') ? '1' : getItem.call(this, key);"
    "};"
    "})();"
)
"""Makes the Monitor think a job's completion was celebrated already (it remembers that under `mojo_celebrated_<start time>`), so a shot does not wait out the confetti and reload. Only the notifications shot, which shows the message the celebration adds, runs without it."""

CHROMIUM_ARGS = ["--font-render-hinting=none"]
"""Turns off font hinting, which headless Chromium on Linux otherwise applies and which can round each glyph's width to whole pixels, so text looks spaced out."""

FROZEN_AFTER_JOB = timedelta(minutes=30)
"""How long after the job finished the browser's clock is frozen for a shot that shows how long ago something happened (the Logs table), so it reads "30m ago" every time and not however long it has been since the cached job was made."""

ATTEMPTS = 2
"""How many times a shot is tried before it counts as failed: a page that is slow to load the first time (a Dojo that has only just started, a browser with several others beside it) is slow once."""

CONFETTI_SECONDS = 6.5
"""How long a finished job's confetti lasts, which a Monitor shot waits out before it reloads the page."""

TRIAL_PLAIN = "trial_00"
"""A trial that succeeded and has the video: the plot, the distributions, the animation and the trial status come from it."""

TRIAL_SAMPLED = "trial_01"
"""A trial that succeeded and has values drawn from the distributions, so the Distributions table shows a draw that is not the nominal one (`trial_00` is the nominal trial, where every draw equals its nominal value)."""

TRIAL_FAILED = "trial_03"
"""A trial that failed its requirement: the trial status shows the failed requirement."""

TRIAL_ERROR = "trial_06"
"""A trial that raised an error halfway through: its log holds the traceback."""


# ----- the server and the browser --------------------------------------------


def clean_environment(home: Path) -> dict[str, str]:
    """The environment a Dojo starts in: an empty home with none of the variables that move the user folders (`USER_DIR_VARIABLES`), no `MUJOCO_MOJO_*` variable of the machine, and the settings the shots need."""
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("MUJOCO_MOJO_") and k not in USER_DIR_VARIABLES
    }
    env.update(
        HOME=str(home),
        USERPROFILE=str(home),
        # the What's Changed window opens over the page on a first launch
        MUJOCO_MOJO_DOJO__SHOW_WHATS_CHANGED="false",
        # the chat button is only drawn when SensAI is on; the chat shots fill the chat themselves, so no model is called
        MUJOCO_MOJO_SENSAI__ENABLED="true",
        MUJOCO_GL=os.environ.get("MUJOCO_GL", "egl"),
    )
    return env


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def make_job(kind: Job, workdir: Path, env: dict[str, str]) -> None:
    """Runs the job that a shot group shows into `workdir`."""
    print(f"running the {kind} job into {workdir} ...", flush=True)
    subprocess.run(
        [sys.executable, str(JOB_SCRIPT), kind, str(workdir)],
        env=env,
        cwd=workdir.parent,
        check=True,
        timeout=JOB_SECONDS,
        stdout=subprocess.DEVNULL,
    )


def job_key(kind: Job) -> str:
    """A short fingerprint of the files `kind` is made from, which changes when any of them does."""
    digest = hashlib.sha256()
    for path in JOB_INPUTS[kind]:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def cached_job(
    kind: Job, cache_dir: Path, env: dict[str, str], *, refresh: bool
) -> Path:
    """The finished `kind` job in the cache, made first if there is none for the current files (or `refresh`). The Dojo only reads a job, so one cached job serves every run."""
    folder = cache_dir / f"{kind}-{job_key(kind)}"
    workdir = folder / f"{kind}-job"
    if (folder / COMPLETE_MARKER).exists() and not refresh:
        print(f"using the cached {kind} job in {workdir}", flush=True)
        return workdir
    # the earlier jobs of this kind are out of date, or were stopped halfway
    for stale in cache_dir.glob(f"{kind}-*"):
        shutil.rmtree(stale, ignore_errors=True)
    folder.mkdir(parents=True)
    make_job(kind, workdir, env)
    (folder / COMPLETE_MARKER).touch()
    return workdir


@contextlib.contextmanager
def serve(workdir: Path, env: dict[str, str]) -> Generator[str]:
    """A Dojo on `workdir`, as its address. It is stopped when the block ends."""
    port = free_port()
    code = "from mujoco_mojo.utils.layers.cli import cli_app; cli_app()"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            code,
            "dojo",
            str(workdir),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=env,
        cwd=workdir.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + STARTUP_SECONDS
        while True:
            if process.poll() is not None:
                raise RuntimeError(
                    f"the Dojo exited with {process.returncode}:\n{process.stderr.read() if process.stderr else ''}"
                )
            try:
                with urllib.request.urlopen(
                    f"{url}/monitor/api/status/job", timeout=2
                ) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, OSError):
                pass
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"the Dojo did not answer within {STARTUP_SECONDS} s"
                )
            time.sleep(0.5)
        yield url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


def seed_storage(values: dict[str, str]) -> str:
    """A script that puts `values` in the browser's storage before the page's own scripts run, leaving a key alone if the page already wrote it."""
    return (
        f"(() => {{ const values = {json.dumps(values)}; for (const [k, v] of Object.entries(values)) "
        "{ try { if (localStorage.getItem(k) === null) localStorage.setItem(k, v); } catch {} } })();"
    )


def new_page(
    browser: Browser,
    theme: Theme,
    storage: dict[str, str] | None = None,
    scale: float = 1,
    now: datetime | None = None,
    celebrates: bool = False,
) -> tuple[BrowserContext, Page]:
    """A page in a fresh browser context in `theme`, so nothing one shot saved reaches the next. `scale` is how many pixels of the image make one pixel of the page, and `now` freezes the page's date and time (its timers keep running). A finished job is celebrated with confetti and a notification the first time a page sees it, unless `celebrates` is false, which is for every shot but the one that shows the notification."""
    context = browser.new_context(
        viewport=VIEWPORT, color_scheme=theme, device_scale_factor=scale
    )
    if now is not None:
        context.clock.set_fixed_time(now)
    context.add_init_script(seed_storage({"theme": theme, **(storage or {})}))
    context.add_init_script(STYLE_SCRIPT)
    if not celebrates:
        context.add_init_script(CELEBRATED_SCRIPT)
    context.add_init_script(VERSION_SCRIPT)
    return context, context.new_page()


def wait_ready(page: Page) -> None:
    """Waits for the Dojo's own loader to leave, which is when the page is drawn."""
    page.wait_for_function(
        "() => window.Alpine && Alpine.store('dojo') && Alpine.store('dojo').isPageReady === true",
        timeout=60_000,
    )
    # every font the page asked for is loaded, so no text is drawn in a fallback and swapped later
    page.evaluate("document.fonts.ready.then(() => true)")
    page.wait_for_timeout(600)


def plot_ready(page: Page) -> None:
    """Waits for the trial page's plot to be drawn."""
    wait_ready(page)
    page.wait_for_selector("#plot-area .main-svg", timeout=60_000)
    page.wait_for_timeout(900)


def popover(page: Page, heading: str) -> Locator:
    """The panel a sidebar button opens (it is moved to the end of the body), found by its heading."""
    return page.locator(
        "body > div.shadow-2xl", has=page.get_by_text(heading, exact=True)
    ).last


def click_sidebar(page: Page, title: str) -> Locator:
    """Presses a button of the plot's sidebar by its tooltip, and returns it, so a picture of the panel it opened can show the button too."""
    button = page.locator(f'button[title="{title}"]').first
    button.click()
    page.wait_for_timeout(500)
    return button


def section(page: Page, heading: str) -> Locator:
    """The block of a trial page under `heading` (Animation, Distributions, Trial Execution or Logs): its divider, its header and what it holds. Each is a `div` with a padding of `pt-6` that holds its own Alpine state, and the innermost one that holds the heading is the block."""
    return page.locator(
        "div.pt-6[x-data]", has=page.get_by_text(heading, exact=True)
    ).last


def reset_saved_state(home: Path) -> None:
    """Deletes what a shot saved on the server, which keeps profiles and labs under the home. Without it the shot of the second theme finds the profile the first one saved, and saving it again asks whether to overwrite it: the dialog, and the blur behind it, is then what the picture shows."""
    # the empty home holds only Mojo's folders, wherever this platform puts them
    for folder in home.rglob(APP_NAME):
        for saved in (PROFILES_DIR, LAB_DIR):
            shutil.rmtree(folder / saved.name, ignore_errors=True)


# ----- what the trial page's plot shows --------------------------------------


KE_SIGNALS = ("Bodies/box1:ke_trans", "Bodies/box1:ke_rot")
"""The two kinetic energy signals of the first box that every plot in the docs shows."""

PLOT_Y_AXES: dict[str, dict[str, object]] = {
    "Bodies/box1:ke_trans": {
        "color": "#00b8db",
        "label": "",
        "width": 3,
        "opacity": 1,
        "filters": [],
        "dash": "solid",
        "marker": "none",
    },
    "Bodies/box1:ke_rot": {
        "color": "#00bc7d",
        "label": "",
        "width": 3,
        "opacity": 1,
        "filters": [],
        "dash": "solid",
        "marker": "none",
    },
}

PLOT: dict[str, object] = {
    "xAxis": {"col": "time", "filters": []},
    "yAxes": PLOT_Y_AXES,
    "refFrame": [None, None],
    "grid": "all",
    "lineMode": "lines+markers",
    "interp": "linear",
    "hover": "closest",
    "title": "Box 1 Energy",
    "xAxisTitle": "",
    "yAxisTitle": "Energy Value",
    "showSpike": True,
    "legendPos": "bottom",
    "rangeX": None,
    "rangeY": None,
    "xScale": "linear",
    "yScale": "linear",
    "xLogBase": None,
    "yLogBase": None,
    "plotType": "cartesian",
    "annotations": [],
    "shapes": [],
    "displayUnitSystem": None,
    "maxPoints": None,
}
"""The plot every trial page in the docs opens with, as the Dojo's own JSON for it. It holds no note, no shape and no filter: a shot changes only the field it is about (`plot_config`), so nothing else is on the plot to distract from it."""

NOTES: list[dict[str, object]] = [
    {"x": 0.6859661552121233, "y": 672.1653013037195, "text": "+Z Spring LOC"},
    {"x": 0.8640013262173208, "y": 816.6442835917725, "text": "-Z Spring LOC"},
]
"""The notes of the Notes Editor shot, the only plot that has any."""

SHAPES: list[dict[str, object]] = [
    {
        "type": "vline",
        "x0": 1.276223278920515,
        "color": "#fe9a00",
        "dash": "solid",
        "label": "vertical line",
    },
    {
        "type": "hline",
        "y0": 695.3969926384658,
        "color": "#ff2056",
        "dash": "dash",
        "label": "horizontal line",
    },
    {
        "type": "rect",
        "x0": 0.9390673156177811,
        "x1": 1.239526031214095,
        "y0": 306.38354739481895,
        "y1": 459.7173141331907,
        "color": "#8e51ff",
        "dash": "dashdot",
        "label": "rectangle",
    },
]
"""The shapes of the Shapes Editor shot, the only plot that has any."""


def plot_config(changes: dict[str, object] | None = None) -> dict[str, str]:
    """The saved plot a trial page opens with: `PLOT`, with `changes` (top-level fields) put over it. A shot passes only what it is about, such as `{"shapes": SHAPES}` for the Shapes Editor."""
    config = copy.deepcopy(PLOT)
    config.update(changes or {})
    return {"mojo_mosaic_config": json.dumps(config), "mojo:media:mini": "0"}


def plot_card(page: Page) -> Locator:
    """The plot's own card: the chart, without the sidebar of buttons beside it."""
    return page.locator("#plot-area").locator("xpath=..")


LAB_NAME = "box1-speed"
"""The name of the lab the Signal Lab shot has open: the docs' example, the speed of `box1` in centimeters per second."""

LAB_GRAPH: dict[str, object] = {
    "last_node_id": 3,
    "last_link_id": 2,
    "nodes": [
        {
            "id": 1,
            "type": "Signal/signal_in",
            "pos": [60, 70],
            "size": [240, 78],
            "flags": {},
            "order": 0,
            "mode": 0,
            "outputs": [
                {"name": "signal", "type": "series", "links": [1], "slot_index": 0}
            ],
            "properties": {"column": "Bodies/box1/xvelp:m"},
            "widgets_values": ["Bodies/box1/xvelp:m", "Browse\u2026"],
        },
        {
            "id": 2,
            "type": "Arithmetic/scale",
            "pos": [380, 70],
            "size": [200, 80],
            "flags": {},
            "order": 1,
            "mode": 0,
            "inputs": [{"name": "signal", "type": "series", "link": 1}],
            "outputs": [
                {"name": "signal", "type": "series", "links": [2], "slot_index": 0}
            ],
            "properties": {"factor": 100, "offset": 0},
            "widgets_values": [100, 0],
        },
        {
            "id": 3,
            "type": "Signal/signal_out",
            "pos": [660, 40],
            "size": [200, 175],
            "flags": {},
            "order": 2,
            "mode": 0,
            "inputs": [{"name": "signal", "type": "series", "link": 2}],
            "properties": {
                "label": "speed_cm_s",
                "unit": "cm/s",
                "dimension": "",
                "quantity": "",
                "transform_type": "",
                "enumeration_map": "",
            },
            "widgets_values": ["speed_cm_s", "cm/s", "", "", "", ""],
        },
    ],
    "links": [[1, 1, 0, 2, 0, "series"], [2, 2, 0, 3, 0, "series"]],
    "groups": [],
    "config": {},
    "extra": {},
    "version": 0.4,
}
"""The graph of that lab, in LiteGraph's own format: Signal In (`Bodies/box1/xvelp:m`, the speed in meters per second), Scale (a factor of 100) and Signal Out (labeled `speed_cm_s`). A tab that holds it is what the Lab opens on."""


def lab_storage() -> dict[str, str]:
    """The browser storage that opens the Signal Lab on `LAB_GRAPH` in a tab named `LAB_NAME`. The tab has no saved baseline, so the Lab takes the graph as it loads it as the clean one and the tab does not show as changed."""
    tab = {
        "id": "screenshot-lab",
        "name": LAB_NAME,
        "graph": LAB_GRAPH,
        "savedState": None,
        "dirty": False,
        "viewport": None,
    }
    return {
        "mojo:lab:open": "1",
        "mojo:lab:tabs": json.dumps([tab]),
        "mojo:lab:activeTab": "screenshot-lab",
    }


# ----- the shots -------------------------------------------------------------


@dataclass(frozen=True)
class Shot:
    name: str
    job: Job
    describe: str
    run: Runner
    storage: dict[str, str] | None = None
    path: str = "/"
    """Where to start, once the Dojo's address is known. `{trial}` names a trial."""
    frozen_clock: bool = False
    """Whether the browser's clock is frozen (see `FROZEN_AFTER_JOB`)."""
    celebrates: bool = False
    """Whether the page is left to celebrate the finished job (see `CELEBRATED_SCRIPT`)."""


SHOTS: dict[str, Shot] = {}


def shot(
    name: str,
    *,
    job: Job = "monte-carlo",
    path: str = "/monitor",
    storage: dict[str, str] | None = None,
    frozen_clock: bool = False,
    celebrates: bool = False,
) -> Callable[[Runner], Runner]:
    """Registers a function as the shot `name`, written to `<theme>-<name>.jpg`. Its docstring says what the shot shows. It is given the page, and a `save` that takes a picture of a page or an element."""

    def register(run: Runner) -> Runner:
        SHOTS[name] = Shot(
            name,
            job,
            (run.__doc__ or "").strip(),
            run,
            storage,
            path,
            frozen_clock,
            celebrates,
        )
        return run

    return register


def monitor_ready(page: Page) -> None:
    """Waits for the Monitor page to be drawn, its timeline chart included."""
    wait_ready(page)
    page.wait_for_selector("#timeline-chart .main-svg", timeout=60_000)
    page.wait_for_timeout(900)


def after_celebration(page: Page) -> None:
    """Lets a finished job's confetti end, then reloads, which does not celebrate it a second time. The reload keeps the notification the celebration added."""
    wait_ready(page)
    page.wait_for_timeout(int(CONFETTI_SECONDS * 1000))
    page.reload()
    monitor_ready(page)


@shot("monitor-view", path="/monitor")
def monitor_view(page: Page, save: Save) -> None:
    """The whole Monitor page for the finished job: progress bar, the six cards, the timeline and the trial lists."""
    monitor_ready(page)
    save(page)


@shot("page-frame", path="/monitor")
def page_frame(page: Page, save: Save) -> None:
    """The header every page shares: the tool tabs, the toolbar, and the job's owner and workdir."""
    monitor_ready(page)
    save(page.locator("header"))


@shot("monitor-timeline", path="/monitor")
def monitor_timeline(page: Page, save: Save) -> None:
    """The Progress Over Time chart: how many trials were pending, running and finished in each stretch of the job."""
    monitor_ready(page)
    save(page.locator("section:has(#timeline-chart)"))


@shot("notifications", path="/monitor", celebrates=True)
def notifications(page: Page, save: Save) -> None:
    """The notification history opened from the bell, holding the message the job's completion added, with the bell that opens it."""
    after_celebration(page)
    bell = page.locator('button[title="Notification history"]')
    bell.click()
    page.wait_for_timeout(500)
    panel = page.locator(
        "div.card.shadow-2xl", has=page.get_by_text("Notifications", exact=True)
    ).last
    save(bell, panel)


@shot("trial-list", path="/mosaic")
def trial_list(page: Page, save: Save) -> None:
    """The Mosaic landing page: a tile for every trial, colored by how it ended."""
    wait_ready(page)
    page.wait_for_selector('a[href^="/mosaic/trial_"]')
    page.wait_for_timeout(500)
    save(page)


@shot(
    "mosaic-view",
    path=f"/mosaic/{TRIAL_PLAIN}",
    storage=plot_config(),
)
def mosaic_view(page: Page, save: Save) -> None:
    """A trial's page: the header with the trial navigation and versus, the signal selectors, and the plot with its sidebar."""
    plot_ready(page)
    save(page)


@shot(
    "selector-bar",
    path=f"/mosaic/{TRIAL_PLAIN}",
    storage=plot_config(),
)
def selector_bar(page: Page, save: Save) -> None:
    """The selector bar with the Y-axes dropdown open, and the signals that were chosen as chips in its ribbon."""
    plot_ready(page)
    ribbon = page.locator(
        "div.card.flex-col", has=page.get_by_text("Y-Axes", exact=True)
    ).last
    # the label is followed by its help icon and then the selector, whose button holds the count of signals
    page.get_by_text("Y-Axes", exact=True).first.locator(
        "xpath=following-sibling::div[2]//button"
    ).first.click()
    menu = ribbon.locator("div.top-full.shadow-2xl:visible").first
    menu.wait_for(state="visible")
    page.wait_for_timeout(700)
    save(ribbon, menu)


@shot("signal-config", path=f"/mosaic/{TRIAL_PLAIN}", storage=plot_config())
def signal_config(page: Page, save: Save) -> None:
    """A signal's own settings (label, width, style and its filter stack) opened from its chip in the ribbon, with the chip."""
    plot_ready(page)
    # the chip's name is the button that opens the signal's settings
    chip = page.locator("button", has_text=KE_SIGNALS[0]).first
    chip.click()
    page.wait_for_timeout(700)
    save(chip, popover(page, KE_SIGNALS[0]))


@shot("versus", path=f"/mosaic/{TRIAL_PLAIN}", storage=plot_config())
def versus(page: Page, save: Save) -> None:
    """Versus mode switched on and applied, so the plot holds the lines of the trials in its range, with the trial header that holds the versus control, its range panel open, and the plot."""
    plot_ready(page)
    control = page.locator(
        'div[class~="sm:w-70"]', has=page.locator("button.toggle")
    ).first
    control.locator("button.toggle").click()
    page.wait_for_timeout(400)
    # no line of another trial is drawn until the range is applied
    control.get_by_role("button", name="Apply").click()
    try:
        page.wait_for_function(
            "() => document.querySelectorAll('#plot-area .scatterlayer .trace').length > 2",
            timeout=30_000,
        )
    except PlaywrightTimeoutError as error:
        lines = page.evaluate(
            "document.querySelectorAll('#plot-area .scatterlayer .trace').length"
        )
        raise RuntimeError(
            f"the plot still holds {lines} line(s) 30 s after Apply, so none of the other trials' lines was drawn"
        ) from error
    page.wait_for_timeout(900)
    control.get_by_text("VS.", exact=False).first.click()
    panel = control.locator("div.panel:visible").first
    panel.wait_for(state="visible")
    page.wait_for_timeout(500)
    # from the trial header (Back to All, the Lab button, the trial selector and the versus control) down, without the page header above it
    trial_header = page.locator(
        "div.pb-4.border-b", has=page.locator('a[href="/mosaic"]')
    ).last
    save(trial_header, panel, plot_card(page))


@shot("plot-editor", path=f"/mosaic/{TRIAL_PLAIN}", storage=plot_config())
def plot_editor(page: Page, save: Save) -> None:
    """The Plot Editor panel with the sidebar button that opens it: gridlines, line mode, interpolation, hover, legend, plot type, point limit, units, scales, ranges and titles."""
    plot_ready(page)
    button = click_sidebar(page, "Edit Plot Configuration")
    save(button, popover(page, "Plot Editor"))


@shot(
    "notes-editor",
    path=f"/mosaic/{TRIAL_PLAIN}",
    storage=plot_config({"annotations": NOTES}),
)
def notes_editor(page: Page, save: Save) -> None:
    """The Notes Editor listing two notes, with the plot that draws them at their coordinates and the sidebar button that opens the editor."""
    plot_ready(page)
    button = click_sidebar(page, "Manage Notes")
    save(plot_card(page), button, popover(page, "Notes Editor"))


@shot(
    "shapes-editor",
    path=f"/mosaic/{TRIAL_PLAIN}",
    storage=plot_config({"shapes": SHAPES}),
)
def shapes_editor(page: Page, save: Save) -> None:
    """The Shapes Editor with the plot's three shapes (a vertical line, a horizontal line and a rectangle) drawn on the plot, and the sidebar button that opens the editor."""
    plot_ready(page)
    button = click_sidebar(page, "Manage Shapes")
    save(plot_card(page), button, popover(page, "Shapes Editor"))


@shot("profiles", path=f"/mosaic/{TRIAL_PLAIN}", storage=plot_config())
def profiles(page: Page, save: Save) -> None:
    """The Saved Profiles panel with one profile saved, in a folder, with the sidebar button that opens it."""
    plot_ready(page)
    button = click_sidebar(page, "Saved Profiles")
    panel = popover(page, "Saved Profiles")
    panel.get_by_placeholder("name or folder/name").fill("springs/kinetic-energy")
    panel.get_by_role("button", name="Save", exact=True).click()
    page.wait_for_timeout(900)
    save(button, panel)


@shot("share", path=f"/mosaic/{TRIAL_PLAIN}", storage=plot_config())
def share(page: Page, save: Save) -> None:
    """The Share panel: copy a link to the current tab, or add a tab from a link, with the sidebar button that opens it."""
    plot_ready(page)
    button = click_sidebar(page, "Share")
    save(button, popover(page, "Share"))


@shot("export-options", path=f"/mosaic/{TRIAL_PLAIN}", storage=plot_config())
def export_options(page: Page, save: Save) -> None:
    """The Export Options panel: the image formats, the filtered CSV, the config JSON, the column manifest and the chat history, with the sidebar button that opens it."""
    plot_ready(page)
    button = click_sidebar(page, "Download Data or Image")
    save(button, popover(page, "Export Options"))


@shot(
    "polar",
    path=f"/mosaic/{TRIAL_PLAIN}",
    storage=plot_config({"plotType": "polar"}),
)
def polar(page: Page, save: Save) -> None:
    """The plot drawn as a polar chart, with the x signal as the angle."""
    plot_ready(page)
    save(page.locator("#plot-area"))


@shot(
    "distributions",
    path=f"/mosaic/{TRIAL_SAMPLED}",
    storage={**plot_config(), "mojo:dists:open": "1"},
)
def distributions(page: Page, save: Save) -> None:
    """The Distributions table of a trial with sampled values, with the tooltip of one parameter's distribution and where this trial's draw falls in it."""
    plot_ready(page)
    panel = section(page, "Distributions")
    page.get_by_text("pz_stiffness", exact=True).first.wait_for()
    # the section at the top of the window, so it and the tooltip under a row are both on screen
    panel.evaluate("el => el.scrollIntoView({ block: 'start' })")
    page.wait_for_timeout(500)
    page.get_by_text("pz_stiffness", exact=True).first.hover()
    tooltip = page.locator("#dist-pdf-tooltip")
    tooltip.wait_for(state="visible")
    page.wait_for_timeout(900)
    save(panel, tooltip, in_view=True)


@shot(
    "animation",
    path=f"/mosaic/{TRIAL_PLAIN}",
    storage={
        **plot_config(),
        "mojo:media:show-line": "1",
        "mojo:media:show-frames": "1",
    },
)
def animation(page: Page, save: Save) -> None:
    """The Animation panel showing the trial's recording at a fixed time, with its playback line and frame markers on the plot above."""
    plot_ready(page)
    panel = section(page, "Animation")
    panel.scroll_into_view_if_needed()
    # the recording is a video once its WebM is ready, which takes a few seconds the first time it is asked for
    page.wait_for_function(
        "() => { const v = document.getElementById('media-video-player'); return !!v && v.offsetParent !== null && v.readyState >= 2; }",
        timeout=90_000,
    )
    # a fixed time, paused, so the picture is the same frame every run
    page.evaluate(
        "() => new Promise((resolve) => { const v = document.getElementById('media-video-player'); v.pause(); v.addEventListener('seeked', () => resolve(true), { once: true }); v.currentTime = 1.0; })"
    )
    page.wait_for_timeout(900)
    plot = page.locator("#plot-area").locator("xpath=..")
    save(plot, panel)


@shot(
    "trial-execution",
    path=f"/mosaic/{TRIAL_FAILED}",
    storage=plot_config(),
)
def trial_execution(page: Page, save: Save) -> None:
    """Trial Execution for a trial that failed a requirement: the time of each step and each requirement's verdict."""
    plot_ready(page)
    panel = section(page, "Trial Execution")
    page.get_by_text("peak_force_in_limits").first.wait_for()
    panel.scroll_into_view_if_needed()
    page.wait_for_timeout(600)
    save(panel)


@shot(
    "trial-logs",
    path=f"/mosaic/{TRIAL_ERROR}",
    storage=plot_config(),
    frozen_clock=True,
)
def trial_logs(page: Page, save: Save) -> None:
    """The Logs table of the trial that raised an error, with the error's entry."""
    plot_ready(page)
    panel = section(page, "Logs")
    page.get_by_text("simulated sensor fault").first.wait_for()
    panel.scroll_into_view_if_needed()
    page.wait_for_timeout(900)
    save(panel)


@shot(
    "signal-lab",
    path=f"/mosaic/{TRIAL_PLAIN}",
    storage={**plot_config(), **lab_storage()},
)
def signal_lab(page: Page, save: Save) -> None:
    """The Signal Lab open on a lab (the speed of `box1` in centimeters per second: Signal In, Scale and Signal Out), with its toolbar and its tab."""
    plot_ready(page)
    page.wait_for_selector("text=Signal Lab", timeout=10_000)
    page.get_by_text(LAB_NAME, exact=True).first.wait_for()
    # the canvas draws the nodes a moment after the overlay opens
    page.wait_for_timeout(1500)
    save(page)


@shot(
    "sensai-chat",
    path=f"/mosaic/{TRIAL_PLAIN}",
    storage={
        **plot_config(),
        "sensai-open": "1",
        "sensai-pinned": "1",
        "sensai-tabs": json.dumps(
            [
                {
                    "id": "tshots",
                    "title": "Which trials failed?",
                    "autoTitled": True,
                    "messages": [
                        {
                            "role": "user",
                            "content": "Which trials failed a requirement, and why?",
                            "ts": 1,
                        },
                        {
                            "role": "assistant",
                            "content": "Trials **3** and **8** failed `peak_force_in_limits` (peak force over the limit). The other ten finished without a failure, and trial 6 errored.",
                            "routed_to": "job_status",
                            "model": "gemini-3.5-flash-lite",
                            "tool_calls": [
                                {
                                    "id": 1,
                                    "name": "ask_job_status_agent",
                                    "agent": "chat",
                                    "args": "request='which trials failed a requirement'",
                                    "status": "ok",
                                    "result": "Trials 3 and 8 failed",
                                },
                                {
                                    "id": 2,
                                    "name": "get_requirement_results",
                                    "agent": "job_status",
                                    "args": "",
                                    "status": "ok",
                                    "result": "peak_force_in_limits: 2 of 12 failed",
                                },
                            ],
                            "ts": 2,
                        },
                    ],
                }
            ]
        ),
        "sensai-active-tab": "tshots",
    },
)
def sensai_chat(page: Page, save: Save) -> None:
    """The SensAI chat window open and pinned, with an answer and the tool calls behind it."""
    plot_ready(page)
    page.wait_for_selector("text=Which trials failed a requirement", timeout=10_000)
    # every other shot hides the button (see `PAGE_CSS`), and here it is part of what is shown
    page.add_style_tag(
        content='button[title="SensAI"] { visibility: visible !important; }'
    )
    page.wait_for_timeout(900)
    save(page)


@shot("settings-panel", path="/monitor")
def settings_panel(page: Page, save: Save) -> None:
    """The settings panel over the page it dims and blurs, on its first section, with the description of the field under the mouse in the bar at the bottom."""
    monitor_ready(page)
    page.locator('button[title="Settings"]').click()
    page.wait_for_selector("text=Global MuJoCo Mojo configuration", timeout=10_000)
    page.get_by_text("Parallel Processes", exact=True).hover()
    page.wait_for_timeout(900)
    save(page)


@shot("morph", job="optimize", path="/morph")
def morph(page: Page, save: Save) -> None:
    """The Morph tab: Optuna Dashboard showing the study of the optimization job."""
    wait_ready(page)
    page.frame_locator("#optuna-iframe").locator("body").wait_for(timeout=60_000)
    page.wait_for_timeout(4000)
    save(page)


# ----- the run ---------------------------------------------------------------


def differs(new: Path, old: Path) -> bool:
    """Whether `new` shows something other than `old`: another size, or more than `CHANGED_PIXELS` pixels that changed by more than `PIXEL_TOLERANCE` levels in any color."""
    with Image.open(new) as a, Image.open(old) as b:
        if a.size != b.size:
            return True
        red, green, blue = ImageChops.difference(
            a.convert("RGB"), b.convert("RGB")
        ).split()
        biggest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        levels = biggest.histogram()
    return sum(levels[PIXEL_TOLERANCE + 1 :]) > CHANGED_PIXELS


def replace_changed(taken: Path, docs: Path) -> list[str]:
    """Copies each image in `taken` into `docs` when `docs` has none by that name or has one that `differs`, and returns the names it copied. An image that did not change is not touched, so git sees nothing."""
    copied: list[str] = []
    for image in sorted(taken.glob("*.jpg")):
        target = docs / image.name
        if not target.exists() or differs(image, target):
            shutil.copyfile(image, target)
            copied.append(image.name)
    return copied


@dataclass
class PageLog:
    """What a page reported while a shot ran: what its console and scripts complained of, the requests that failed, and the ones still waiting for an answer. A shot that fails has nothing else to say why."""

    console: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    waiting: set[Request] = field(default_factory=set)

    def attach(self, page: Page) -> None:
        """Starts listening to `page`."""
        # plain functions: Playwright marks each handler it is given with an attribute, which a method of a built-in type such as `set.add` cannot take
        page.on("console", lambda message: self._console(message))
        page.on("pageerror", lambda error: self.errors.append(str(error)))
        page.on("request", lambda request: self.waiting.add(request))
        page.on("requestfinished", lambda request: self.waiting.discard(request))
        page.on("requestfailed", lambda request: self._failed(request))

    def _console(self, message: ConsoleMessage) -> None:
        if message.type in ("error", "warning"):
            self.console.append(f"{message.type}: {message.text}")

    def _failed(self, request: Request) -> None:
        self.waiting.discard(request)
        self.failed.append(f"{request.url} ({request.failure})")

    def report(self, page: Page, limit: int = 6) -> str:
        """The lines to add to the error of a failed shot, empty when the page reported nothing."""
        try:
            state = str(page.evaluate("document.readyState"))
        except Exception:
            state = "not readable"
        sections = {
            "console": self.console,
            "script errors": self.errors,
            "failed requests": self.failed,
            "still waiting for": [request.url for request in self.waiting],
        }
        lines = [f"page {page.url} (document {state})"]
        for name, entries in sections.items():
            for entry in entries[:limit]:
                lines.append(f"{name}: {entry[:200]}")
            if len(entries) > limit:
                lines.append(f"{name}: and {len(entries) - limit} more")
        return "\n    " + "\n    ".join(lines)


@dataclass(frozen=True)
class Session:
    """What every shot of one job shares: the browser, the Dojo serving the job, and where the images and the Dojo's home are."""

    browser: Browser
    base_url: str
    out: Path
    scale: float
    home: Path
    now: datetime
    """The time a shot with a frozen clock sees (see `FROZEN_AFTER_JOB`)."""


def crop_area(
    boxes: list[FloatRect],
    offset: tuple[float, float],
    limit: tuple[float, float],
) -> FloatRect:
    """The area that holds `boxes`, with `CROP_PADDING` around it. `offset` is added to it (where the window is on the page, for a picture of the whole page, whose areas are on the page and not in the window), and it is kept inside `limit` (the size of what can be pictured), so a button at the edge of the page does not ask for pixels beyond it."""
    left = min(box["x"] for box in boxes) - CROP_PADDING + offset[0]
    top = min(box["y"] for box in boxes) - CROP_PADDING + offset[1]
    right = max(box["x"] + box["width"] for box in boxes) + CROP_PADDING + offset[0]
    bottom = max(box["y"] + box["height"] for box in boxes) + CROP_PADDING + offset[1]
    left, top = max(0.0, left), max(0.0, top)
    right, bottom = min(right, limit[0]), min(bottom, limit[1])
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def box_of(item: Locator) -> FloatRect:
    """Where `item` is in the window, which it has to be on the page to have."""
    box = item.bounding_box()
    if box is None:
        raise RuntimeError(f"{item} is not on the page, so its area cannot be saved")
    return box


def take_once(session: Session, chosen: Shot, theme: Theme) -> None:
    """Takes one shot in one theme and writes its image, closing the browser context afterward. A shot that fails says what the page reported while it ran."""
    target = session.out / f"{theme}-{chosen.name}.jpg"
    reset_saved_state(session.home)
    context, page = new_page(
        session.browser,
        theme,
        chosen.storage,
        session.scale,
        session.now if chosen.frozen_clock else None,
        chosen.celebrates,
    )
    log = PageLog()
    log.attach(page)

    def save(what: Page | Locator, *also: Locator, in_view: bool = False) -> None:
        if isinstance(what, Page):
            what.screenshot(
                path=target,
                type="jpeg",
                quality=JPEG_QUALITY,
                full_page=chosen.name in FULL_PAGE,
            )
            return
        if not also:
            what.screenshot(path=target, type="jpeg", quality=JPEG_QUALITY)
            return
        boxes = [box_of(item) for item in (what, *also)]
        if in_view:
            offset = (0.0, 0.0)
            limit = (float(VIEWPORT["width"]), float(VIEWPORT["height"]))
        else:
            # the boxes are where the elements are in the window now, and the clip of a whole-page picture is on the page
            scroll_x, scroll_y = page.evaluate("[window.scrollX, window.scrollY]")
            width, height = page.evaluate(
                "[document.documentElement.scrollWidth, document.documentElement.scrollHeight]"
            )
            offset = (float(scroll_x), float(scroll_y))
            limit = (float(width), float(height))
        page.screenshot(
            path=target,
            type="jpeg",
            quality=JPEG_QUALITY,
            clip=crop_area(boxes, offset, limit),
            full_page=not in_view,
        )

    try:
        # `commit` is the answer arriving, and every shot then waits for what it needs (the page drawn, a plot, a panel) with a limit of its own, so a page whose load event is slow does not fail a shot that does not need it
        page.goto(session.base_url + chosen.path, wait_until="commit")
        chosen.run(page, save)
        if not target.exists():
            raise RuntimeError("the shot ran but saved nothing")
    except Exception as error:
        raise RuntimeError(f"{error}{log.report(page)}") from error
    finally:
        context.close()


def take(session: Session, chosen: Shot, theme: Theme) -> None:
    """Takes one shot in one theme, again if it fails (see `ATTEMPTS`), and raises what the last try reported if it fails every time."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            take_once(session, chosen, theme)
            return
        except Exception as error:
            if attempt == ATTEMPTS:
                raise
            reason = str(error).strip().splitlines()[0] if str(error).strip() else ""
            print(
                f"retrying {theme}-{chosen.name} (try {attempt} failed: {reason})",
                file=sys.stderr,
                flush=True,
            )


FULL_PAGE = {"monitor-view", "trial-list"}
"""The shots of a whole page, long enough to scroll. The rest are the window as it is."""


def default_workers() -> int:
    """How many worker processes to use when not told: half the processors, at most four, since each worker is a Dojo and a browser."""
    return max(1, min(4, (os.cpu_count() or 2) // 2))


def partition(shots: list[Shot], parts: int) -> list[list[Shot]]:
    """`shots` dealt out to at most `parts` groups in turn, none of them empty. A shot goes to one group with both of its themes, so one Dojo and one home take its two pictures one after the other: the profiles shot saves a profile on the server, and two of them at once would find each other's."""
    return [group for group in (shots[i::parts] for i in range(parts)) if group]


def shoot(
    args: argparse.Namespace,
    chosen_shots: list[Shot],
    themes: tuple[Theme, ...],
    taken: Path,
    scratch: Path,
    env: dict[str, str],
) -> list[str]:
    """Takes `chosen_shots` in this process: a browser, and a Dojo for each job they show. Returns what failed."""
    failures: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=not args.headed, args=CHROMIUM_ARGS
        )
        for job in ("monte-carlo", "optimize"):
            group = [s for s in chosen_shots if s.job == job]
            if not group:
                continue
            workdir = cached_job(job, args.cache_dir, env, refresh=args.refresh_jobs)
            finished = datetime.fromtimestamp(
                (workdir.parent / COMPLETE_MARKER).stat().st_mtime
            )
            with serve(workdir, env) as base_url:
                session = Session(
                    browser,
                    base_url,
                    taken,
                    args.scale,
                    scratch / "home",
                    finished + FROZEN_AFTER_JOB,
                )
                for chosen in group:
                    for theme in themes:
                        try:
                            take(session, chosen, theme)
                            print(f"wrote {theme}-{chosen.name}.jpg", flush=True)
                        except Exception as error:
                            failures.append(f"{theme}-{chosen.name}: {error}")
                            print(
                                f"FAILED {theme}-{chosen.name}: {error}",
                                file=sys.stderr,
                                flush=True,
                            )
        browser.close()
    return failures


def run_workers(
    args: argparse.Namespace,
    chosen_shots: list[Shot],
    taken: Path,
    scratch: Path,
    env: dict[str, str],
) -> list[str]:
    """Takes `chosen_shots` in `args.workers` processes of this script at once, each on its own share of them, and returns what failed. The jobs are made here first, since two workers making one at the same time would trip over each other."""
    for job in ("monte-carlo", "optimize"):
        if any(s.job == job for s in chosen_shots):
            cached_job(job, args.cache_dir, env, refresh=args.refresh_jobs)
    workers: list[tuple[int, Path, subprocess.Popen[bytes]]] = []
    try:
        for index, group in enumerate(partition(chosen_shots, args.workers)):
            report = scratch / f"failures-{index}.json"
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--workers",
                "1",
                "--only",
                *[s.name for s in group],
                "--out",
                str(taken),
                "--scale",
                str(args.scale),
                "--cache-dir",
                str(args.cache_dir),
                "--failures-file",
                str(report),
            ]
            if args.theme:
                command += ["--theme", args.theme]
            if args.headed:
                command.append("--headed")
            workers.append((index, report, subprocess.Popen(command)))
        failures: list[str] = []
        for index, report, process in workers:
            code = process.wait()
            if report.exists():
                failures += json.loads(report.read_text())
            elif code != 0:
                failures.append(
                    f"worker {index} stopped with exit code {code} before it reported"
                )
        return failures
    finally:
        # a stopped run (Ctrl+C reaches the workers too) leaves none of them behind
        for _, _, process in workers:
            if process.poll() is None:
                process.terminate()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Take the Dojo screenshots for the docs."
    )
    parser.add_argument("--list", action="store_true", help="print the shots and exit")
    parser.add_argument(
        "--only", nargs="+", metavar="NAME", help="take only these shots"
    )
    parser.add_argument("--theme", choices=THEMES, help="take one theme only")
    parser.add_argument(
        "--out", type=Path, default=ASSETS, help="where to write the images"
    )
    parser.add_argument("--headed", action="store_true", help="show the browser")
    parser.add_argument(
        "--scale",
        type=float,
        default=1,
        help="pixels of the image per pixel of the page; 2 is sharper and makes images about three times larger",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=default_workers(),
        help="processes to take the shots in at once, each with its own Dojo and browser (default: half the processors, at most 4)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=CACHE_DIR,
        help="where the finished jobs are kept between runs",
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="replace an image only when it shows something different, and exit 1 when any was replaced",
    )
    parser.add_argument(
        "--refresh-jobs",
        action="store_true",
        help="run the jobs again instead of using the cached ones",
    )
    parser.add_argument(
        "--failures-file",
        type=Path,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    if args.list:
        for name, chosen in SHOTS.items():
            print(f"{name:20} {chosen.job:12} {chosen.describe}")
        return 0

    unknown = sorted(set(args.only or []) - SHOTS.keys())
    if unknown:
        parser.error(f"unknown shot(s): {', '.join(unknown)} (see --list)")
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    chosen_shots = [SHOTS[n] for n in (args.only or SHOTS)]
    themes: tuple[Theme, ...] = (args.theme,) if args.theme else THEMES
    args.out.mkdir(parents=True, exist_ok=True)

    # the home holds nothing but what the Dojo saves while serving, so it is made fresh every run
    scratch = Path(tempfile.mkdtemp(prefix="dojo-shots-"))
    env = clean_environment(scratch / "home")
    (scratch / "home").mkdir()
    # with --changed-only every shot is taken into the scratch folder first, and only the ones that changed reach the docs
    taken = scratch / "images" if args.changed_only else args.out
    taken.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    replaced: list[str] = []
    try:
        if args.workers > 1 and len(chosen_shots) > 1:
            failures = run_workers(args, chosen_shots, taken, scratch, env)
        else:
            failures = shoot(args, chosen_shots, themes, taken, scratch, env)
        if args.failures_file:
            args.failures_file.write_text(json.dumps(failures))
        if args.changed_only:
            replaced = replace_changed(taken, args.out)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        print(f"\n{len(failures)} shot(s) failed:", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
    if replaced:
        print(f"\n{len(replaced)} image(s) changed and were replaced:", file=sys.stderr)
        for name in replaced:
            print(f"  {name}", file=sys.stderr)
        print("commit them and push again", file=sys.stderr)
    elif args.changed_only and not failures:
        print("no screenshot changed")
    return 1 if failures or replaced else 0


if __name__ == "__main__":
    raise SystemExit(main())
