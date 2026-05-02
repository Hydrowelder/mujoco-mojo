import numpy as np
import polars as pl
import pytest
from pydantic import ValidationError

from mujoco_mojo.utils.dataframe import MojoFrame
from mujoco_mojo.utils.filters import (
    AbsoluteValueFilter,
    AnyFilter,
    ClipFilter,
    DeadbandFilter,
    DerivativeFilter,
    HighPassFilter,
    IntegralFilter,
    LowPassFilter,
    MedianFilter,
    NormalizeFilter,
    RollingMeanFilter,
    SavitzkyGolayFilter,
    ScaleFilter,
    WrapFilter,
    ZeroingFilter,
)


@pytest.fixture
def signal_df():
    """A basic linear ramp for testing deterministic filters."""
    return pl.DataFrame(
        {"val": [0.0, 1.0, 2.0, 3.0, 4.0], "noise": [-0.001, 0.005, 0.5, -0.5, 0.001]}
    )


# --- Math & Basic Transformation Tests ---


def test_scale_filter(signal_df: MojoFrame):
    f = ScaleFilter(factor=2.0, offset=1.0)
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    # Expected: (x * 2) + 1 -> [1, 3, 5, 7, 9]
    assert result == [1.0, 3.0, 5.0, 7.0, 9.0]


def test_absolute_value_filter():
    df = pl.DataFrame({"x": [-1.0, 0.0, 1.0]})
    f = AbsoluteValueFilter()
    result = df.select(f.apply(pl.col("x")))["x"].to_list()
    assert result == [1.0, 0.0, 1.0]


def test_zeroing_filter(signal_df: MojoFrame):
    # Offsets the entire series so the first value is 0
    # Our 'val' already starts at 0, so let's use a shifted version
    df = signal_df.with_columns(pl.col("val") + 10.0)
    f = ZeroingFilter()
    result = df.select(f.apply(pl.col("val")))["val"].to_list()
    assert result == [0.0, 1.0, 2.0, 3.0, 4.0]


# --- Calculus & Signal Processing Tests ---


def test_derivative_filter(signal_df: MojoFrame):
    # Ramp 0, 1, 2, 3, 4 with dt=1.0 should have derivative of 1.0
    f = DerivativeFilter(dt=1.0)
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    # First value is 0 due to .fill_null(0)
    assert result == [0.0, 1.0, 1.0, 1.0, 1.0]


def test_integral_filter(signal_df: MojoFrame):
    # Integral of [0, 1, 2] with dt=1.0 is cumsum [0, 1, 3]
    f = IntegralFilter(dt=1.0)
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    assert result == [0.0, 1.0, 3.0, 6.0, 10.0]


def test_low_pass_filter(signal_df: MojoFrame):
    # Alpha=1.0 should return the original signal (no smoothing)
    f = LowPassFilter(alpha=1.0)
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    assert result == signal_df["val"].to_list()


def test_deadband_filter(signal_df: MojoFrame):
    f = DeadbandFilter(threshold=0.1)
    result = signal_df.select(f.apply(pl.col("noise")))["noise"].to_list()
    # noise: [-0.001, 0.005, 0.5, -0.5, 0.001]
    # Expected: [0, 0, 0.5, -0.5, 0]
    assert result == [0.0, 0.0, 0.5, -0.5, 0.0]


# --- Boundary & Circular Tests ---


def test_clip_filter(signal_df: MojoFrame):
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


def test_normalize_filter(signal_df: MojoFrame):
    f = NormalizeFilter()
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()
    assert np.allclose(result[0], 0.0)
    assert np.allclose(result[-1], 1.0)


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
    from mujoco_mojo.utils.filters import filter_adapter

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


def test_filter_chaining_integrity(signal_df: MojoFrame):
    """Verifies that multiple filters can be stacked without side effects."""
    # Recipe: Offset by 10, then zero it out (should return original ramp)
    stack: list[AnyFilter] = [ScaleFilter(factor=1.0, offset=10.0), ZeroingFilter()]

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


def test_high_pass_filter(signal_df: MojoFrame):
    # If alpha is very low, the LowPass part captures the DC offset.
    # Subtracting it should leave us near zero for a constant signal.
    df = pl.DataFrame({"x": [10.0] * 20})  # Constant signal
    f = HighPassFilter(alpha=0.01)
    result = df.select(f.apply(pl.col("x")))["x"].to_list()

    # After initial settling, it should be near 0.0
    assert np.allclose(result[-1], 0.0, atol=1e-2)


def test_rolling_mean_filter(signal_df: MojoFrame):
    # window=3, center=True on [0, 1, 2, 3, 4]
    # At index 2 (val=2.0), window is [1, 2, 3], mean is 2.0
    f = RollingMeanFilter(window=3, center=True)
    result = signal_df.select(f.apply(pl.col("val")))["val"].to_list()

    assert result[2] == 2.0
    assert len(result) == 5


def test_median_filter():
    # Median is great for removing "salt and pepper" noise
    df = pl.DataFrame({"x": [1.0, 1.0, 100.0, 1.0, 1.0]})
    f = MedianFilter(window=3)
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
