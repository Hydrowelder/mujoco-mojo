import sys
from pathlib import Path

import pytest
import typer

from mujoco_mojo.utils.layers.cli import _load_func


@pytest.fixture
def add_to_sys_path(tmp_path: Path):
    sys.path.insert(0, str(tmp_path))
    yield tmp_path
    sys.path.remove(str(tmp_path))


def _write_module(tmp_path: Path, name: str, source: str) -> None:
    (tmp_path / f"{name}.py").write_text(source)
    sys.modules.pop(name, None)


def test_load_func_resolves_module_function(add_to_sys_path: Path) -> None:
    _write_module(
        add_to_sys_path,
        "load_func_plain_mod",
        "def my_func():\n    return 'ok'\n",
    )

    func = _load_func("load_func_plain_mod.my_func")

    assert func() == "ok"


def test_load_func_resolves_class_method(add_to_sys_path: Path) -> None:
    _write_module(
        add_to_sys_path,
        "load_func_class_mod",
        "class MyClass:\n    def my_method(self):\n        return 'method'\n",
    )

    func = _load_func("load_func_class_mod.MyClass.my_method")

    assert func.__name__ == "my_method"


def test_load_func_return_module(add_to_sys_path: Path) -> None:
    _write_module(
        add_to_sys_path,
        "load_func_return_mod",
        "def my_func():\n    return 'ok'\n",
    )

    func, mod = _load_func("load_func_return_mod.my_func", True)

    assert func() == "ok"
    assert mod.__name__ == "load_func_return_mod"


def test_load_func_unknown_module_reports_not_found(
    add_to_sys_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(typer.Exit):
        _load_func("totally.nonexistent.module.func")

    captured = capsys.readouterr()
    assert "Could not find module" in captured.out


def test_load_func_unknown_attribute_reports_attribute_error(
    add_to_sys_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_module(add_to_sys_path, "load_func_attr_mod", "x = 1\n")

    with pytest.raises(typer.Exit):
        _load_func("load_func_attr_mod.does_not_exist")

    captured = capsys.readouterr()
    assert "not found" in captured.out


def test_load_func_non_callable_reports_error(
    add_to_sys_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_module(add_to_sys_path, "load_func_noncallable_mod", "NOT_CALLABLE = 42\n")

    with pytest.raises(typer.Exit):
        _load_func("load_func_noncallable_mod.NOT_CALLABLE")

    captured = capsys.readouterr()
    assert "resolved to a" in captured.out
    assert "int" in captured.out


def test_load_func_syntax_error_surfaces_real_error(
    add_to_sys_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_module(add_to_sys_path, "load_func_syntax_error_mod", "def f(:\n    pass\n")

    with pytest.raises(typer.Exit):
        _load_func("load_func_syntax_error_mod.f")

    captured = capsys.readouterr()
    out = " ".join(captured.out.split())
    assert "Failed to import module" in out
    assert "invalid syntax" in out


def test_load_func_internal_import_error_surfaces_real_error(
    add_to_sys_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_module(
        add_to_sys_path,
        "load_func_bad_import_mod",
        "import totally_fake_dependency_xyz\n\n\ndef f():\n    return totally_fake_dependency_xyz\n",
    )

    with pytest.raises(typer.Exit):
        _load_func("load_func_bad_import_mod.f")

    captured = capsys.readouterr()
    assert "Failed to import module" in captured.out
    assert "totally_fake_dependency_xyz" in captured.out
