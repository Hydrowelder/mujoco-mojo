import numpy as np
import polars as pl
import pytest
from pydantic import ValidationError

from mujoco_mojo.utils.dataframe import MojoDataFrame
from mujoco_mojo.utils.filters import (
    AbsoluteValueFilter,
    AnyFilter,
    ClipFilter,
    DeadbandFilter,
    DerivativeFilter,
    FirstFilter,
    HighPassFilter,
    IntegralFilter,
    LastFilter,
    LowPassFilter,
    MaxFilter,
    MeanFilter,
    MedianFilter,
    MinFilter,
    ModeFilter,
    NormalizeFilter,
    RollingMeanFilter,
    RollingMedianFilter,
    RotationFilter,
    SavitzkyGolayFilter,
    ScaleFilter,
    SortFilter,
    StandardDeviationFilter,
    TaringFilter,
    UnitFilter,
    WrapFilter,
)


@pytest.fixture
def signal_df():
    """A basic linear ramp for testing deterministic filters."""
    return pl.DataFrame(
        {"val": [0.0, 1.0, 2.0, 3.0, 4.0], "noise": [-0.001, 0.005, 0.5, -0.5, 0.001]}
    )


# --- Math & Basic Transformation Tests ---


def test_scale_filter(signal_df: MojoDataFrame):
    f = ScaleFilter(factor=2.0, offset=1.0)
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    # Expected: (x * 2) + 1 -> [1, 3, 5, 7, 9]
    assert result == [1.0, 3.0, 5.0, 7.0, 9.0]


def test_absolute_value_filter():
    df = pl.DataFrame({"x": [-1.0, 0.0, 1.0]})
    f = AbsoluteValueFilter()
    result = df.select(f.apply(pl.col("x")))["x"].to_list()
    assert result == [1.0, 0.0, 1.0]


def test_zeroing_filter(signal_df: MojoDataFrame):
    # Offsets the entire series so the first value is 0
    # Our 'val' already starts at 0, so let's use a shifted version
    df = signal_df.with_columns(pl.col("val") + 10.0)
    f = TaringFilter()
    result = df.select(f.apply(pl.col("val")))["val"].to_list()
    assert result == [0.0, 1.0, 2.0, 3.0, 4.0]


# --- Calculus & Signal Processing Tests ---


def test_derivative_filter(signal_df: MojoDataFrame):
    # Ramp 0, 1, 2, 3, 4 with dt=1.0 should have derivative of 1.0
    f = DerivativeFilter(dt=1.0)
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    # First value is 0 due to .fill_null(0)
    assert result == [0.0, 1.0, 1.0, 1.0, 1.0]


def test_integral_filter(signal_df: MojoDataFrame):
    # Integral of [0, 1, 2] with dt=1.0 is cumsum [0, 1, 3]
    f = IntegralFilter(dt=1.0)
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    assert result == [0.0, 1.0, 3.0, 6.0, 10.0]


def test_low_pass_filter(signal_df: MojoDataFrame):
    # Alpha=1.0 should return the original signal (no smoothing)
    f = LowPassFilter(alpha=1.0)
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    assert result == signal_df["val"].to_list()


def test_deadband_filter(signal_df: MojoDataFrame):
    f = DeadbandFilter(threshold=0.1)
    result = signal_df.select(f.apply(pl.col("noise")))["noise"].to_list()
    # noise: [-0.001, 0.005, 0.5, -0.5, 0.001]
    # Expected: [0, 0, 0.5, -0.5, 0]
    assert result == [0.0, 0.0, 0.5, -0.5, 0.0]


# --- Boundary & Circular Tests ---


def test_clip_filter(signal_df: MojoDataFrame):
    f = ClipFilter(min=1.5, max=3.5)
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    assert result == [1.5, 1.5, 2.0, 3.0, 3.5]


def test_wrap_filter():
    # Test wrapping around [0, 3]
    f = WrapFilter(lb=0, ub=3)
    df = pl.DataFrame({"x": [3.5, -0.5, 1.0]})
    result = df.select(f.apply(pl.col("x")))["x"].to_list()
    # 3.5 wraps to 0.5, -0.5 wraps to 2.5
    assert np.allclose(result, [0.5, 2.5, 1.0])


