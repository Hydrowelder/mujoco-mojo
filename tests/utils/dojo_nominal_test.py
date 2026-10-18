import numpy as np
import pytest

from mujoco_mojo.utils.layers.dojo.routers.mosaic import _split_nominal


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (2.5, 2.5),
        (3, 3.0),
        (True, 1.0),
        (np.float64(1.5), 1.5),
        (np.array(4.0), 4.0),
        ("3.5", 3.5),
    ],
)
def test_numbers_and_numeric_strings_are_exposed_as_a_float(
    raw: object, expected: float
) -> None:
    assert _split_nominal(raw) == (expected, None)


@pytest.mark.parametrize(
    ("raw", "label"),
    [
        ("class_A", "class_A"),
        (["a", "b"], "a, b"),
        ((1, 2, 3), "1, 2, 3"),
    ],
)
def test_strings_and_sequences_are_exposed_as_a_label(raw: object, label: str) -> None:
    assert _split_nominal(raw) == (None, label)


@pytest.mark.parametrize("raw", [None, np.array([1.0, 2.0]), object()])
def test_anything_else_has_neither_a_number_nor_a_label(raw: object) -> None:
    assert _split_nominal(raw) == (None, None)
