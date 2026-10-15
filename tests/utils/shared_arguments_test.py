import inspect
import json
import logging
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

import mujoco_mojo as mojo
from mujoco_mojo.utils.layers.cli import cli_app
from mujoco_mojo.utils.runner import (
    GENERATOR_FIXED_ARGS,
    OBJECTIVE_FIXED_ARGS,
    RUNTIME_FIXED_ARGS,
    MojoRunner,
    MonteCarloConfig,
    accepted_kwarg_names,
    select_kwargs,
    validate_shared_kwargs,
)
from mujoco_mojo.utils.statusing import JOB_STATUS_FNAME, JobStatus

# --- functions with different signatures, as a user would write them ---


def explicit(
    model: Any, overrides: Any, mode: str = "fast", *, scale: float = 1.0
) -> Any:
    return model


def takes_everything(model: Any, overrides: Any, *args: Any, **kwargs: Any) -> Any:
    return model


def positional_only(model: Any, overrides: Any, /, mode: str = "fast") -> Any:
    return model


# --- which keywords a function accepts ---


def test_explicit_parameters_are_the_accepted_names() -> None:
    names = accepted_kwarg_names(explicit, GENERATOR_FIXED_ARGS, [])

    # the two fixed leading arguments are never a keyword
    assert names == {"mode", "scale"}


def test_a_name_bound_positionally_is_not_accepted_again_by_keyword() -> None:
    """`--arg x` fills `mode`, so `--kwarg mode=...` would raise 'multiple values'."""
    assert accepted_kwarg_names(explicit, GENERATOR_FIXED_ARGS, ["x"]) == {"scale"}


def test_var_keyword_accepts_anything() -> None:
    assert accepted_kwarg_names(takes_everything, GENERATOR_FIXED_ARGS, []) is None


def test_positional_only_parameters_are_not_keywords() -> None:
    names = accepted_kwarg_names(positional_only, GENERATOR_FIXED_ARGS, [])

    assert names == {"mode"}


def test_an_unreadable_signature_accepts_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_signature(*args: Any, **kwargs: Any) -> inspect.Signature:
        raise ValueError("no signature found")

    monkeypatch.setattr(inspect, "signature", no_signature)

    assert accepted_kwarg_names(explicit, GENERATOR_FIXED_ARGS, []) is None


def test_select_kwargs_keeps_only_what_the_function_accepts() -> None:
    shared = {"mode": "slow", "scale": 2.0, "weight": 5}

    assert select_kwargs(explicit, GENERATOR_FIXED_ARGS, [], shared) == {
        "mode": "slow",
        "scale": 2.0,
    }
    assert select_kwargs(takes_everything, GENERATOR_FIXED_ARGS, [], shared) == shared


# --- catching a misspelled keyword ---


def test_a_keyword_nobody_accepts_is_an_error_naming_what_is_accepted() -> None:
    targets = {
        "generator": (explicit, GENERATOR_FIXED_ARGS),
        "objective": (positional_only, OBJECTIVE_FIXED_ARGS),
    }

    with pytest.raises(ValueError, match="modee") as raised:
        validate_shared_kwargs({"mode": "slow", "modee": "typo"}, [], targets)

    assert "generator: ['mode', 'scale']" in str(raised.value)


def test_a_keyword_accepted_by_any_one_function_is_fine() -> None:
    targets = {
        "generator": (explicit, GENERATOR_FIXED_ARGS),
        "runtime": (positional_only, RUNTIME_FIXED_ARGS),
    }

    validate_shared_kwargs({"scale": 2.0}, [], targets)


def test_nothing_is_checked_when_a_function_takes_var_keyword() -> None:
    """A `**kwargs` function accepts every key, so a typo cannot be told apart from a real one."""
    targets = {
        "generator": (explicit, GENERATOR_FIXED_ARGS),
        "runtime": (takes_everything, RUNTIME_FIXED_ARGS),
    }

    validate_shared_kwargs({"anything": 1}, [], targets)