def test_normalize_filter(signal_df: MojoDataFrame):
    f = NormalizeFilter()
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    assert np.allclose(result[0], 0.0)
    assert np.allclose(result[-1], 1.0)


def test_rotation_filter_apply_to_frame_missing_quat_columns_raises():
    """apply_to_frame must fail loudly rather than silently returning the frame unchanged."""
    df = pl.DataFrame(
        {
            "Bodies/racket/xpos:x": [1.0],
            "Bodies/racket/xpos:y": [0.0],
            "Bodies/racket/xpos:z": [0.0],
        }
    )
    f = RotationFilter(quat_col="Bodies/racket/missing_quat", origin_col=None)
    with pytest.raises(ValueError, match="not found"):
        f.apply_to_frame(df, {"Bodies/racket/xpos"})


def test_rotation_filter_apply_to_frame_point_bases_without_origin_col_raises():
    df = pl.DataFrame(
        {
            "Bodies/racket/xquat:x": [0.0],
            "Bodies/racket/xquat:y": [0.0],
            "Bodies/racket/xquat:z": [0.0],
            "Bodies/racket/xquat:w": [1.0],
            "Bodies/target/xpos:x": [5.0],
            "Bodies/target/xpos:y": [0.0],
            "Bodies/target/xpos:z": [0.0],
        }
    )
    f = RotationFilter(quat_col="Bodies/racket/xquat", origin_col=None)
    with pytest.raises(ValueError, match="origin_col"):
        f.apply_to_frame(df, vector_bases=set(), point_bases={"Bodies/target/xpos"})


def test_rotation_filter_apply_to_frame_translates_points_and_recomputes_magnitude():
    """A point base is translated against origin_col before rotating (unlike a vector base), and its stale :m magnitude sibling is recomputed rather than left untouched - translation changes distance-from-origin, so the old magnitude no longer applies."""
    df = pl.DataFrame(
        {
            "Bodies/racket/xquat:x": [0.0],
            "Bodies/racket/xquat:y": [0.0],
            "Bodies/racket/xquat:z": [0.0],
            "Bodies/racket/xquat:w": [1.0],
            "Bodies/racket/xpos:x": [1.0],
            "Bodies/racket/xpos:y": [0.0],
            "Bodies/racket/xpos:z": [0.0],
            "Bodies/target/xpos:x": [5.0],
            "Bodies/target/xpos:y": [0.0],
            "Bodies/target/xpos:z": [0.0],
            "Bodies/target/xpos:m": [5.0],
        }
    )
    f = RotationFilter(
        quat_col="Bodies/racket/xquat", origin_col="Bodies/racket/xpos", invert=True
    )
    rotated = f.apply_to_frame(
        df, vector_bases=set(), point_bases={"Bodies/target/xpos"}
    )

    assert np.allclose(rotated["Bodies/target/xpos:x"].to_numpy(), [4.0])
    assert np.allclose(rotated["Bodies/target/xpos:y"].to_numpy(), [0.0])
    assert np.allclose(rotated["Bodies/target/xpos:z"].to_numpy(), [0.0])
    assert np.allclose(rotated["Bodies/target/xpos:m"].to_numpy(), [4.0])


