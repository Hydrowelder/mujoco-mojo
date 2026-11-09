"""Tests for building the documentation site from the source in the package, and for serving it."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import mujoco_mojo.utils.docs_site as docs_site
from mujoco_mojo.meta import DOCS_SOURCE_DIR
from mujoco_mojo.utils.docs_site import (
    OFFLINE_SHIM,
    DocsBuildError,
    build_docs,
    built_versions,
    docs_app_for,
    docs_site_dir,
    github_ref,
    is_built,
    link_missing_assets,
    patch_config,
    require_docs_extra,
)

RAW = "https://raw.githubusercontent.com/Hydrowelder/mujoco-mojo"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `~/.mujoco-mojo` that is not the real one."""
    folder = tmp_path / "mojo-home"
    monkeypatch.setattr(docs_site, "MUJOCO_MOJO_DIR", folder)
    return folder


@pytest.mark.parametrize(
    ("version", "ref"),
    [
        ("2.7.1", "v2.7.1"),
        ("2.7.2.dev36+g38c4dbcb8.d20261108", "master"),
        ("2.7.2.dev1", "master"),
        ("2.7.2+local", "master"),
        ("0.0.0-dev", "master"),
    ],
)
def test_a_release_is_at_its_tag_and_anything_else_is_at_master(
    version: str, ref: str
) -> None:
    assert github_ref(version) == ref


def test_the_site_of_a_version_is_kept_in_the_mojo_folder(home: Path) -> None:
    assert docs_site_dir("2.7.1") == home / "docs" / "v2.7.1"


def test_a_site_is_built_when_it_has_an_index(home: Path) -> None:
    site = docs_site_dir("1.0.0")
    assert not is_built(site)

    site.mkdir(parents=True)
    assert not is_built(site)

    (site / "index.html").write_text("<html></html>")
    assert is_built(site)


def test_built_versions_lists_only_sites_that_are_there(home: Path) -> None:
    assert built_versions() == []

    for name, built in (("v1.0.0", True), ("v2.0.0", True), ("v3.0.0", False)):
        (home / "docs" / name).mkdir(parents=True)
        if built:
            (home / "docs" / name / "index.html").write_text("x")
    (home / "docs" / ".build-v4.0.0-abc").mkdir()
    (home / "docs" / "notes").mkdir()

    assert built_versions() == ["1.0.0", "2.0.0"]


def test_built_versions_are_in_version_order_not_name_order(home: Path) -> None:
    for version in ("2.10.0", "2.7.10", "2.7.9", "2.9.0", "2.7.9.dev1+gabc"):
        (home / "docs" / f"v{version}").mkdir(parents=True)
        (home / "docs" / f"v{version}" / "index.html").write_text("x")

    assert built_versions() == [
        "2.7.9",
        "2.7.9.dev1+gabc",
        "2.7.10",
        "2.9.0",
        "2.10.0",
    ]


def fake_extra(monkeypatch: pytest.MonkeyPatch, *, missing: tuple[str, ...]) -> None:
    """Makes `find_spec` find every module but the ones named."""
    real = importlib.util.find_spec

    def find_spec(name: str, package: str | None = None) -> object | None:
        if name in missing:
            return None
        if name in docs_site.DOCS_EXTRA_MODULES:
            return object()
        return real(name, package)

    monkeypatch.setattr(docs_site.importlib.util, "find_spec", find_spec)


def test_a_missing_docs_extra_is_reported_with_how_to_install_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_extra(monkeypatch, missing=("zensical", "mkdocstrings_handlers"))

    with pytest.raises(ModuleNotFoundError) as caught:
        require_docs_extra()

    message = str(caught.value)
    assert "missing: zensical, mkdocstrings-python)" in message
    assert "pip install mujoco-mojo[docs]" in message
    assert "uv add mujoco-mojo[docs]" in message