# --- the runner ---

_received: dict[str, Any] = {}


def recording_generator(
    mojo_model: mojo.MojoModel, overrides: Any, first: str, mode: str = "fast"
) -> mojo.MojoModel:
    _received["generator"] = {"first": first, "mode": mode}
    return mojo_model


def objective_with_weight(
    mojo_model: Any, telemetry: Any, state: Any, first: str, weight: int = 1
) -> float:
    return 0.0


def test_the_generator_gets_the_shared_arguments_filtered_to_its_signature(
    tmp_path: Path,
) -> None:
    """`weight` belongs to the objective, so the generator must not be called with it."""
    _received.clear()
    runner = MojoRunner(
        generator=recording_generator,
        objective=objective_with_weight,
        workdir=tmp_path,
        config=MonteCarloConfig(n_trial=1, n_proc=1),
        args=["a"],
        kwargs={"mode": "slow", "weight": 3},
    )

    had_fails = runner.run()

    assert not had_fails
    assert _received["generator"] == {"first": "a", "mode": "slow"}


def test_run_rejects_a_misspelled_keyword_before_doing_anything(
    tmp_path: Path,
) -> None:
    workdir = tmp_path / "work"
    runner = MojoRunner(
        generator=recording_generator,
        workdir=workdir,
        config=MonteCarloConfig(n_trial=1, n_proc=1),
        args=["a"],
        kwargs={"modee": "typo"},
    )

    with pytest.raises(ValueError, match="modee"):
        runner.run()

    assert not workdir.exists()


def test_shared_argument_flags_round_trip_through_the_cli_parser() -> None:
    from mujoco_mojo.utils.layers.cli import _process_kwargs, _smart_parse

    runner = MojoRunner(
        generator=explicit,
        args=["a", 1.5],
        kwargs={"mode": "fast", "flag": False},
    )

    assert runner.shared_argument_flags() == (
        '--arg "a" --arg "1.5" --kwarg "mode=fast" --kwarg "flag=False"'
    )
    # what the worker's `run single` will parse those back into
    assert _smart_parse("1.5") == 1.5
    assert _process_kwargs(["mode=fast", "flag=False"]) == {
        "mode": "fast",
        "flag": False,
    }


def test_shared_argument_flags_are_empty_without_arguments() -> None:
    assert MojoRunner(generator=explicit).shared_argument_flags() == ""


# --- the CLI ---


@pytest.fixture
def isolated_logging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """
    Runs a CLI command in a temporary directory and puts the logging state back afterwards.

    Every command calls `setup_logger`, which replaces the root logger's handlers and opens `mojo.log` in the current directory. Left alone, that writes a log into the repository and leaves the file handle open for pytest to complain about.
    """
    monkeypatch.chdir(tmp_path)
    root = logging.getLogger()
    handlers, level, propagate = list(root.handlers), root.level, root.propagate
    yield
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)
    root.propagate = propagate


@pytest.fixture
def user_module(tmp_path: Path) -> Iterator[Path]:
    """A module on `sys.path` whose generator takes `mode` and `flag`."""
    (tmp_path / "shared_args_sim.py").write_text(
        "import os\n"
        "from pathlib import Path\n\n"
        "def generate(mojo_model, overrides, mode='fast', flag=True):\n"
        "    Path(os.environ['SHARED_ARGS_OUT']).write_text(repr((mode, flag)))\n"
        "    return mojo_model\n"
    )
    sys.path.insert(0, str(tmp_path))
    yield tmp_path
    sys.path.remove(str(tmp_path))
    sys.modules.pop("shared_args_sim", None)


@pytest.mark.parametrize("command", ["monte-carlo", "single", "optimization"])
def test_run_commands_take_arg_and_kwarg_not_the_old_options(command: str) -> None:
    result = CliRunner().invoke(cli_app, ["run", command, "--help"])

    assert result.exit_code == 0
    assert "--arg" in result.output
    assert "--kwarg" in result.output
    for old in ("--gen-arg", "--gen-kwarg", "--run-arg", "--run-kwarg"):
        assert old not in result.output