def test_rotation_filter_compose_to_frame_matches_scipy():
    """Cross-check the hand-rolled Hamilton-product quaternion composition against scipy as a trusted oracle. Quaternions double-cover rotations (q and -q represent the same rotation), so compare via the resulting rotation matrices rather than raw components."""
    from scipy.spatial.transform import Rotation

    rng = np.random.default_rng(1)
    n = 10
    qb = rng.normal(size=(n, 4))
    qb /= np.linalg.norm(qb, axis=1, keepdims=True)
    qa = rng.normal(size=(n, 4))
    qa /= np.linalg.norm(qa, axis=1, keepdims=True)

    df = pl.DataFrame(
        {
            "Bodies/frame/quat:x": qb[:, 0],
            "Bodies/frame/quat:y": qb[:, 1],
            "Bodies/frame/quat:z": qb[:, 2],
            "Bodies/frame/quat:w": qb[:, 3],
            "Bodies/target/quat:x": qa[:, 0],
            "Bodies/target/quat:y": qa[:, 1],
            "Bodies/target/quat:z": qa[:, 2],
            "Bodies/target/quat:w": qa[:, 3],
        }
    )

    rb = Rotation.from_quat(qb)
    ra = Rotation.from_quat(qa)

    for invert in (True, False):
        f = RotationFilter(quat_col="Bodies/frame/quat", origin_col=None, invert=invert)
        composed = f.compose_to_frame(df, quaternion_bases={"Bodies/target/quat"})
        result = composed.select(
            [
                "Bodies/target/quat:x",
                "Bodies/target/quat:y",
                "Bodies/target/quat:z",
                "Bodies/target/quat:w",
            ]
        ).to_numpy()

        expected_rot = (rb.inv() * ra) if invert else (rb * ra)
        actual_rot = Rotation.from_quat(result)
        assert np.allclose(actual_rot.as_matrix(), expected_rot.as_matrix(), atol=1e-10)


def test_rotation_filter_compose_to_frame_missing_quat_col_columns_raises():
    df = pl.DataFrame(
        {
            "Bodies/target/quat:x": [0.0],
            "Bodies/target/quat:y": [0.0],
            "Bodies/target/quat:z": [0.0],
            "Bodies/target/quat:w": [1.0],
        }
    )
    f = RotationFilter(quat_col="Bodies/frame/missing_quat", origin_col=None)
    with pytest.raises(ValueError, match="not found"):
        f.compose_to_frame(df, quaternion_bases={"Bodies/target/quat"})


def test_rotation_filter_compose_to_frame_zero_quaternion_raises():
    df = pl.DataFrame(
        {
            "Bodies/frame/quat:x": [0.0],
            "Bodies/frame/quat:y": [0.0],
            "Bodies/frame/quat:z": [0.0],
            "Bodies/frame/quat:w": [0.0],
            "Bodies/target/quat:x": [0.0],
            "Bodies/target/quat:y": [0.0],
            "Bodies/target/quat:z": [0.0],
            "Bodies/target/quat:w": [1.0],
        }
    )
    f = RotationFilter(quat_col="Bodies/frame/quat", origin_col=None)
    with pytest.raises(ValueError, match="zero, NaN, or infinite"):
        f.compose_to_frame(df, quaternion_bases={"Bodies/target/quat"})


