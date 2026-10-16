import contextlib
import os
import warnings
from pathlib import Path

import mujoco
import numpy as np
import pytest
from PIL import Image

from mujoco_mojo.mjcf import (
    Asset,
    Body,
    Compiler,
    GeomMesh,
    GeomSphere,
    Joint,
    Mesh,
    Mujoco,
    WorldBody,
)
from mujoco_mojo.mjcf.dependency_path import DepPath, collect_asset_slots, copy_asset
from mujoco_mojo.mjcf.mujoco_attr.asset_attr.hfield import HField
from mujoco_mojo.mjcf.mujoco_attr.asset_attr.model import Model
from mujoco_mojo.mjcf.mujoco_attr.asset_attr.texture import Texture
from mujoco_mojo.mjcf.mujoco_attr.body_attr.flexcomp import FlexComp
from mujoco_mojo.mjcf.mujoco_attr.deformable_attr.skin import DeformableSkin
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import (
    BodyName,
    FlexCompType,
    JointName,
    JointType,
    MeshName,
    TextureName,
    TextureType,
)

requires_posix = pytest.mark.skipif(
    os.name != "posix", reason="unprivileged symlink creation requires POSIX"
)


def test_copy_asset_ignores_prefer_symlinks_on_non_posix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """prefer_symlinks is silently ignored off POSIX; a normal copy is made instead."""
    monkeypatch.setattr("mujoco_mojo.mjcf.dependency_path.os.name", "nt")
    # os.name is a single process-wide attribute, so patching it also fools
    # filelock's own platform check when it builds its lock path - on Python
    # 3.13+, pathlib refuses to instantiate a WindowsPath while actually
    # running on POSIX, which crashes FileLock.acquire() before copy_asset's
    # own prefer_symlinks branch (the thing this test cares about) is even
    # reached. copy_asset's lock is an implementation detail unrelated to
    # that branch, so it's stubbed out here rather than genuinely exercised.
    monkeypatch.setattr(
        "mujoco_mojo.mjcf.dependency_path.FileLock",
        lambda *_args, **_kwargs: contextlib.nullcontext(),
    )

    source = tmp_path / "source.txt"
    source.write_text("hello")
    dest = tmp_path / "bundle" / "source.txt"

    copy_asset(source, dest, prefer_symlinks=True)

    assert dest.exists()
    assert not dest.is_symlink()
    assert dest.read_text() == "hello"


@requires_posix
def test_copy_asset_creates_symlink_when_prefer_symlinks_and_posix(
    tmp_path: Path,
) -> None:
    """On POSIX, prefer_symlinks links to the source instead of copying its bytes."""
    source = tmp_path / "source.txt"
    source.write_text("hello")
    dest = tmp_path / "bundle" / "source.txt"

    copy_asset(source, dest, prefer_symlinks=True)

    assert dest.is_symlink()
    assert dest.resolve() == source.resolve()


@requires_posix
def test_copy_asset_relinks_when_symlink_target_changes(tmp_path: Path) -> None:
    """A symlink already at dest pointing elsewhere is replaced, not left stale."""
    old_source = tmp_path / "old.txt"
    old_source.write_text("old")
    new_source = tmp_path / "new.txt"
    new_source.write_text("new")
    dest = tmp_path / "bundle" / "asset.txt"

    copy_asset(old_source, dest, prefer_symlinks=True)
    copy_asset(new_source, dest, prefer_symlinks=True)

    assert dest.is_symlink()
    assert dest.resolve() == new_source.resolve()


@requires_posix
def test_copy_asset_replaces_real_file_with_symlink(tmp_path: Path) -> None:
    """A real, non-symlinked file already at dest (e.g. from a copy-mode bundle) is replaced with a symlink."""
    source = tmp_path / "source.txt"
    source.write_text("hello")
    dest = tmp_path / "bundle" / "source.txt"
    dest.parent.mkdir(parents=True)
    dest.write_text("stale copy")

    copy_asset(source, dest, prefer_symlinks=True)

    assert dest.is_symlink()
    assert dest.resolve() == source.resolve()


# --- compiler directories (meshdir, texturedir, assetdir, strippath) ---

TETRAHEDRON = "v 0 0 0\nv 1 0 0\nv 0 1 0\nv 0 0 1\nf 1 3 2\nf 1 2 4\nf 1 4 3\nf 2 3 4\n"


