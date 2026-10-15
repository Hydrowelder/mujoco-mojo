import io
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from rich.console import Console
from typer.testing import CliRunner

from mujoco_mojo.settings import (
    MujocoMojoSettings,
    slurm_settings_sources,
)
from mujoco_mojo.utils.layers.cli import _process_kwargs, _smart_parse, cli_app
from mujoco_mojo.utils.runner import MojoRunner, MonteCarloConfig, _print_slurm_extras

# --- CLI value parsing ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("true", True),
        ("True", True),
        (" true ", True),
        ("10", 10),
        ("1.5", 1.5),
        ("None", None),
        ("[1, 2, 3]", [1, 2, 3]),
        ("fast", "fast"),
        # a quoted value is the way to ask for the literal string
        ("'false'", "false"),
    ],
)
def test_smart_parse(raw: str, expected: object) -> None:
    assert _smart_parse(raw) == expected


def test_a_lowercase_false_kwarg_is_falsy() -> None:
    """The bug this guards: `false` used to arrive as the string `'false'`, which is truthy."""
    parsed = _process_kwargs(["use_cache=false", "verbose=true", "mode=fast"])

    assert parsed == {"use_cache": False, "verbose": True, "mode": "fast"}
    assert not parsed["use_cache"]


# --- SLURM memory parsing ---


@pytest.mark.parametrize(
    ("text", "expected_mb"),
    [
        ("1000", 1000),  # a bare number is MB, like SLURM
        ("1G", 1024),
        ("1024M", 1024),
        ("2T", 2 * 1024**2),
        ("2048K", 2),
        ("1.5G", 1536),
        (".5G", 512),
        ("0.5T", 512 * 1024),
        ("125.9G", int(125.9 * 1024)),
        ("1.5GB", 1536),
        ("  4g ", 4096),
        ("", 0),
        ("garbage", 0),
        ("1G extra", 0),
        ("1.2.3G", 0),
    ],
)
def test_normalize_to_mb(text: str, expected_mb: int) -> None:
    assert MojoRunner.normalize_to_mb(text) == expected_mb


def test_a_decimal_limit_is_not_read_as_a_tiny_one() -> None:
    """The bug this guards: `125.9G` was read as 125 MB, so a request for `4G` looked larger than the node limit."""
    assert MojoRunner.normalize_to_mb("4G") < MojoRunner.normalize_to_mb("125.9G")


@pytest.mark.parametrize(
    ("mb", "expected"),
    [
        (1, "1M"),
        (512, "512M"),
        (1024, "1G"),
        (1536, "1.5G"),
        (128922, "125.9G"),
        # rounded down, not to the nearest: 125.879G must not be shown as 125.9G
        (128900, "125.8G"),
        (1024**2, "1T"),
        (1024**2 - 1, "1023.9G"),
    ],
)
def test_format_bytes(mb: int, expected: str) -> None:
    assert MojoRunner.format_bytes(mb) == expected


@pytest.mark.parametrize(
    "mb", [1, 100, 1023, 1024, 1025, 4096, 128900, 128922, 257_500, 1_048_575, 10**7]
)
def test_format_bytes_round_trips_without_overshooting(mb: int) -> None:
    """A limit that is shown and parsed back must never be larger than the real limit, or the default request would be rejected."""
    back = MojoRunner.normalize_to_mb(MojoRunner.format_bytes(mb))

    assert back <= mb
    # at most one decimal place of whichever unit was chosen is lost
    unit_mb = 1 if mb < 1024 else 1024 if mb < 1024**2 else 1024**2
    assert mb - back <= 0.1 * unit_mb + 1


def test_node_memory_limit_is_the_smallest_node_in_the_partition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outputs = iter(
        [
            "PartitionName=compute AllowGroups=ALL Nodes=n[1-2] State=UP",
            "NodeName=n1 RealMemory=257500 CPUTot=32\nNodeName=n2 RealMemory=128922 CPUTot=32",
        ]
    )

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(stdout=next(outputs))

    monkeypatch.setattr(subprocess, "run", fake_run)

    limit = MojoRunner.get_slurm_node_mem_limit("compute")

    assert limit == "125.9G"
    assert MojoRunner.normalize_to_mb(limit) <= 128922


def test_node_memory_limit_accepts_decimal_real_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outputs = iter(["Nodes=n1", "NodeName=n1 RealMemory=1.5G CPUTot=32"])

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(stdout=next(outputs))

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert MojoRunner.get_slurm_node_mem_limit("compute") == "1.5G"


# --- SLURM time parsing ---


@pytest.mark.parametrize(
    ("text", "expected_seconds"),
    [
        ("01:00:00", 3600),
        ("1-00:00:00", 86400),
        ("30", 30 * 60),  # minutes
        ("5:30", 5 * 60 + 30),  # minutes:seconds
        ("1-12", 86400 + 12 * 3600),  # days-hours
        ("1-12:30", 86400 + 12 * 3600 + 30 * 60),  # days-hours:minutes
        ("1-12:30:15", 86400 + 12 * 3600 + 30 * 60 + 15),
        ("UNLIMITED", -1),
        ("unlimited", -1),
        ("INFINITE", -1),
    ],
)
def test_slurm_time_to_seconds(text: str, expected_seconds: int) -> None:
    assert MojoRunner.slurm_time_to_seconds(text) == expected_seconds