def _frame_and_point_df() -> tuple[pl.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    """A frame rotated +90 degrees about z at (1, 0, 0), and a point at (2, 0, 0)."""
    from scipy.spatial.transform import Rotation

    q = Rotation.from_euler("z", 90, degrees=True).as_quat()  # [x, y, z, w]
    origin = np.array([1.0, 0.0, 0.0])
    point = np.array([2.0, 0.0, 0.0])
    df = pl.DataFrame(
        {
            "Bodies/F/quat:x": [q[0]],
            "Bodies/F/quat:y": [q[1]],
            "Bodies/F/quat:z": [q[2]],
            "Bodies/F/quat:w": [q[3]],
            "Bodies/F/xpos:x": [origin[0]],
            "Bodies/F/xpos:y": [origin[1]],
            "Bodies/F/xpos:z": [origin[2]],
            "Bodies/P/xpos:x": [point[0]],
            "Bodies/P/xpos:y": [point[1]],
            "Bodies/P/xpos:z": [point[2]],
        }
    )
    return df, q, origin, point


def _apply_per_component(f: RotationFilter, df: pl.DataFrame, base: str) -> np.ndarray:
    """Runs apply_with_context on each :x/:y/:z series, as the dojo router does."""
    out = []
    for axis in "xyz":
        col = f"{base}:{axis}"
        result = f.apply_with_context(df[col], df)
        assert result is not None
        out.append(result[0])
    return np.array(out)


def test_rotation_filter_apply_with_context_translates_then_rotates_with_origin():
    """With origin_col set, a position series is expressed relative to the frame origin: R^T (p - o)."""
    from scipy.spatial.transform import Rotation

    df, q, origin, point = _frame_and_point_df()
    f = RotationFilter(
        quat_col="Bodies/F/quat", origin_col="Bodies/F/xpos", invert=True
    )

    actual = _apply_per_component(f, df, "Bodies/P/xpos")

    expected = Rotation.from_quat(q).inv().apply(point - origin)
    assert np.allclose(actual, expected, atol=1e-10)


def test_rotation_filter_apply_with_context_only_rotates_without_origin():
    """Without origin_col the same series is only rotated, keeping its world-frame origin."""
    from scipy.spatial.transform import Rotation

    df, q, _origin, point = _frame_and_point_df()
    f = RotationFilter(quat_col="Bodies/F/quat", origin_col=None, invert=True)

    actual = _apply_per_component(f, df, "Bodies/P/xpos")

    assert np.allclose(actual, Rotation.from_quat(q).inv().apply(point), atol=1e-10)


# --- Pydantic Validation Tests ---


def test_pydantic_constraints():
    # Test Derivative dt > 0
    with pytest.raises(ValidationError):
        DerivativeFilter(dt=0)

    # Test Clip min < max
    with pytest.raises(ValidationError):
        ClipFilter(min=10, max=5)

    # Test Wrap lb < ub
    with pytest.raises(ValidationError):
        WrapFilter(lb=np.pi, ub=-np.pi)


def test_filter_adapter_parsing():
    from mujoco_mojo.utils.filters.filters import filter_adapter

    # Simulate a JSON payload from the frontend
    payload = {
        "Bodies/racket/xvelr:y": [
            {"type": "scale", "factor": 10.0},
            {"type": "absolute_value"},
        ]
    }
    stack_dict = filter_adapter.validate_python(payload)
    assert len(stack_dict["Bodies/racket/xvelr:y"]) == 2
    assert isinstance(stack_dict["Bodies/racket/xvelr:y"][0], ScaleFilter)


def test_filter_chaining_integrity(signal_df: MojoDataFrame):
    """Verifies that multiple filters can be stacked without side effects."""
    # Recipe: Offset by 10, then zero it out (should return original ramp)
    stack: list[AnyFilter] = [ScaleFilter(factor=1.0, offset=10.0), TaringFilter()]

    expr = pl.col("val")
    for f in stack:
        expr = f.apply(expr)

    result = signal_df.select(expr)["val"].to_list()
    assert result == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_derivative_integral_roundtrip():
    """Verifies numerical consistency of calculus filters."""
    # Constant signal
    df = pl.DataFrame({"x": [1.0] * 100})
    dt = 0.01

    # Integral of 1.0 over 1 second is a ramp to 1.0
    # Derivative of that ramp should be 1.0
    df_calc = df.with_columns(
        [
            IntegralFilter(dt=dt).apply(pl.col("x")).alias("int"),
        ]
    ).with_columns([DerivativeFilter(dt=dt).apply(pl.col("int")).alias("roundtrip")])

    # Exclude the first few samples where initialization happens
    assert np.allclose(df_calc["roundtrip"][5:], 1.0)


def test_null_handling_persistence():
    """Ensures filters don't crash when encountering nulls/NaNs."""
    df = pl.DataFrame({"x": [1.0, None, 3.0, np.nan, 5.0]})
    f = ScaleFilter(factor=2.0)

    result = df.select(f.apply(pl.col("x")))["x"].to_list()
    # Pydantic/Polars should preserve the null structure
    assert result[1] is None
    assert np.isnan(result[3])


def test_high_pass_filter(signal_df: MojoDataFrame):
    # If alpha is very low, the LowPass part captures the DC offset.
    # Subtracting it should leave us near zero for a constant signal.
    df = pl.DataFrame({"x": [10.0] * 20})  # Constant signal
    f = HighPassFilter(alpha=0.01)
    result = df.select(f.apply(pl.col("x")))["x"].to_list()

    # After initial settling, it should be near 0.0
    assert np.allclose(result[-1], 0.0, atol=1e-2)


def test_rolling_mean_filter(signal_df: MojoDataFrame):
    # window=3, center=True on [0, 1, 2, 3, 4]
    # At index 2 (val=2.0), window is [1, 2, 3], mean is 2.0
    f = RollingMeanFilter(window=3, center=True)
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()

    assert result[2] == 2.0
    assert len(result) == 5


def test_rolling_median_filter():
    # Median is great for removing "salt and pepper" noise
    df = pl.DataFrame({"x": [1.0, 1.0, 100.0, 1.0, 1.0]})
    f = RollingMedianFilter(window=3)
    result = df.select(f.apply(pl.col("x")))["x"].to_list()

    # The 100.0 spike should be replaced by the median of [1, 100, 1] -> 1.0
    assert result[2] == 1.0


def test_window_larger_than_data():
    df = pl.DataFrame({"x": [1.0, 2.0]})
    # Window of 10 on 2 rows of data
    f = RollingMeanFilter(window=10)
    result = df.select(f.apply(pl.col("x")))["x"].to_list()

    # Depending on Polars version, this usually returns Nulls
    # unless min_periods is set. Good to know your baseline.
    assert len(result) == 2


def test_savitzky_golay_peak_preservation():
    """Verifies SG filter preserves peaks better than Rolling Mean."""
    # A signal with a sharp peak at index 5
    data = [0.0, 0.0, 0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    df = pl.DataFrame({"x": data})

    # Savitzky-Golay
    sg = SavitzkyGolayFilter(window=5, order=2)
    # Rolling Mean for comparison
    rm = RollingMeanFilter(window=5, center=True)

    results = df.with_columns(
        [sg.apply(pl.col("x")).alias("sg"), rm.apply(pl.col("x")).alias("rm")]
    )

    # The original peak was 10.0.
    # Rolling Mean window of 5 will average [0, 0, 10, 0, 0] / 5 = 2.0
    # Savitzky-Golay will attempt to fit a parabola, keeping the peak higher.
    peak_sg = results["sg"][5]
    peak_rm = results["rm"][5]

    assert peak_sg > peak_rm
    assert peak_rm == 2.0
    # Note: SG results will vary based on order, but it will always be > 2.0 here.


def test_savitzky_golay_validation():
    """Ensures window/order logic is enforced."""
    # Even window should fail
    with pytest.raises(ValidationError):
        SavitzkyGolayFilter(window=10, order=2)

    # Order >= window should fail
    with pytest.raises(ValidationError):
        SavitzkyGolayFilter(window=5, order=5)


def test_unit_filter_basic_conversion(signal_df: MojoDataFrame):
    """Verifies standard scaling conversion (e.g., meters to millimeters)."""
    # 1.0 m -> 1000.0 mm
    f = UnitFilter(from_unit="m", to_unit="mm")
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    assert result == [0.0, 1000.0, 2000.0, 3000.0, 4000.0]


def test_unit_filter_rotation_conversion(signal_df: MojoDataFrame):
    """Verifies angular conversion (radians to degrees)."""
    f = UnitFilter(from_unit="rad", to_unit="deg")
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    expected = [np.degrees(x) for x in [0.0, 1.0, 2.0, 3.0, 4.0]]
    assert np.allclose(result, expected)


def test_unit_filter_offset_conversion():
    """Verifies affine transformations with offsets (e.g., Celsius to Kelvin)."""
    df = pl.DataFrame({"temp_c": [0.0, 100.0]})
    # Pint uses 'degC' for Celsius and 'K' for Kelvin
    f = UnitFilter(from_unit="degC", to_unit="K")
    result = df.select(f.apply(pl.col("temp_c")))["temp_c"].to_list()

    # Freezing point check (273.15) and boiling point check (373.15)
    assert np.allclose(result, [273.15, 373.15])


def test_unit_filter_dimensionality_mismatch():
    """Ensures Pydantic prevents incompatible unit conversions (e.g., Length to Time)."""
    # Length to Time should raise ValueError via model_validator
    with pytest.raises(ValidationError) as exc:
        UnitFilter(from_unit="m", to_unit="s")
    assert "Incompatible unit" in str(exc.value)

    # Angle to Force
    with pytest.raises(ValidationError):
        UnitFilter(from_unit="rad", to_unit="pound_force")


def test_unit_filter_undefined_unit():
    """Ensures Pydantic catches nonsense unit strings that Pint cannot parse."""
    with pytest.raises(ValidationError) as exc:
        UnitFilter(from_unit="rad", to_unit="not_a_physical_unit")
    assert "Unknown unit definition" in str(exc.value)


def test_unit_filter_custom_string_fallback():
    """Verifies that strings outside the Literal list but valid in Pint still work."""
    # 'parsec' isn't in our AngleUnit/LenUnit/etc literals, but Pint knows it
    f = UnitFilter(from_unit="m", to_unit="parsec")
    # approx 1 parsec in meters
    df = pl.DataFrame({"x": [3.086e16]})
    result = df.select(f.apply(pl.col("x")))["x"][0]

    assert np.allclose(result, 1.0, rtol=1e-3)


# --- Statistics Tests ---


def test_max_filter():
    # Statistics filters reduce the signal to one value, broadcast to the
    # original length via with_columns (the same mechanism the router/lab
    # executor use to apply filters in place).
    df = pl.DataFrame({"x": [1.0, 5.0, 3.0, -2.0]})
    result = df.with_columns(MaxFilter().apply(pl.col("x")))["x"].to_list()

    assert result == [5.0, 5.0, 5.0, 5.0]


def test_min_filter():
    df = pl.DataFrame({"x": [1.0, 5.0, 3.0, -2.0]})
    result = df.with_columns(MinFilter().apply(pl.col("x")))["x"].to_list()

    assert result == [-2.0, -2.0, -2.0, -2.0]


def test_mean_filter():
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
    result = df.with_columns(MeanFilter().apply(pl.col("x")))["x"].to_list()

    assert result == [2.5, 2.5, 2.5, 2.5]


def test_median_filter():
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0, 4.0]})
    result = df.with_columns(MedianFilter().apply(pl.col("x")))["x"].to_list()

    assert result == [2.5, 2.5, 2.5, 2.5]


