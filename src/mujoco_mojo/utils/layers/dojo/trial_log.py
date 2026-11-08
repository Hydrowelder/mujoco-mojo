"""Reading a trial's log file: the Dojo's log route and SensAI's job agent both read it the same way."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = ["DEFAULT_LOG_ENTRY", "find_log_file", "parse_log_file"]

DEFAULT_LOG_ENTRY: dict[str, Any] = {
    "timestamp": 0,
    "level": "Invalid Level",
    "pathname": "",
    "lineno": None,
    "message": "",
}
"""What an entry has when its line leaves a field out."""


def find_log_file(trial_dir: Path) -> Path | None:
    """The trial's log: `mojo.log` if it has one, else the first `*.log` file by name, else `None`."""
    log_path = trial_dir / "mojo.log"
    if log_path.is_file():
        return log_path
    candidates = sorted(trial_dir.glob("*.log")) if trial_dir.is_dir() else []
    return candidates[0] if candidates else None


def parse_log_file(log_path: Path) -> list[dict[str, Any]]:
    """
    Parses a `mojo.log` file of newline-delimited JSON log entries.

    Lines that aren't valid JSON (e.g. output from a library that doesn't use our JSON formatter) are appended to the message of the preceding entry. Entries missing fields are filled in with defaults.
    """
    entries: list[dict[str, Any]] = []
    with log_path.open(encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if not line:
                continue
            try:
                entries.append({**DEFAULT_LOG_ENTRY, **json.loads(line)})
            except json.JSONDecodeError:
                if entries:
                    entries[-1]["message"] += f"\n{line}"
    return entries
