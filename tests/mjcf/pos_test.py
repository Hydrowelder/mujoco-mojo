import numpy as np

from mujoco_mojo.mjcf.position import Pos


def test_pos_initialization():
    """Verify initialization with explicit ndarray wrapping."""
    # Wrapping here ensures the IDE sees the 'pos' field receiving an ndarray
    p = Pos(pos=np.asarray([1.0, 2.0, 3.0]))

    # Check that the underlying array is correct
    arr = np.asarray(p)
    assert isinstance(arr, np.ndarray)
    assert np.array_equal(arr, [1.0, 2.0, 3.0])


def test_pos_indexing():
    """Verify direct indexing works smoothly for the highlighter."""
    p = Pos(pos=np.asarray([10.0, 20.0, 30.0]))

    # Accessing via __getitem__ (p[0]) is safer for IDEs than p.pos[0]
    assert p[0] == 10.0
    assert p[1] == 20.0
    assert p[2] == 30.0

    # Slicing check
    assert np.array_equal(p[:2], [10.0, 20.0])


def test_pos_arithmetic():
    """Test operators return Pos instances with correct values."""
    p1 = Pos(pos=np.asarray([1.0, 2.0, 3.0]))
    p2 = Pos(pos=np.asarray([4.0, 5.0, 6.0]))

    # Addition: Pos + Pos -> Pos
    sum_p = p1 + p2
    assert isinstance(sum_p, Pos)
    assert np.array_equal(np.asarray(sum_p), [5.0, 7.0, 9.0])

    # Subtraction: Pos - Pos -> Pos
    diff_p = p2 - p1
    assert np.array_equal(np.asarray(diff_p), [3.0, 3.0, 3.0])

    # Scalar multiplication (Left and Right)
    mult_p = p1 * 2.0
    rmult_p = 2.0 * p1
    assert np.array_equal(np.asarray(mult_p), [2.0, 4.0, 6.0])
    assert np.array_equal(np.asarray(rmult_p), [2.0, 4.0, 6.0])


def test_pos_equality():
    """Verify __eq__ logic handles array comparisons correctly."""
    p1 = Pos(pos=np.asarray([1.0, 1.0, 1.0]))
    p2 = Pos(pos=np.asarray([1.0, 1.0, 1.0]))
    p3 = Pos(pos=np.asarray([1.0, 1.1, 1.0]))

    assert p1 == p2
    assert p1 != p3
    # Ensure it doesn't crash against different types
    assert not (p1 == "string")


def test_pos_math_utilities():
    """Test Euclidean distance and LERP."""
    p_start = Pos(pos=np.asarray([0.0, 0.0, 0.0]))
    p_end = Pos(pos=np.asarray([10.0, 0.0, 0.0]))

    # Distance calculation
    dist = p_start.distance_to(p_end)
    assert dist == 10.0

    # Linear interpolation (LERP)
    mid = p_start.lerp(p_end, 0.5)
    assert isinstance(mid, Pos)
    assert np.array_equal(np.asarray(mid), [5.0, 0.0, 0.0])


def test_pos_collection_interop():
    """Verify arithmetic works with raw lists/arrays through duck typing."""
    p = Pos(pos=np.asarray([1.0, 1.0, 1.0]))
    raw_list = [2.0, 3.0, 4.0]

    # Pos + list -> Pos (Internal logic handles the np.asarray for raw_list)
    res = p + raw_list
    assert isinstance(res, Pos)
    assert np.array_equal(np.asarray(res), [3.0, 4.0, 5.0])