# --- trial folder padding ---


def test_padding_defaults_to_the_width_of_n_trial() -> None:
    assert MonteCarloConfig(n_trial=1).padding_style == "01d"
    assert MonteCarloConfig(n_trial=1000).padding_style == "03d"


def test_padding_overrides_the_derived_width() -> None:
    """A SLURM worker only knows about its own trial, so it is told the width of the whole job."""
    config = MonteCarloConfig(n_trial=1, padding=3)

    assert config.padding_style == "03d"
    assert f"trial_{7:{config.padding_style}}" == "trial_007"


def test_padding_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        MonteCarloConfig(n_trial=1, padding=0)


def test_run_single_has_a_padding_option() -> None:
    result = CliRunner().invoke(cli_app, ["run", "single", "--help"])

    assert result.exit_code == 0
    assert "--padding" in result.output


# --- SLURM settings from the global and project files ---


def _write_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    global_toml: str | None,
    project_toml: str | None,
) -> tuple[Path, Path]:
    global_path = tmp_path / "global" / "settings.toml"
    project_path = tmp_path / "project" / ".mujoco-mojo" / "settings.toml"
    for path, text in ((global_path, global_toml), (project_path, project_toml)):
        if text is not None:
            path.parent.mkdir(parents=True)
            path.write_text(text, encoding="utf-8")
    monkeypatch.setattr("mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", global_path)
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file", lambda: project_path
    )
    return global_path, project_path


def test_project_slurm_entries_add_to_and_override_the_global_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_settings(
        monkeypatch,
        tmp_path,
        global_toml='[slurm]\n"sbatch.account" = "GLOBAL"\n"sbatch.constraint" = "gpu"\n',
        project_toml='[slurm]\n"sbatch.account" = "PROJECT"\n"sbatch.qos" = "high"\n',
    )

    slurm = MujocoMojoSettings().slurm

    assert dict(slurm.root) == {
        "sbatch.account": "PROJECT",
        "sbatch.constraint": "gpu",
        "sbatch.qos": "high",
    }


def test_slurm_settings_sources_report_each_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    global_path, project_path = _write_settings(
        monkeypatch,
        tmp_path,
        global_toml='[slurm]\n"sbatch.account" = "GLOBAL"\n',
        project_toml=None,
    )

    global_source, project_source = slurm_settings_sources()

    assert (global_source.label, global_source.path) == ("global", global_path)
    assert global_source.exists
    assert global_source.entries == {"sbatch.account": "GLOBAL"}
    # the path it looked in is reported even though nothing is there
    assert (project_source.label, project_source.path) == ("project", project_path)
    assert not project_source.exists
    assert project_source.entries == {}


def test_slurm_settings_sources_report_an_unreadable_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_settings(
        monkeypatch, tmp_path, global_toml=None, project_toml="[slurm\nnot toml"
    )

    project_source = slurm_settings_sources()[-1]

    assert project_source.exists
    assert project_source.error is not None


def _printed_extras(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    global_toml: str | None,
    project_toml: str | None,
) -> str:
    _write_settings(
        monkeypatch, tmp_path, global_toml=global_toml, project_toml=project_toml
    )
    buffer = io.StringIO()
    console = Console(file=buffer, width=300, force_terminal=False, highlight=False)

    _print_slurm_extras(console, MujocoMojoSettings().slurm)

    return buffer.getvalue()


def test_printed_extras_list_each_line_with_where_it_came_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _printed_extras(
        tmp_path,
        monkeypatch,
        global_toml='[slurm]\n"sbatch.account" = "GLOBAL"\n"sbatch.constraint" = "gpu"\n',
        project_toml='[slurm]\n"sbatch.account" = "PROJECT"\n"sbatch.qos" = "high"\n',
    )

    assert "#SBATCH --account=PROJECT  (project)" in output
    assert "#SBATCH --constraint=gpu  (global)" in output
    assert "#SBATCH --qos=high  (project)" in output
    # the overridden global value is not part of the script
    assert "GLOBAL  (" not in output


def test_printed_extras_say_when_the_project_file_was_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """This is how a project file that was never read (wrong directory) becomes visible."""
    output = _printed_extras(
        tmp_path,
        monkeypatch,
        global_toml='[slurm]\n"sbatch.account" = "GLOBAL"\n',
        project_toml=None,
    )

    assert "not found" in output
    assert str(tmp_path / "project" / ".mujoco-mojo" / "settings.toml") in output
    assert "#SBATCH --account=GLOBAL  (global)" in output


def test_printed_extras_hide_environment_variable_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _printed_extras(
        tmp_path,
        monkeypatch,
        global_toml='[slurm]\nMLM_LICENSE_FILE = "27000@license.internal"\n',
        project_toml=None,
    )

    assert "export MLM_LICENSE_FILE=" in output
    assert "license.internal" not in output


def test_printed_extras_explain_how_to_add_settings_when_there_are_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = _printed_extras(tmp_path, monkeypatch, global_toml=None, project_toml=None)

    assert "No extra SLURM settings were found" in output
    assert "settings set --project slurm.sbatch.account" in output
