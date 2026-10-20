from typing import Any

from mujoco_mojo.utils.layers.dojo.lab_executor import LabExecutor
from mujoco_mojo.utils.signal_metadata import ColumnMetadata, TransformType


def _graph(*signal_outs: dict[str, Any]) -> dict[str, Any]:
    return {
        "nodes": [
            {"id": i, "type": "Signal/signal_out", "properties": props}
            for i, props in enumerate(signal_outs, start=1)
        ],
        "links": [],
    }


def test_output_metadata_reads_the_declared_fields() -> None:
    graph = _graph(
        {
            "label": "pos:x",
            "unit": "meter",
            "quantity": "length",
            "transform_type": "point",
        },
    )
    meta = LabExecutor(graph).output_metadata
    assert meta == {
        "pos:x": ColumnMetadata(
            unit="meter", quantity="length", transform_type=TransformType.POINT
        )
    }


def test_output_metadata_ignores_empty_values_and_unrelated_properties() -> None:
    graph = _graph(
        {"label": "a", "unit": "", "dimension": None, "color": "#fff"},
        {"label": "b", "dimension": "[length]", "color": "#fff"},
    )
    meta = LabExecutor(graph).output_metadata
    assert set(meta) == {"b"}
    assert meta["b"].model_dump() == {"dimension": "[length]"}


def test_output_metadata_skips_an_output_whose_metadata_is_invalid() -> None:
    graph = _graph(
        {"label": "bad", "unit": "not_a_unit"},
        {"label": "good", "unit": "meter"},
    )
    meta = LabExecutor(graph).output_metadata
    assert set(meta) == {"good"}


def test_output_metadata_falls_back_to_the_node_id_label() -> None:
    meta = LabExecutor(_graph({"unit": "meter"})).output_metadata
    assert set(meta) == {"out_1"}


def test_output_metadata_reads_every_field_the_model_declares() -> None:
    """The node's fields come from ColumnMetadata, so a property named after any declared field is picked up."""
    props: dict[str, Any] = {
        "label": "x",
        "unit": "meter",
        "dimension": "[length]",
        "quantity": "length",
        "transform_type": "vector",
        "enumeration_map": '{"A": 0, "B": 3}',
    }
    assert set(props) - {"label"} == set(ColumnMetadata.model_fields)
    meta = LabExecutor(_graph(props)).output_metadata["x"]
    assert meta.model_dump() == {
        "unit": "meter",
        "dimension": "[length]",
        "quantity": "length",
        "transform_type": "vector",
        "enumeration_map": {"A": 0, "B": 3},
    }


def test_output_metadata_keeps_the_rest_when_the_enumeration_map_is_not_json() -> None:
    """A malformed map drops this node's metadata with a warning, like any other invalid field."""
    graph = _graph(
        {"label": "bad", "unit": "meter", "enumeration_map": "A=0"},
        {"label": "good", "enumeration_map": '{"A": 0}'},
    )
    meta = LabExecutor(graph).output_metadata
    assert set(meta) == {"good"}
    assert meta["good"].enumeration_map == {"A": 0}
