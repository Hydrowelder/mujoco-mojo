"""Tests for reading a trial's log file (`dojo/trial_log.py`) and the Dojo route that returns it."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mujoco_mojo.utils.layers.dojo import shared
from mujoco_mojo.utils.layers.dojo.routers import mosaic
from mujoco_mojo.utils.layers.dojo.trial_log import (
    DEFAULT_LOG_ENTRY,
    find_log_file,
    parse_log_file,
)
from mujoco_mojo.utils.statusing import ExecutionMode, JobStatus, JobType


def entry(message: str, level: str = "INFO", **fields: Any) -> str:
    return json.dumps(
        {
            "timestamp": 1000.0,
            "level": level,
            "pathname": "a.py",
            "lineno": 3,
            "message": message,
            **fields,
        }
    )


class TestParsing:
    def test_each_line_is_an_entry(self, tmp_path: Path) -> None:
        log = tmp_path / "mojo.log"
        log.write_text(entry("one") + "\n" + entry("two", "ERROR") + "\n")

        assert [(e["level"], e["message"]) for e in parse_log_file(log)] == [
            ("INFO", "one"),
            ("ERROR", "two"),
        ]

    def test_a_line_that_is_not_json_continues_the_message_before_it(
        self, tmp_path: Path
    ) -> None:
        log = tmp_path / "mojo.log"
        log.write_text(entry("first") + "\nlibrary output\nmore output\n")

        [only] = parse_log_file(log)

        assert only["message"] == "first\nlibrary output\nmore output"

    def test_a_non_json_line_before_any_entry_is_dropped(self, tmp_path: Path) -> None:
        log = tmp_path / "mojo.log"
        log.write_text("stray\n" + entry("real") + "\n")

        assert [e["message"] for e in parse_log_file(log)] == ["real"]

    def test_blank_lines_are_skipped(self, tmp_path: Path) -> None:
        log = tmp_path / "mojo.log"
        log.write_text("\n" + entry("a") + "\n\n\n" + entry("b") + "\n")

        assert len(parse_log_file(log)) == 2

    def test_a_missing_field_gets_its_default(self, tmp_path: Path) -> None:
        log = tmp_path / "mojo.log"
        log.write_text(json.dumps({"message": "bare"}) + "\n")

        assert parse_log_file(log) == [{**DEFAULT_LOG_ENTRY, "message": "bare"}]

    def test_bytes_that_are_not_utf8_do_not_stop_the_read(self, tmp_path: Path) -> None:
        log = tmp_path / "mojo.log"
        log.write_bytes(entry("ok").encode() + b"\n\xff\xfe broken\n")

        [only] = parse_log_file(log)

        assert only["message"].startswith("ok\n")


class TestFindingTheLog:
    def test_mojo_log_is_preferred(self, tmp_path: Path) -> None:
        (tmp_path / "a.log").write_text("")
        (tmp_path / "mojo.log").write_text("")

        assert find_log_file(tmp_path) == tmp_path / "mojo.log"

    def test_without_it_the_first_log_by_name_is_used(self, tmp_path: Path) -> None:
        (tmp_path / "b.log").write_text("")
        (tmp_path / "a.log").write_text("")

        assert find_log_file(tmp_path) == tmp_path / "a.log"

    def test_a_folder_with_no_log_gives_none(self, tmp_path: Path) -> None:
        (tmp_path / "notes.txt").write_text("")

        assert find_log_file(tmp_path) is None

    def test_a_folder_that_does_not_exist_gives_none(self, tmp_path: Path) -> None:
        assert find_log_file(tmp_path / "nope") is None


class TestTheLogsRoute:
    @pytest.fixture
    def client(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        job = JobStatus(
            job_type=JobType.MONTE_CARLO,
            execution_mode=ExecutionMode.LOCAL,
            workdir=tmp_path,
            n_proc=1,
            padding_style="02",
            seed=0,
            generator=("g", None, None),
            runtime=("r", None, None),
            objective=("o", None, None),
            trial_nums=[0, 1, 2],
        )
        monkeypatch.setattr(shared, "CURRENT_JOB", job)
        app = FastAPI()
        app.include_router(mosaic.router, prefix="/mosaic")
        return TestClient(app)

    def trial_dir(self, tmp_path: Path, name: str) -> Path:
        path = tmp_path / "trials" / name
        path.mkdir(parents=True)
        return path

    def test_it_returns_the_entries_and_the_file_name(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        (self.trial_dir(tmp_path, "trial_00") / "mojo.log").write_text(
            entry("hello") + "\n"
        )

        body = client.get("/mosaic/trial_00/logs").json()

        assert body["filename"] == "mojo.log"
        assert [e["message"] for e in body["entries"]] == ["hello"]

    def test_a_trial_with_no_log_has_no_entries(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        self.trial_dir(tmp_path, "trial_01")

        assert client.get("/mosaic/trial_01/logs").json() == {
            "filename": None,
            "entries": [],
        }

    def test_a_trial_folder_that_does_not_exist_has_no_entries(
        self, client: TestClient
    ) -> None:
        assert client.get("/mosaic/trial_02/logs").json() == {
            "filename": None,
            "entries": [],
        }