def test_it_is_quiet_when_the_docs_extra_is_there(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_extra(monkeypatch, missing=())

    require_docs_extra()


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    """A docs folder with the image `assets/there.svg` in it and no other."""
    folder = tmp_path / "docs"
    (folder / "assets").mkdir(parents=True)
    (folder / "sub").mkdir()
    (folder / "assets" / "there.svg").write_text("<svg/>")
    return folder


def test_an_image_that_is_missing_is_linked_on_github_at_the_ref(docs: Path) -> None:
    page = docs / "index.md"
    page.write_text("![Shot](assets/shot.jpg)\n")

    changed = link_missing_assets(docs, "v2.7.1")

    assert changed == 1
    assert page.read_text() == f"![Shot]({RAW}/v2.7.1/docs/assets/shot.jpg)\n"


def test_what_follows_the_file_name_is_kept(docs: Path) -> None:
    page = docs / "index.md"
    page.write_text(
        "![A](assets/a.jpg#only-light) ![B](assets/b.jpg?raw=1#x)\n"
        '![C](assets/c.jpg "A title"){ width="300" }\n'
    )

    link_missing_assets(docs, "master")

    assert page.read_text() == (
        f"![A]({RAW}/master/docs/assets/a.jpg#only-light) "
        f"![B]({RAW}/master/docs/assets/b.jpg?raw=1#x)\n"
        f'![C]({RAW}/master/docs/assets/c.jpg "A title"){{ width="300" }}\n'
    )


def test_an_html_image_is_linked_too(docs: Path) -> None:
    page = docs / "index.md"
    page.write_text(
        '<img class="x" src="./assets/missing.png#only-dark" alt="A">\n'
        "<img src='assets/other.gif'>\n"
    )

    changed = link_missing_assets(docs, "v1.0.0")

    assert changed == 2
    assert page.read_text() == (
        f'<img class="x" src="{RAW}/v1.0.0/docs/assets/missing.png#only-dark" alt="A">\n'
        f"<img src='{RAW}/v1.0.0/docs/assets/other.gif'>\n"
    )


def test_a_link_is_worked_out_from_the_folder_of_its_page(docs: Path) -> None:
    page = docs / "sub" / "page.md"
    page.write_text("![A](./landed.jpg) ![B](../assets/wide.jpg)\n")

    link_missing_assets(docs, "v1.0.0")

    assert page.read_text() == (
        f"![A]({RAW}/v1.0.0/docs/sub/landed.jpg) ![B]({RAW}/v1.0.0/docs/assets/wide.jpg)\n"
    )


def test_a_link_to_a_file_that_is_there_is_left_alone(docs: Path) -> None:
    """So a build from a checkout, which has the images, changes nothing."""
    page = docs / "index.md"
    text = "![Logo](assets/there.svg#only-dark)\n"
    page.write_text(text)

    assert link_missing_assets(docs, "v1.0.0") == 0
    assert page.read_text() == text


def test_anything_that_is_not_a_missing_relative_file_is_left_alone(
    docs: Path,
) -> None:
    page = docs / "index.md"
    text = (
        "![Badge](https://img.shields.io/badge/x.svg)\n"
        "![Protocol](//example.com/a.png)\n"
        "![Rooted](/assets/a.png)\n"
        "![Mail](mailto:someone@example.com)\n"
        "![Page](other.md)\n"
        "![Folder](assets/)\n"
        "![Outside](../../outside.png)\n"
        "![Anchor](#top)\n"
        "[A link, not an image](assets/missing.jpg)\n"
    )
    page.write_text(text)

    assert link_missing_assets(docs, "v1.0.0") == 0
    assert page.read_text() == text


def test_an_image_in_a_code_block_is_left_alone(docs: Path) -> None:
    page = docs / "index.md"
    page.write_text(
        "```markdown\n![Shot](assets/shot.jpg)\n```\n\n"
        '~~~html\n<img src="assets/shot.jpg">\n~~~\n\n'
        "![Out](assets/out.jpg)\n"
    )

    changed = link_missing_assets(docs, "v1.0.0")

    assert changed == 1
    text = page.read_text()
    assert "```markdown\n![Shot](assets/shot.jpg)\n```" in text
    assert '~~~html\n<img src="assets/shot.jpg">\n~~~' in text
    assert f"![Out]({RAW}/v1.0.0/docs/assets/out.jpg)" in text


CONFIG = """\
site_name: Test
site_url: https://hydrowelder.github.io/mujoco-mojo/
repo_url: https://github.com/Hydrowelder/mujoco-mojo

watch:
  - docs
  - src
  - scripts

nav:
  - Home: index.md

theme:
  features:
    - navigation.tabs
    - navigation.instant
    # - navigation.instant.preview
    - navigation.instant.prefetch
    - navigation.instant.progress
    - content.code.copy

plugins:
  - search
  - api-autonav:
      modules: [src/mujoco_mojo]
  - mkdocstrings:
      handlers:
        python:
          paths: [src]

markdown_extensions:
  - pymdownx.emoji:
      emoji_index: !!python/name:material.extensions.emoji.twemoji

extra:
  generator: false
"""


def test_the_config_is_pointed_at_the_installed_package(tmp_path: Path) -> None:
    config = tmp_path / "mkdocs.yml"
    config.write_text(CONFIG)
    package = tmp_path / "site-packages" / "mujoco_mojo"

    patch_config(config, package)

    text = config.read_text()
    assert f'modules: ["{package.as_posix()}"]' in text
    assert f'paths: ["{package.parent.as_posix()}"]' in text
    assert "src/mujoco_mojo" not in text
    assert "watch:" not in text
    assert "site_url: http://localhost/" in text
    # nothing else is touched, tags included
    assert "!!python/name:material.extensions.emoji.twemoji" in text
    assert "nav:\n  - Home: index.md\n" in text


def test_the_site_is_made_to_work_offline(tmp_path: Path) -> None:
    config = tmp_path / "mkdocs.yml"
    config.write_text(CONFIG)

    patch_config(config, tmp_path / "mujoco_mojo")

    text = config.read_text()
    # the plugin is on, ahead of the others
    assert "plugins:\n  - offline\n  - search\n  - api-autonav:" in text
    # what it cannot work with is gone: every instant navigation feature (a commented one is left as it was) and the repository link
    lines = [x.strip() for x in text.splitlines() if not x.strip().startswith("#")]
    assert not [x for x in lines if x.startswith("- navigation.instant")]
    assert "repo_url" not in text
    # the shim it needs is the local copy, not the one it would fetch from unpkg.com
    assert f"extra:\n  polyfills:\n    - {OFFLINE_SHIM}\n  generator: false" in text
    # the rest of the theme is as it was
    assert "    - navigation.tabs\n" in text
    assert "    - content.code.copy\n" in text


@pytest.mark.parametrize("setting", ["plugins:", "extra:"])
def test_a_config_with_no_plugins_or_extra_to_edit_is_an_error(
    tmp_path: Path, setting: str
) -> None:
    config = tmp_path / "mkdocs.yml"
    config.write_text(CONFIG.replace(f"\n{setting}\n", "\n# gone\n"))

    with pytest.raises(DocsBuildError, match="_make_offline"):
        patch_config(config, tmp_path / "mujoco_mojo")


def test_a_path_with_a_quote_or_backslash_is_still_valid_yaml(tmp_path: Path) -> None:
    config = tmp_path / "mkdocs.yml"
    config.write_text(CONFIG)

    patch_config(config, tmp_path / 'a "b"' / "mujoco_mojo")

    line = next(x for x in config.read_text().splitlines() if "modules:" in x)
    assert json.loads(line.split("modules: ", 1)[1])[0].endswith('a "b"/mujoco_mojo')


@pytest.mark.parametrize("setting", ["modules: [src/mujoco_mojo]", "paths: [src]"])
def test_a_config_that_lost_a_line_it_edits_is_an_error(
    tmp_path: Path, setting: str
) -> None:
    config = tmp_path / "mkdocs.yml"
    config.write_text(CONFIG.replace(setting, "# gone"))

    with pytest.raises(DocsBuildError, match="patch_config"):
        patch_config(config, tmp_path / "mujoco_mojo")


def test_the_config_in_the_bundle_is_one_it_can_edit(tmp_path: Path) -> None:
    """Fails when someone changes those lines of `mkdocs.yml`, rather than at a user's first `docs build`."""
    config = tmp_path / "mkdocs.yml"
    config.write_text((DOCS_SOURCE_DIR / "mkdocs.yml").read_text(encoding="utf-8"))

    patch_config(config, tmp_path / "mujoco_mojo")

    text = config.read_text()
    assert "src/mujoco_mojo" not in text
    assert "paths: [src]" not in text
    assert "\nwatch:" not in text
    assert "plugins:\n  - offline\n" in text
    assert "\n    - navigation.instant" not in text
    assert "\nrepo_url:" not in text


def test_the_shim_the_offline_site_loads_is_in_the_bundle() -> None:
    """Zensical fetches its own from unpkg.com unless `extra.polyfills` names a file with `iframe-worker` in its name."""
    shim = DOCS_SOURCE_DIR / "docs" / OFFLINE_SHIM

    assert "iframe-worker" in shim.name
    assert shim.is_file()
    assert "MIT license" in shim.read_text(encoding="utf-8")


def test_the_online_docs_are_built_as_they_were() -> None:
    """The offline changes are made to the copy the build works in, never to the config the online docs are built from."""
    text = (DOCS_SOURCE_DIR / "mkdocs.yml").read_text(encoding="utf-8")

    assert "\n  - offline" not in text
    assert "\n    - navigation.instant\n" in text
    assert "\nrepo_url: " in text
    assert "polyfills" not in text


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """The smallest bundled source the build copes with: a config with the lines it edits, and a page that has an image that is not there."""
    folder = tmp_path / "bundle"
    (folder / "docs").mkdir(parents=True)
    (folder / "mkdocs.yml").write_text(CONFIG)
    (folder / "docs" / "index.md").write_text("![Shot](assets/shot.jpg)\n")
    return folder


def run_recorder(
    monkeypatch: pytest.MonkeyPatch,
    *,
    returncode: int = 0,
    stderr: str = "",
    make_site: bool = True,
) -> list[dict[str, object]]:
    """Replaces the builder with a function that writes a tiny site where the builder would, and records what it was run with."""
    calls: list[dict[str, object]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        cwd = kwargs["cwd"]
        assert isinstance(cwd, Path)
        calls.append(
            {
                "command": command,
                "cwd": cwd,
                "config": (cwd / "mkdocs.yml").read_text(),
                "page": (cwd / "docs" / "index.md").read_text(),
            }
        )
        if make_site:
            (cwd / "site").mkdir()
            (cwd / "site" / "index.html").write_text("<html>built</html>")
        return subprocess.CompletedProcess(command, returncode, "", stderr)

    monkeypatch.setattr(docs_site.subprocess, "run", run)
    return calls


@pytest.fixture
def extra_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_extra(monkeypatch, missing=())


def leftovers(home: Path) -> list[str]:
    """What is in the docs folder besides built sites."""
    return sorted(p.name for p in (home / "docs").iterdir() if p.name.startswith("."))


@pytest.mark.usefixtures("extra_installed")
def test_the_site_is_built_from_a_prepared_copy_and_put_in_place(
    home: Path, source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = run_recorder(monkeypatch)
    package = tmp_path / "installed" / "mujoco_mojo"

    result = build_docs("2.7.1", source_dir=source, package_dir=package)

    assert result == home / "docs" / "v2.7.1"
    assert (result / "index.html").read_text() == "<html>built</html>"
    (call,) = calls
    command = call["command"]
    assert isinstance(command, list)
    assert command[1:4] == ["-m", "zensical", "build"]
    assert command[-2:] == ["-f", "mkdocs.yml"]
    cwd = call["cwd"]
    assert isinstance(cwd, Path)
    # the copy is beside the result, not in the bundle, and its page and config were prepared
    assert cwd.parent == home / "docs"
    assert cwd != source
    assert f'modules: ["{package.as_posix()}"]' in str(call["config"])
    assert "plugins:\n  - offline\n" in str(call["config"])
    assert f"{RAW}/v2.7.1/docs/assets/shot.jpg" in str(call["page"])
    # the bundle itself was not touched
    assert (source / "docs" / "index.md").read_text() == "![Shot](assets/shot.jpg)\n"
    assert (source / "mkdocs.yml").read_text() == CONFIG


@pytest.mark.usefixtures("extra_installed")
def test_a_development_version_links_its_images_at_master(
    home: Path, source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = run_recorder(monkeypatch)

    build_docs("2.7.2.dev3+gabc", source_dir=source, package_dir=tmp_path)

    assert f"{RAW}/master/docs/assets/shot.jpg" in str(calls[0]["page"])


@pytest.mark.usefixtures("extra_installed")
def test_the_copy_is_removed_once_the_build_is_done(
    home: Path, source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_recorder(monkeypatch)

    build_docs("2.7.1", source_dir=source, package_dir=tmp_path)

    assert leftovers(home) == []


@pytest.mark.usefixtures("extra_installed")
def test_a_site_that_is_built_is_not_built_again(
    home: Path, source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = run_recorder(monkeypatch)
    build_docs("2.7.1", source_dir=source, package_dir=tmp_path)

    again = build_docs("2.7.1", source_dir=source, package_dir=tmp_path)

    assert again == home / "docs" / "v2.7.1"
    assert len(calls) == 1


@pytest.mark.usefixtures("extra_installed")
def test_rebuild_replaces_the_site(
    home: Path, source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = run_recorder(monkeypatch)
    site = build_docs("2.7.1", source_dir=source, package_dir=tmp_path)
    (site / "stale.html").write_text("from the first build")

    build_docs("2.7.1", rebuild=True, source_dir=source, package_dir=tmp_path)

    assert len(calls) == 2
    assert (site / "index.html").is_file()
    assert not (site / "stale.html").exists()
    assert leftovers(home) == []


@pytest.mark.usefixtures("extra_installed")
def test_a_failed_build_says_why_and_leaves_nothing_behind(
    home: Path, source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lines = "\n".join(f"line {n}" for n in range(100))
    run_recorder(monkeypatch, returncode=1, stderr=f"{lines}\nError: it broke")

    with pytest.raises(DocsBuildError) as caught:
        build_docs("2.7.1", source_dir=source, package_dir=tmp_path)

    message = str(caught.value)
    assert "Error: it broke" in message
    # only the end of the output, not all of it
    assert "line 0\n" not in message
    assert not docs_site_dir("2.7.1").exists()
    assert leftovers(home) == []


@pytest.mark.usefixtures("extra_installed")
def test_a_failed_rebuild_keeps_the_site_that_was_there(
    home: Path, source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_recorder(monkeypatch)
    site = build_docs("2.7.1", source_dir=source, package_dir=tmp_path)
    run_recorder(monkeypatch, returncode=1, stderr="broken")

    with pytest.raises(DocsBuildError):
        build_docs("2.7.1", rebuild=True, source_dir=source, package_dir=tmp_path)

    assert (site / "index.html").read_text() == "<html>built</html>"


@pytest.mark.usefixtures("extra_installed")
def test_a_build_that_makes_no_site_is_an_error(
    home: Path, source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_recorder(monkeypatch, make_site=False)

    with pytest.raises(DocsBuildError, match="no site"):
        build_docs("2.7.1", source_dir=source, package_dir=tmp_path)

    assert not docs_site_dir("2.7.1").exists()
    assert leftovers(home) == []


def test_nothing_is_built_without_the_docs_extra(
    home: Path, source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_extra(monkeypatch, missing=("zensical",))
    calls = run_recorder(monkeypatch)

    with pytest.raises(ModuleNotFoundError, match=r"mujoco-mojo\[docs\]"):
        build_docs("2.7.1", source_dir=source, package_dir=tmp_path)

    assert calls == []
    assert not home.exists()


@pytest.fixture
def site(tmp_path: Path) -> Path:
    folder = tmp_path / "site"
    (folder / "guide").mkdir(parents=True)
    (folder / "index.html").write_text("<html>home</html>")
    (folder / "guide" / "index.html").write_text("<html>guide</html>")
    (folder / "404.html").write_text("<html>not here</html>")
    (folder / "search.json").write_text("{}")
    return folder


def test_the_app_serves_the_pages_of_the_site(site: Path) -> None:
    with TestClient(docs_app_for(site)) as client:
        assert client.get("/").text == "<html>home</html>"
        assert client.get("/guide/").text == "<html>guide</html>"
        assert client.get("/search.json").json() == {}


def test_a_folder_without_its_slash_is_sent_to_the_one_with_it(site: Path) -> None:
    with TestClient(docs_app_for(site)) as client:
        response = client.get("/guide", follow_redirects=False)

    assert response.status_code in (301, 302, 307, 308)
    assert response.headers["location"].endswith("/guide/")


def test_a_missing_page_gets_the_404_page_of_the_site(site: Path) -> None:
    with TestClient(docs_app_for(site)) as client:
        response = client.get("/nope/")

    assert response.status_code == 404
    assert response.text == "<html>not here</html>"