def test_mode_filter():
    df = pl.DataFrame({"x": [1.0, 2.0, 2.0, 3.0]})
    result = df.with_columns(ModeFilter().apply(pl.col("x")))["x"].to_list()

    assert result == [2.0, 2.0, 2.0, 2.0]


def test_standard_deviation_filter():
    # Polars uses the sample standard deviation (ddof=1) by default.
    df = pl.DataFrame({"x": [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]})
    result = df.with_columns(StandardDeviationFilter().apply(pl.col("x")))[
        "x"
    ].to_list()

    expected = float(np.std(df["x"].to_numpy(), ddof=1))
    assert np.allclose(result, [expected] * 8)


def test_first_filter():
    df = pl.DataFrame({"x": [1.0, 5.0, 3.0, -2.0]})
    result = df.with_columns(FirstFilter().apply(pl.col("x")))["x"].to_list()

    assert result == [1.0, 1.0, 1.0, 1.0]


def test_last_filter():
    df = pl.DataFrame({"x": [1.0, 5.0, 3.0, -2.0]})
    result = df.with_columns(LastFilter().apply(pl.col("x")))["x"].to_list()

    assert result == [-2.0, -2.0, -2.0, -2.0]


def test_sort_filter():
    df = pl.DataFrame({"x": [1.0, 5.0, 3.0, -2.0]})

    ascending = df.with_columns(SortFilter().apply(pl.col("x")))["x"].to_list()
    assert ascending == [-2.0, 1.0, 3.0, 5.0]

    descending = df.with_columns(SortFilter(descending=True).apply(pl.col("x")))[
        "x"
    ].to_list()
    assert descending == [5.0, 3.0, 1.0, -2.0]