class _Project:
    """A project directory (the working directory) next to a workdir with a trial folder, laid out like a real run."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.project = root / "project"
        self.trial = root / "workdir" / "trial_0"
        self.shared = root / "workdir" / "assets"
        self.project.mkdir()
        self.trial.mkdir(parents=True)

    def add(self, relative: str, content: str | bytes = TETRAHEDRON) -> Path:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            path.write_text(content)
        else:
            path.write_bytes(content)
        return path

    def bundle(self, model: Mujoco) -> bool:
        rel_to_xml = Path(os.path.relpath(self.shared, self.trial))
        return model.bundle_assets(target_dir=self.shared, rel_to_xml=rel_to_xml)

    def compile(self, model: Mujoco) -> mujoco.MjModel:
        """Compiles the XML that would be written for the trial, from the trial folder, as the runner does."""
        xml = self.trial / "model.xml"
        model.write_xml(xml)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return mujoco.MjModel.from_xml_path(str(xml))


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Project:
    monkeypatch.setattr(
        "mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", tmp_path / "no-global.toml"
    )
    layout = _Project(tmp_path)
    monkeypatch.chdir(layout.project)
    return layout


def _mesh_model(file: Path, compiler: Compiler | None = None) -> Mujoco:
    """A model whose only mesh is `file`, with the given compiler element if any."""
    body = Body(name=BodyName("b"))
    body.geoms.append(GeomMesh(mesh=MeshName("m")))
    worldbody = WorldBody()
    worldbody.bodies.append(body)
    return Mujoco(
        compilers=[compiler] if compiler is not None else [],
        assets=[Asset(meshes=[Mesh(name=MeshName("m"), file=DepPath(file))])],
        worldbody=worldbody,
    )


def test_a_mesh_file_is_found_through_meshdir(project: _Project) -> None:
    """`file` is relative to `meshdir`, as it is for MuJoCo, and the bundled file needs no directory afterwards."""
    project.add("meshes/cube.obj")
    model = _mesh_model(Path("cube.obj"), Compiler(meshdir=Path("meshes")))

    assert project.bundle(model) is True

    assert (project.shared / "cube.obj").is_file()
    assert project.compile(model).nmeshvert == 4


def test_the_compiler_directories_are_removed_once_assets_are_bundled(
    project: _Project,
) -> None:
    """They would otherwise be put in front of the explicit paths the bundle is written with."""
    project.add("meshes/cube.obj")
    compiler = Compiler(
        meshdir=Path("meshes"),
        texturedir=Path("tex"),
        assetdir=Path("both"),
        strippath=True,
    )
    model = _mesh_model(Path("cube.obj"), compiler)

    project.bundle(model)

    assert compiler.meshdir is None
    assert compiler.texturedir is None
    assert compiler.assetdir is None
    assert compiler.strippath is False
    xml = project.trial / "model.xml"
    model.write_xml(xml)
    assert "meshdir" not in xml.read_text()


@pytest.mark.parametrize("directory_type", [Path, DepPath])
def test_a_directory_is_never_bundled_as_if_it_were_a_file(
    project: _Project, directory_type: type[Path]
) -> None:
    """A `DepPath` for a compiler directory used to crash bundling with `IsADirectoryError`."""
    project.add("meshes/cube.obj")
    compiler = Compiler(meshdir=directory_type("meshes"))
    model = _mesh_model(Path("cube.obj"), compiler)

    assert not isinstance(compiler.meshdir, DepPath)
    assert project.bundle(model) is True
    assert project.compile(model).nmeshvert == 4


def test_the_crawler_skips_a_dependency_that_is_a_directory(tmp_path: Path) -> None:
    class Holder(XMLModel):
        tag = "holder"
        attributes = ("file",)

        file: DepPath | None = None

    assert collect_asset_slots(Holder(file=DepPath(tmp_path))) == []


def test_assetdir_sets_both_directories_and_the_specific_one_wins(
    project: _Project,
) -> None:
    project.add("meshes/cube.obj")

    via_assetdir = _mesh_model(Path("cube.obj"), Compiler(assetdir=Path("meshes")))
    assert project.bundle(via_assetdir) is True
    assert project.compile(via_assetdir).nmeshvert == 4

    # a specific directory beats assetdir, so the wrong assetdir is never consulted
    specific = _mesh_model(
        Path("cube.obj"), Compiler(assetdir=Path("wrong"), meshdir=Path("meshes"))
    )
    assert project.bundle(specific) is True
    assert project.compile(specific).nmeshvert == 4


def test_a_mesh_is_not_looked_for_in_texturedir(project: _Project) -> None:
    project.add("tex/cube.obj")
    model = _mesh_model(Path("cube.obj"), Compiler(texturedir=Path("tex")))

    assert project.bundle(model) is False


def test_a_texture_file_is_found_through_texturedir(project: _Project) -> None:
    image = project.project / "tex" / "red.png"
    image.parent.mkdir()
    Image.new("RGB", (4, 4), (255, 0, 0)).save(image)
    texture = Texture(
        name=TextureName("red"), type=TextureType.D2, file=DepPath("red.png")
    )
    model = Mujoco(
        compilers=[Compiler(texturedir=Path("tex"))],
        assets=[Asset(textures=[texture])],
        worldbody=WorldBody(),
    )

    assert project.bundle(model) is True

    assert (project.shared / "red.png").is_file()
    assert project.compile(model).ntex == 1


def test_a_flexcomp_file_is_found_through_meshdir(project: _Project) -> None:
    project.add("meshes/cube.obj")
    body = Body(name=BodyName("b"))
    body.geoms.append(GeomSphere(size=0.1))
    body.joints.append(
        Joint(name=JointName("j"), type=JointType.SLIDE, axis=np.array((1, 0, 0)))
    )
    body.flexcomps.append(
        FlexComp(name="f", type=FlexCompType.MESH, file=DepPath("cube.obj"), mass=1)
    )
    worldbody = WorldBody()
    worldbody.bodies.append(body)
    model = Mujoco(compilers=[Compiler(meshdir=Path("meshes"))], worldbody=worldbody)

    assert project.bundle(model) is True

    assert project.compile(model).nflex == 1


def test_strippath_looks_up_the_file_name_in_the_directory(project: _Project) -> None:
    """With `strippath` the directories in a file name are dropped before the compiler directory is applied."""
    project.add("meshes/cube.obj")
    model = _mesh_model(
        Path("elsewhere/on/another/machine/cube.obj"),
        Compiler(meshdir=Path("meshes"), strippath=True),
    )

    assert project.bundle(model) is True
    assert project.compile(model).nmeshvert == 4


def test_an_absolute_file_ignores_the_compiler_directory(
    project: _Project, tmp_path: Path
) -> None:
    absolute = tmp_path / "elsewhere" / "cube.obj"
    absolute.parent.mkdir()
    absolute.write_text(TETRAHEDRON)
    model = _mesh_model(absolute, Compiler(meshdir=Path("does-not-exist")))

    assert project.bundle(model) is True
    assert project.compile(model).nmeshvert == 4


def test_an_absolute_compiler_directory_is_used_as_it_is(
    project: _Project, tmp_path: Path
) -> None:
    directory = tmp_path / "elsewhere"
    directory.mkdir()
    (directory / "cube.obj").write_text(TETRAHEDRON)
    model = _mesh_model(Path("cube.obj"), Compiler(meshdir=directory))

    assert project.bundle(model) is True
    assert project.compile(model).nmeshvert == 4


def test_a_file_that_cannot_be_found_leaves_the_compiler_alone(
    project: _Project,
) -> None:
    """Nothing is bundled, so nothing is rewritten and the directories stay as authored."""
    compiler = Compiler(meshdir=Path("meshes"))
    model = _mesh_model(Path("missing.obj"), compiler)

    assert project.bundle(model) is False
    assert compiler.meshdir == Path("meshes")


def test_a_model_without_compiler_directories_bundles_as_before(
    project: _Project,
) -> None:
    project.add("meshes/cube.obj")
    model = _mesh_model(Path("meshes/cube.obj"))

    assert project.bundle(model) is True
    assert project.compile(model).nmeshvert == 4


@pytest.mark.parametrize(
    ("owner", "directory"),
    [
        (Mesh, "meshdir"),
        (HField, "meshdir"),
        (DeformableSkin, "meshdir"),
        (FlexComp, "meshdir"),
        (Texture, "texturedir"),
        (Model, None),
    ],
)
def test_each_asset_owner_names_the_directory_mujoco_uses_for_it(
    owner: type[XMLModel], directory: str | None
) -> None:
    """Checked against MuJoCo 3.16.0: sub-model files ignore the compiler directories, everything else here follows one."""
    assert owner.compiler_asset_dir == directory
