"""Tests for the units the Dojo's trial data route reports when a display unit system is picked: each column has to be labeled with the unit its values are in."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import mujoco
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.runtime.signal_manager import SignalManager
from mujoco_mojo.utils.column import Column
from mujoco_mojo.utils.layers.dojo import shared
from mujoco_mojo.utils.layers.dojo.routers import mosaic
from mujoco_mojo.utils.signal_metadata import ColumnMetadata

REACH = Column(
    category="Custom",
    subgroups=("probe",),
    attr="reach",
    metadata=ColumnMetadata(unit="inch"),
)
"""A custom signal with only a unit, which the display unit system converts."""

ANGLE = Column(
    category="Custom",
    subgroups=("probe",),
    attr="angle",
    metadata=ColumnMetadata(unit="degree", quantity="angle"),
)
"""An angle, which a unit system has no unit for, so it is left as it is."""

SPEED = Column(
    category="Custom",
    subgroups=("probe",),
    attr="speed",
    metadata=ColumnMetadata(unit="m / s", dimension="[length] / [time]"),
)
"""Tagged the way a built-in signal is, with a dimension and the unit it resolved to."""


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A client for the mosaic router, with a job whose one trial recorded a row of `REACH`, `ANGLE` and `SPEED`."""
    trial = tmp_path / "trials" / "trial_0"
    trial.mkdir(parents=True)
    model = mujoco.MjModel.from_xml_string("<mujoco/>")
    state = MjState(model, mujoco.MjData(model))
    manager = SignalManager(export_path=trial / SignalManager.default_output_name())

    def sample(_: MjState) -> None:
        manager.post(1.0, REACH)
        manager.post(90.0, ANGLE)
        manager.post(2.0, SPEED)

    manager.register_sampler(sample)
    manager.record(state)
    manager.close()

    monkeypatch.setattr(shared, "CURRENT_JOB", SimpleNamespace(workdir=tmp_path))
    # the lab folder adds the machine's saved lab signals to the columns
    lab = tmp_path / "lab"
    lab.mkdir()
    monkeypatch.setattr(mosaic, "_get_lab_dir", lambda: lab)
    app = FastAPI()
    app.include_router(mosaic.router, prefix="/mosaic")
    return TestClient(app)


def fetch(client: TestClient, unit_system: str) -> dict[str, Any]:
    """The route's reply for the three columns, shown in `unit_system`."""
    response = client.get(
        "/mosaic/trial_0/data",
        params={
            "cols": ",".join(str(column) for column in (REACH, ANGLE, SPEED)),
            "display_unit_system": unit_system,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize(
    ("unit_system", "value", "unit"),
    [("si", 0.0254, "meter"), ("cgs", 2.54, "centimeter")],
)
def test_a_column_with_only_a_unit_is_labeled_with_the_unit_its_values_became(
    client: TestClient, unit_system: str, value: float, unit: str
) -> None:
    """It kept the unit it was recorded in, so a reach in inches showed 0.0254 labeled inch."""
    body = fetch(client, unit_system)

    assert body["data"][str(REACH)] == pytest.approx([value])
    assert body["columns"]["column_metadata"][str(REACH)]["unit"] == unit


@pytest.mark.parametrize("unit_system", ["si", "cgs"])
def test_an_angle_keeps_its_values_and_its_unit(
    client: TestClient, unit_system: str
) -> None:
    body = fetch(client, unit_system)

    assert body["data"][str(ANGLE)] == [90.0]
    assert body["columns"]["column_metadata"][str(ANGLE)]["unit"] == "degree"


@pytest.mark.parametrize(
    ("unit_system", "value", "unit"),
    [("si", 2.0, "m / s"), ("cgs", 200.0, "cm / s")],
)
def test_a_column_with_a_dimension_is_labeled_from_it(
    client: TestClient, unit_system: str, value: float, unit: str
) -> None:
    """The built-in signals' labels, written from their dimension in the system's units."""
    body = fetch(client, unit_system)

    assert body["data"][str(SPEED)] == pytest.approx([value])
    assert body["columns"]["column_metadata"][str(SPEED)]["unit"] == unit