def test_reloaded_takes_arg_and_kwarg() -> None:
    result = CliRunner().invoke(cli_app, ["reloaded", "--help"])

    assert result.exit_code == 0
    assert "--kwarg" in result.output
    assert "--gen-kwarg" not in result.output


@pytest.mark.parametrize(
    "old", ["--gen-kwarg", "--run-kwarg", "--gen-arg", "--run-arg"]
)
def test_the_old_options_are_gone(old: str) -> None:
    result = CliRunner().invoke(cli_app, ["run", "single", "-g", "x.y", old, "a=1"])

    assert result.exit_code == 2
    assert "No such option" in result.output


def test_a_misspelled_kwarg_stops_the_command_with_a_message(
    user_module: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_logging: None,
) -> None:
    monkeypatch.setenv("SHARED_ARGS_OUT", str(tmp_path / "out.txt"))

    result = CliRunner().invoke(
        cli_app,
        [
            "run",
            "single",
            "-g",
            "shared_args_sim.generate",
            "--workdir",
            str(tmp_path / "work"),
            "--kwarg",
            "modee=slow",
        ],
    )

    assert result.exit_code == 1
    assert "modee" in result.output
    # nothing ran
    assert not (tmp_path / "out.txt").exists()


def test_a_lowercase_false_reaches_the_generator_as_a_bool(
    user_module: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_logging: None,
) -> None:
    out = tmp_path / "out.txt"
    monkeypatch.setenv("SHARED_ARGS_OUT", str(out))

    result = CliRunner().invoke(
        cli_app,
        [
            "run",
            "single",
            "-g",
            "shared_args_sim.generate",
            "--workdir",
            str(tmp_path / "work"),
            "-k",
            "mode=slow",
            "-k",
            "flag=false",
        ],
    )

    assert result.exit_code == 0, result.output
    assert out.read_text() == repr(("slow", False))


# --- the job status file ---


def test_job_status_records_whether_args_and_kwargs_were_used(tmp_path: Path) -> None:
    MojoRunner(
        generator=recording_generator,
        workdir=tmp_path,
        config=MonteCarloConfig(n_trial=1, n_proc=1),
        args=["a"],
        kwargs={"mode": "slow"},
    ).run()

    status = json.loads((tmp_path / JOB_STATUS_FNAME).read_text())

    assert status["args_used"] is True
    assert status["kwargs_used"] is True
    assert not any(key.startswith(("gen_", "run_")) for key in status)


def test_a_status_file_from_before_the_change_no_longer_loads(tmp_path: Path) -> None:
    """The four separate flags were replaced outright, with no compatibility shim."""
    MojoRunner(
        generator=recording_generator,
        workdir=tmp_path,
        config=MonteCarloConfig(n_trial=1, n_proc=1),
        args=["a"],
    ).run()
    status = json.loads((tmp_path / JOB_STATUS_FNAME).read_text())
    status.pop("args_used")
    status.pop("kwargs_used")
    status.update(
        gen_args_used=True,
        gen_kwargs_used=False,
        run_args_used=False,
        run_kwargs_used=False,
    )

    with pytest.raises(ValidationError, match="args_used"):
        JobStatus.model_validate(status)


def test_the_runtime_report_has_one_row_each_for_args_and_kwargs(
    tmp_path: Path,
) -> None:
    MojoRunner(
        generator=recording_generator,
        workdir=tmp_path,
        config=MonteCarloConfig(n_trial=1, n_proc=1),
        args=["a"],
    ).run()

    report = (tmp_path / "MOJO_RUNTIME_REPORT.md").read_text(encoding="utf-8")

    assert "| Args Used?" in report
    assert "| Kwargs Used?" in report
    assert "Generator Args Used?" not in report
    assert "Runtime Kwargs Used?" not in report
