"""Tests for what reaches the terminal: a logger quieted with `quiet_in_terminal` logs below WARNING to the file only."""

import logging
import os
from collections.abc import Iterator

import pytest

from mujoco_mojo.utils import log


@pytest.fixture(autouse=True)
def nothing_quiet(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(log, "_QUIET_IN_TERMINAL", set())
    log._is_quiet.cache_clear()
    yield
    log._is_quiet.cache_clear()


def record(name: str, level: int = logging.INFO, **extra: object) -> logging.LogRecord:
    made = logging.LogRecord(name, level, __file__, 1, "message", None, None)
    made.__dict__.update(extra)
    return made


def shown(made: logging.LogRecord) -> bool:
    return log.TerminalFilter().filter(made)


def test_a_quiet_logger_and_the_ones_under_it_stay_out_of_the_terminal() -> None:
    log.quiet_in_terminal("httpx")

    assert not shown(record("httpx"))
    assert not shown(record("httpx._client", logging.DEBUG))
    assert shown(record("httpxtra"))
    assert shown(record("mujoco_mojo.runtime"))


def test_a_quiet_logger_still_shows_its_warnings_and_errors() -> None:
    log.quiet_in_terminal("mujoco_mojo.utils.sensai")

    assert shown(record("mujoco_mojo.utils.sensai.agents.docs", logging.WARNING))
    assert shown(record("mujoco_mojo.utils.sensai", logging.ERROR))


def test_a_logger_quieted_after_its_first_record_is_quiet_from_then_on() -> None:
    """The answer for a name is cached, and quieting it has to drop that."""
    assert shown(record("late"))

    log.quiet_in_terminal("late")

    assert not shown(record("late"))


def test_a_file_only_record_never_shows() -> None:
    assert not shown(record("anything", logging.ERROR, file_only=True))


def test_importing_sensai_turns_off_the_pydantic_ai_banner() -> None:
    """Every agent run goes through the package, so importing it is early enough."""
    import mujoco_mojo.utils.sensai  # noqa: F401

    assert "PYDANTIC_AI_NO_BANNER" in os.environ
