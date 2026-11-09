import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from mujoco_mojo import MojoModel
from mujoco_mojo.stochas import DistName, NormalDistribution, UnitSystem
from mujoco_mojo.utils.layers.dojo import shared
from mujoco_mojo.utils.layers.dojo.routers.mosaic import (
    _in_unit,
    _sampled_values_in_dist_unit,
    _stat,
    _stored_unit,
    get_trial_dists,
)

INCH_IN_METERS = 0.0254
MU = 10.0
SIGMA = 0.5


def sampled_inch_model() -> tuple[MojoModel, float]:
    """An SI model with a distribution declared in inches and one draw from it, and that draw expressed in inches. Trial 0 draws the nominal, which would make the z-score zero whatever the scaling, so this uses a later trial."""
    model = MojoModel().with_seed(7).with_trial_num(2)
    model = model.with_unit_system(UnitSystem.si())
    assert model.us is not None
    dist = NormalDistribution(
        name=DistName("leg_len"),
        nominal=MU,
        mu=MU,
        sigma=SIGMA,
        unit=model.us.inch,
        category="geometry",
    )
    drawn = model.sample_dist(dist)
    in_inches = float(drawn.stored_value[0]) / INCH_IN_METERS
    assert in_inches != pytest.approx(MU)
    return model, in_inches


def test_a_draw_is_stored_in_the_base_unit_while_the_distribution_keeps_its_own() -> (
    None
):
    """The premise of the Dojo bug: the two sides really are in different units."""
    model, in_inches = sampled_inch_model()
    stored = json.loads(model.named.model_dump_json())["leg_len"]

    assert stored["unit"] == {"name": "m"}
    assert float(stored["stored_value"][0]) == pytest.approx(in_inches * INCH_IN_METERS)
    assert str(model.dists["leg_len"].unit) == "inch"


def test_the_draw_is_reported_in_the_unit_of_the_distribution() -> None:
    model, in_inches = sampled_inch_model()
    named_raw = json.loads(model.named.model_dump_json())

    values = _sampled_values_in_dist_unit(named_raw, model.dists["leg_len"])

    assert values == pytest.approx([in_inches])
    # an inch draw from 10 +/- 0.5 inches lies near the mean, not 19 sigma below it
    assert values is not None
    z_score, percentile = _stat(model.dists["leg_len"], values[0])
    assert z_score == pytest.approx((in_inches - MU) / SIGMA, abs=1e-3)
    assert z_score is not None
    assert abs(z_score) < 5
    assert percentile is not None
    assert 0.0 < percentile < 100.0


def test_the_endpoint_reports_the_draw_and_its_z_score_in_the_declared_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model, in_inches = sampled_inch_model()
    (tmp_path / "stochas").mkdir()
    (tmp_path / "stochas" / "dists.json").write_text(model.dists.model_dump_json())
    trial = tmp_path / "trials" / "trial_000"
    trial.mkdir(parents=True)
    (trial / "named_values.json").write_text(model.named.model_dump_json())
    monkeypatch.setattr(shared, "CURRENT_JOB", SimpleNamespace(workdir=tmp_path))

    (entry,) = asyncio.run(get_trial_dists("trial_000"))["entries"]

    assert entry["units"] == "inch"
    assert entry["nominal"] == MU
    assert entry["params"]["mu"] == MU
    assert entry["sampled_value"] == pytest.approx(in_inches)
    assert entry["sampled_values"] == pytest.approx([in_inches])
    assert entry["z_score"] == pytest.approx((in_inches - MU) / SIGMA, abs=1e-3)
    # read as meters, this draw would have been -19.5 sigma and flagged as an outlier
    assert abs(entry["z_score"]) < 5


@pytest.mark.parametrize(
    ("values", "from_unit", "to_unit", "expected"),
    [
        ([0.0254, 0.0508], "m", "inch", [1.0, 2.0]),
        ([1.0], "kg", "g", [1000.0]),
        ([100.0], "degC", "degF", [212.0]),
        ([], "m", "inch", []),
    ],
)
def test_values_are_converted_between_compatible_units(
    values: list[float], from_unit: str, to_unit: str, expected: list[float]
) -> None:
    assert _in_unit(values, from_unit, to_unit) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("from_unit", "to_unit"),
    [
        ("m", "m"),
        (None, "inch"),
        ("m", None),
        ("", "inch"),
        ("m", "not_a_unit"),
        ("not_a_unit", "inch"),
        ("m", "kg"),
    ],
)
def test_values_are_left_alone_when_there_is_nothing_sensible_to_convert(
    from_unit: str | None, to_unit: str | None
) -> None:
    assert _in_unit([1.5, 2.5], from_unit, to_unit) == [1.5, 2.5]


@pytest.mark.parametrize(
    ("named_raw", "expected"),
    [
        ({"x": {"unit": {"name": "m"}}}, "m"),
        ({"x": {"unit": "m"}}, "m"),
        ({"root": {"x": {"unit": {"name": "m"}}}}, "m"),
        ({"x": {"unit": None}}, None),
        ({"x": {}}, None),
        ({}, None),
    ],
)
def test_the_stored_unit_is_read_however_it_was_written(
    named_raw: dict[str, Any], expected: str | None
) -> None:
    assert _stored_unit(named_raw, "x") == expected


def test_nothing_is_converted_without_a_declared_unit_or_a_recorded_one() -> None:
    plain = NormalDistribution(name=DistName("x"), nominal=0.0, mu=0.0, sigma=1.0)
    declared = NormalDistribution(name=DistName("x"), nominal=0.0, mu=0.0, sigma=1.0)
    declared.unit = UnitSystem.si().inch
    stored = {"x": {"stored_value": [0.0254], "unit": {"name": "m"}}}
    unrecorded = {"x": {"stored_value": [0.0254]}}

    assert _sampled_values_in_dist_unit(stored, plain) == [0.0254]
    assert _sampled_values_in_dist_unit(unrecorded, declared) == [0.0254]
    assert _sampled_values_in_dist_unit(stored, declared) == pytest.approx([1.0])
    assert _sampled_values_in_dist_unit({}, declared) is None
