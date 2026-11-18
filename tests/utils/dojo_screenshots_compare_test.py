"""Tests of how `scripts/gen_dojo_screenshots.py --changed-only` decides which images to replace, since a wrong answer either leaves a stale screenshot in the docs or puts a new commit's worth of noise in git on every push."""

import argparse
import importlib.util
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import ClassVar

import pytest
from PIL import Image

pytest.importorskip("playwright.sync_api")

SCRIPT = Path(__file__).parents[2] / "scripts" / "gen_dojo_screenshots.py"


@pytest.fixture(scope="module")
def shots() -> ModuleType:
    """The script as a module. Importing it runs nothing, only the Playwright import is needed."""
    spec = importlib.util.spec_from_file_location("gen_dojo_screenshots", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def white(path: Path, size: tuple[int, int] = (200, 100)) -> Image.Image:
    """A white image of `size`, saved to `path` and returned so a test can draw on it."""
    image = Image.new("RGB", size, (255, 255, 255))
    image.save(path)
    return image


def block(
    path: Path, side: int, color: tuple[int, int, int], base: Image.Image | None = None
) -> None:
    """Saves to `path` a white image with a square of `side` pixels of `color` in it."""
    image = base if base is not None else Image.new("RGB", (200, 100), (255, 255, 255))
    image.paste(Image.new("RGB", (side, side), color), (10, 10))
    image.save(path)


def test_the_same_image_does_not_differ(shots: ModuleType, tmp_path: Path) -> None:
    white(tmp_path / "a.png")
    white(tmp_path / "b.png")

    assert not shots.differs(tmp_path / "a.png", tmp_path / "b.png")


def test_another_size_differs(shots: ModuleType, tmp_path: Path) -> None:
    white(tmp_path / "a.png", (200, 100))
    white(tmp_path / "b.png", (200, 101))

    assert shots.differs(tmp_path / "a.png", tmp_path / "b.png")


def test_a_few_pixels_are_noise(shots: ModuleType, tmp_path: Path) -> None:
    """A rerun of an unchanged Dojo can draw an edge a hair differently, which must not rewrite the image."""
    white(tmp_path / "a.png")
    block(tmp_path / "b.png", 5, (0, 0, 0))

    assert not shots.differs(tmp_path / "a.png", tmp_path / "b.png")


def test_a_changed_area_is_a_change(shots: ModuleType, tmp_path: Path) -> None:
    """A changed label or a moved element is hundreds of pixels."""
    white(tmp_path / "a.png")
    block(tmp_path / "b.png", 10, (0, 0, 0))

    assert shots.differs(tmp_path / "a.png", tmp_path / "b.png")


def test_a_faint_difference_everywhere_is_noise(
    shots: ModuleType, tmp_path: Path
) -> None:
    """Every pixel a few levels off, as a slightly different encode would leave it, is the same screenshot."""
    white(tmp_path / "a.png")
    Image.new("RGB", (200, 100), (245, 245, 245)).save(tmp_path / "b.png")

    assert not shots.differs(tmp_path / "a.png", tmp_path / "b.png")


def test_a_change_in_one_color_only_is_counted(
    shots: ModuleType, tmp_path: Path
) -> None:
    """White to yellow changes the blue channel alone, which a brightness comparison would see as small."""
    white(tmp_path / "a.png")
    block(tmp_path / "b.png", 10, (255, 255, 0))

    assert shots.differs(tmp_path / "a.png", tmp_path / "b.png")


def test_replace_changed_writes_new_and_changed_images_only(
    shots: ModuleType, tmp_path: Path
) -> None:
    taken, docs = tmp_path / "taken", tmp_path / "docs"
    taken.mkdir()
    docs.mkdir()
    # an image the docs have and that did not change, one that did, and one they do not have yet
    white(taken / "same.jpg")
    white(docs / "same.jpg")
    block(taken / "changed.jpg", 20, (0, 0, 0))
    white(docs / "changed.jpg")
    white(taken / "new.jpg")
    untouched = (docs / "same.jpg").stat().st_mtime_ns

    copied = shots.replace_changed(taken, docs)

    assert copied == ["changed.jpg", "new.jpg"]
    assert (docs / "same.jpg").stat().st_mtime_ns == untouched
    assert (docs / "new.jpg").exists()
    assert (docs / "changed.jpg").read_bytes() == (taken / "changed.jpg").read_bytes()


def test_replace_changed_with_nothing_changed_copies_nothing(
    shots: ModuleType, tmp_path: Path
) -> None:
    taken, docs = tmp_path / "taken", tmp_path / "docs"
    taken.mkdir()
    docs.mkdir()
    white(taken / "a.jpg")
    white(docs / "a.jpg")

    assert shots.replace_changed(taken, docs) == []


def version_pattern(shots: ModuleType) -> re.Pattern[str]:
    """The regular expression the footer script applies to a version, read from the script (the pattern is the same in JavaScript and Python)."""
    found = re.search(r"/(\^v.*?\$)/\.exec", shots.VERSION_SCRIPT)
    assert found is not None
    return re.compile(found.group(1))


@pytest.mark.parametrize(
    ("shown", "stable"),
    [
        ("v2.8.2.dev2+gf354c449a.d20261111", "2.8.2"),
        ("v2.8.2+gf354c449a", "2.8.2"),
        ("v2.8.2-rc1", "2.8.2"),
        ("v12.30.4.dev0", "12.30.4"),
    ],
)
def test_a_development_version_is_shown_as_its_release(
    shots: ModuleType, shown: str, stable: str
) -> None:
    found = version_pattern(shots).match(shown)

    assert found is not None
    assert found.group(1) == stable


@pytest.mark.parametrize("shown", ["v2.8.1", "v2.8.10", "v2.8", "2.8.2.dev2", "vtext"])
def test_a_release_or_other_text_is_left_alone(shots: ModuleType, shown: str) -> None:
    """`v2.8.10` must not be cut to `v2.8.1`."""
    assert version_pattern(shots).match(shown) is None


def box(x: float, y: float, width: float, height: float) -> dict[str, float]:
    return {"x": x, "y": y, "width": width, "height": height}


def test_the_crop_area_holds_every_box_with_padding(shots: ModuleType) -> None:
    """A sidebar button and the panel it opened, side by side."""
    area = shots.crop_area(
        [box(1100, 100, 60, 50), box(800, 120, 288, 400)], (0, 0), (1280, 900)
    )
    pad = shots.CROP_PADDING

    assert area == box(800 - pad, 100 - pad, 1160 - 800 + 2 * pad, 520 - 100 + 2 * pad)


def test_the_crop_area_stays_inside_what_can_be_pictured(shots: ModuleType) -> None:
    """A button at the edge of the page must not ask for pixels that are not there."""
    area = shots.crop_area(
        [box(0, 0, 50, 40), box(1250, 880, 30, 20)], (0, 0), (1280, 900)
    )

    assert area == box(0, 0, 1280, 900)


def test_the_crop_area_moves_by_the_scroll_of_the_window(shots: ModuleType) -> None:
    """A picture of the whole page is cut where the elements are on the page, and the boxes are where they are in the window."""
    area = shots.crop_area([box(100, 50, 200, 100)], (0, 700), (1280, 5000))
    pad = shots.CROP_PADDING

    assert area == box(100 - pad, 700 + 50 - pad, 200 + 2 * pad, 100 + 2 * pad)


def test_partition_deals_every_shot_to_one_group(shots: ModuleType) -> None:
    every = list(shots.SHOTS.values())

    groups = shots.partition(every, 3)

    assert len(groups) == 3
    assert sorted(s.name for g in groups for s in g) == sorted(s.name for s in every)
    assert max(len(g) for g in groups) - min(len(g) for g in groups) <= 1


def test_partition_makes_no_empty_group(shots: ModuleType) -> None:
    two = [shots.SHOTS["share"], shots.SHOTS["polar"]]

    assert [[s.name for s in g] for g in shots.partition(two, 4)] == [
        ["share"],
        ["polar"],
    ]


class FakeWorker:
    """Stands in for a worker process: it records its command line, and reports as the test says."""

    commands: ClassVar[list[list[str]]] = []
    reports: ClassVar[dict[str, tuple[int, list[str] | None]]] = {}
    terminated: ClassVar[int] = 0

    def __init__(self, command: list[str]) -> None:
        self.command = command
        FakeWorker.commands.append(command)

    def wait(self) -> int:
        code, failures = FakeWorker.reports[
            self.command[self.command.index("--only") + 1]
        ]
        if failures is not None:
            report = Path(self.command[self.command.index("--failures-file") + 1])
            report.write_text(json.dumps(failures))
        return code

    def poll(self) -> int:
        return 0

    def terminate(self) -> None:
        FakeWorker.terminated += 1


def test_run_workers_shares_the_shots_and_merges_what_failed(
    shots: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    FakeWorker.commands = []
    FakeWorker.reports = {
        "monitor-view": (1, ["light-share: boom"]),
        "morph": (3, None),
    }
    made: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        shots,
        "cached_job",
        lambda kind, cache, env, *, refresh: made.append((kind, refresh)) or tmp_path,
    )
    monkeypatch.setattr(shots.subprocess, "Popen", FakeWorker)
    args = argparse.Namespace(
        workers=2,
        cache_dir=tmp_path / "cache",
        refresh_jobs=True,
        scale=1.0,
        theme=None,
        headed=False,
    )
    chosen = [shots.SHOTS[n] for n in ("monitor-view", "morph", "share", "polar")]

    failures = shots.run_workers(args, chosen, tmp_path / "images", tmp_path, {})

    # the jobs are made once, here, and the refresh is for these and not for the workers
    assert made == [("monte-carlo", True), ("optimize", True)]
    assert len(FakeWorker.commands) == 2
    for command in FakeWorker.commands:
        assert command[command.index("--workers") + 1] == "1"
        assert "--refresh-jobs" not in command
        assert command[command.index("--out") + 1] == str(tmp_path / "images")
    only = [c[c.index("--only") + 1 : c.index("--out")] for c in FakeWorker.commands]
    assert only == [["monitor-view", "share"], ["morph", "polar"]]
    assert failures == [
        "light-share: boom",
        "worker 1 stopped with exit code 3 before it reported",
    ]


def seeded_plot(shots: ModuleType, name: str) -> dict[str, object] | None:
    """The plot a shot seeds the trial page with, or None for a shot that is not about a trial page."""
    raw = (shots.SHOTS[name].storage or {}).get("mojo_mosaic_config")
    if not raw:
        return None
    plot = json.loads(raw)
    assert isinstance(plot, dict)
    fields: dict[str, object] = {str(key): value for key, value in plot.items()}
    return fields


def test_a_shot_changes_only_the_field_it_is_about(shots: ModuleType) -> None:
    """Every plot is the one plot of the docs, so a note or a shape on it is there only in the shot about notes or shapes."""
    own_field = {
        "notes-editor": {"annotations"},
        "shapes-editor": {"shapes"},
        "polar": {"plotType"},
    }
    checked = 0
    for name in shots.SHOTS:
        plot = seeded_plot(shots, name)
        if plot is None:
            continue
        checked += 1
        changed = {key for key in plot if plot[key] != shots.PLOT[key]}

        assert changed == own_field.get(name, set()), name

    assert checked > 10


def test_the_base_plot_has_no_note_and_no_shape(shots: ModuleType) -> None:
    assert shots.PLOT["annotations"] == []
    assert shots.PLOT["shapes"] == []


def test_the_lab_graph_is_wired_consistently(shots: ModuleType) -> None:
    """LiteGraph loads a link from the node it leaves, the node it enters, and its own list, which must all agree."""
    graph = shots.LAB_GRAPH
    nodes = {node["id"]: node for node in graph["nodes"]}

    for link_id, origin, origin_slot, target, target_slot, kind in graph["links"]:
        leaving = nodes[origin]["outputs"][origin_slot]
        entering = nodes[target]["inputs"][target_slot]
        assert link_id in leaving["links"]
        assert entering["link"] == link_id
        assert kind == leaving["type"] == entering["type"]
    assert graph["last_node_id"] == max(nodes)
    assert graph["last_link_id"] == max(link[0] for link in graph["links"])


def test_the_lab_graph_is_the_docs_example(shots: ModuleType) -> None:
    """The guide builds this lab step by step, so the picture has to be the same three nodes."""
    kinds = [node["type"] for node in shots.LAB_GRAPH["nodes"]]
    scale = next(n for n in shots.LAB_GRAPH["nodes"] if n["type"] == "Arithmetic/scale")
    out = next(n for n in shots.LAB_GRAPH["nodes"] if n["type"] == "Signal/signal_out")

    assert kinds == ["Signal/signal_in", "Arithmetic/scale", "Signal/signal_out"]
    assert scale["properties"]["factor"] == 100
    assert out["properties"]["label"] == "speed_cm_s"


def test_the_lab_storage_opens_the_lab_on_that_graph(shots: ModuleType) -> None:
    storage = shots.lab_storage()
    tabs = json.loads(storage["mojo:lab:tabs"])

    assert storage["mojo:lab:open"] == "1"
    assert len(tabs) == 1
    assert storage["mojo:lab:activeTab"] == tabs[0]["id"]
    assert tabs[0]["name"] == shots.LAB_NAME
    assert tabs[0]["graph"] == shots.LAB_GRAPH
    # no baseline, so the Lab takes the graph as loaded for the clean one and the tab does not show as changed
    assert tabs[0]["savedState"] is None
    assert tabs[0]["dirty"] is False


def test_a_shot_that_fails_once_is_taken_again(
    shots: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The first load of a page can be slow, and one slow load should not cost the picture."""
    tries: list[str] = []

    def flaky(session: object, chosen: object, theme: str) -> None:
        tries.append(theme)
        if len(tries) == 1:
            raise RuntimeError(
                "Page.goto: Timeout 30000ms exceeded.\n    page about:blank"
            )

    monkeypatch.setattr(shots, "take_once", flaky)

    shots.take(object(), shots.SHOTS["share"], "light")

    assert tries == ["light", "light"]
    assert "retrying light-share" in capsys.readouterr().err


def test_a_shot_that_fails_every_time_raises_the_last_error(
    shots: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    tries: list[int] = []

    def broken(session: object, chosen: object, theme: str) -> None:
        tries.append(1)
        raise RuntimeError(f"failed try {len(tries)}")

    monkeypatch.setattr(shots, "take_once", broken)

    with pytest.raises(RuntimeError, match=f"failed try {shots.ATTEMPTS}"):
        shots.take(object(), shots.SHOTS["share"], "dark")

    assert len(tries) == shots.ATTEMPTS


class FakeRequest:
    def __init__(self, url: str, failure: str | None = None) -> None:
        self.url = url
        self.failure = failure


class FakePage:
    url = "http://127.0.0.1:1234/monitor/"

    def __init__(self) -> None:
        self.handlers: dict[str, Callable[..., object]] = {}

    def evaluate(self, script: str) -> str:
        return "loading"

    def on(self, event: str, handler: Callable[..., object]) -> None:
        """Takes a handler as Playwright does, which marks it with an attribute: a method of a built-in type (`set.add`) cannot take one, and every shot failed on that."""
        vars(handler)["_pw_impl_instance_"] = handler
        self.handlers[event] = handler


def test_the_page_log_says_what_the_page_reported(shots: ModuleType) -> None:
    log = shots.PageLog()
    stuck = FakeRequest("http://127.0.0.1:1234/mojo-static/chime.mp3")
    log.waiting.add(stuck)
    log.errors.append("TypeError: x is undefined")
    log.console.append("error: boom")
    log._failed(FakeRequest("http://127.0.0.1:1234/api", "net::ERR_ABORTED"))

    report = log.report(FakePage())

    assert "page http://127.0.0.1:1234/monitor/ (document loading)" in report
    assert "script errors: TypeError: x is undefined" in report
    assert "console: error: boom" in report
    assert "failed requests: http://127.0.0.1:1234/api (net::ERR_ABORTED)" in report
    assert "still waiting for: http://127.0.0.1:1234/mojo-static/chime.mp3" in report


def test_the_page_log_keeps_only_the_first_entries(shots: ModuleType) -> None:
    log = shots.PageLog()
    log.errors.extend(f"error {i}" for i in range(10))

    report = log.report(FakePage(), limit=3)

    assert "script errors: error 2" in report
    assert "script errors: error 3" not in report
    assert "script errors: and 7 more" in report


class FakeMessage:
    def __init__(self, kind: str, text: str) -> None:
        self.type = kind
        self.text = text


def test_the_page_log_listens_the_way_playwright_needs(shots: ModuleType) -> None:
    """Every shot failed once, because a handler that was a method of `set` cannot be marked the way Playwright marks its handlers."""
    page = FakePage()
    log = shots.PageLog()

    log.attach(page)

    request = FakeRequest("http://127.0.0.1:1234/a")
    page.handlers["request"](request)
    assert request in log.waiting
    page.handlers["requestfinished"](request)
    assert request not in log.waiting
    page.handlers["pageerror"](ValueError("bad"))
    assert log.errors == ["bad"]
    page.handlers["console"](FakeMessage("error", "boom"))
    page.handlers["console"](FakeMessage("log", "ignored"))
    assert log.console == ["error: boom"]
    page.handlers["requestfailed"](FakeRequest("http://127.0.0.1:1234/b", "net::ERR"))
    assert log.failed == ["http://127.0.0.1:1234/b (net::ERR)"]


def test_the_fake_page_refuses_what_playwright_refuses(shots: ModuleType) -> None:
    """The check above only means something if the fake fails on a built-in method, as the real page did."""
    page = FakePage()

    with pytest.raises(TypeError):
        page.on("request", set().add)
