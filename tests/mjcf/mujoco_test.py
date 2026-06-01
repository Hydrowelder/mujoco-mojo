from pathlib import Path

import pytest

from mujoco_mojo.mjcf.mujoco import Mujoco
from mujoco_mojo.mjcf.mujoco_attr.compiler import Compiler
from mujoco_mojo.typing import Angle, EulerSeq


@pytest.fixture
def simple_mujoco() -> Mujoco:
    return Mujoco()


def test_compiler_degree_settings_returns_default(simple_mujoco: Mujoco) -> None:
    """compiler_degree_settings is False (radians) when no Compiler is set."""
    assert simple_mujoco.compiler_degree_settings is Angle.DEGREE


def test_compiler_degree_settings_with_degree_compiler() -> None:
    """compiler_degree_settings is True when a Compiler with angle=degree is set."""
    m = Mujoco(compilers=[Compiler(angle=Angle.RADIAN)])
    assert m.compiler_degree_settings is Angle.RADIAN


def test_compiler_degree_settings_raises_on_conflict() -> None:
    """compiler_degree_settings raises ValueError when compilers disagree on angle."""
    m = Mujoco(compilers=[Compiler(angle=Angle.DEGREE), Compiler(angle=Angle.RADIAN)])
    with pytest.raises(ValueError, match="Inconsistent compiler angle"):
        _ = m.compiler_degree_settings


def test_compiler_eulerseq_settings_with_custom_seq() -> None:
    """compiler_eulerseq_settings reflects the Compiler's eulerseq."""
    m = Mujoco(compilers=[Compiler(eulerseq=EulerSeq.xyz)])
    assert m.compiler_eulerseq_settings == EulerSeq.xyz


def test_compiler_eulerseq_settings_raises_on_conflict() -> None:
    """compiler_eulerseq_settings raises ValueError when compilers disagree on eulerseq."""
    m = Mujoco(
        compilers=[Compiler(eulerseq=EulerSeq.xyz), Compiler(eulerseq=EulerSeq.zyx)]
    )
    with pytest.raises(ValueError, match="Inconsistent compiler eulerseq"):
        _ = m.compiler_eulerseq_settings


def test_write_xml_creates_file(simple_mujoco: Mujoco, tmp_path: Path) -> None:
    """write_xml() creates a file at the given path containing valid XML."""
    out: Path = tmp_path / "model.xml"
    xml: str = simple_mujoco.write_xml(out)

    assert out.exists()
    assert "<mujoco" in xml
    content: str = out.read_text(encoding="utf-8")
    assert "<mujoco" in content


def test_write_xml_returns_pretty_xml(simple_mujoco: Mujoco, tmp_path: Path) -> None:
    """write_xml() returns the same string that was written to disk."""
    out: Path = tmp_path / "model.xml"
    returned: str = simple_mujoco.write_xml(out)
    on_disk: str = out.read_text(encoding="utf-8")
    assert returned == on_disk
