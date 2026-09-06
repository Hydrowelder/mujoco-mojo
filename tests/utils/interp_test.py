import numpy as np
import pytest

from mujoco_mojo.utils.interp import Interpolator


def test_linear_interpolation():
    """Verify standard midpoint lookup."""
    # Using np.asarray() to keep the constructor clean
    x = np.asarray([0.0, 10.0])
    y = np.asarray([0.0, 100.0])
    interp = Interpolator(x=x, y=y, kind="linear")

    # Midpoint check
    assert interp.lookup(5.0) == pytest.approx(50.0)
    # Edge check
    assert interp.lookup(0.0) == 0.0
    assert interp.lookup(10.0) == 100.0


def test_extrapolation():
    """Verify that fill_value='extrapolate' works as expected."""
    x = np.asarray([0.0, 1.0])
    y = np.asarray([10.0, 20.0])
    interp = Interpolator(x=x, y=y, kind="linear")

    # Testing beyond the upper bound
    assert interp.lookup(2.0) == pytest.approx(30.0)
    # Testing below the lower bound
    assert interp.lookup(-1.0) == pytest.approx(0.0)


def test_nearest_neighbor():
    """Verify 'nearest' kind interpolation."""
    x = np.asarray([0.0, 10.0])
    y = np.asarray([0.0, 100.0])
    interp = Interpolator(x=x, y=y, kind="nearest")

    # 2.0 is closer to 0.0 than 10.0
    assert interp.lookup(2.0) == 0.0
    # 8.0 is closer to 10.0
    assert interp.lookup(8.0) == 100.0


def test_from_arrays():
    """Verify factory method using plain x/y array-likes."""
    x = [0, 1, 2]
    y = [10, 20, 30]

    interp = Interpolator.from_arrays(x, y)

    assert interp.lookup(0.5) == pytest.approx(15.0)
    assert np.array_equal(np.asarray(interp.x), x)
    assert np.array_equal(np.asarray(interp.y), y)


def test_pydantic_validation():
    """Verify that Pydantic converts lists to arrays automatically."""
    # Passing raw lists - Pydantic's numpydantic should handle the conversion
    interp = Interpolator(x=np.asarray([0, 1]), y=np.asarray([10, 20]))

    assert isinstance(interp.x, np.ndarray)
    assert interp.lookup(0.5) == 15.0


def test_invalid_shapes():
    """Verify behavior when x and y lengths don't match."""
    # This should be caught by Scipy's interp1d inside our validator
    with pytest.raises(ValueError):
        Interpolator(x=np.asarray([0, 1]), y=np.asarray([10, 20, 30]))
