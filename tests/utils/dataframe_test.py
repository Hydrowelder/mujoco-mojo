from pathlib import Path
from typing import cast

import numpy as np
import polars as pl
import pytest

from mujoco_mojo.typing import BodyName, SignalCategory
from mujoco_mojo.utils.dataframe import MojoDataFrame
from mujoco_mojo.utils.defaults import TIME_COLUMN_NAME
from mujoco_mojo.utils.filters import AnyFilter, ScaleFilter


@pytest.fixture
def sample_data():
    """Generates a representative telemetry dataset for testing."""
    data = {
        TIME_COLUMN_NAME: [0.0, 0.1, 0.2],
        "Bodies/racket/xpos:x": [1.0, 1.1, 1.2],
        "Bodies/racket/xpos:y": [0.0, 0.1, 0.2],
        "Bodies/racket/xpos:z": [0.0, 0.0, 0.0],
        "Bodies/racket/xiquat:x": [0.0, 0.0, 0.0],  # Triplet
        "Bodies/racket/xiquat:y": [0.0, 0.0, 0.0],
        "Bodies/racket/xiquat:z": [0.0, 0.0, 0.0],
        "Bodies/racket/xiquat:w": [1.0, 1.0, 1.0],
        "Joints/hinge_1/qpos": [0.5, 0.6, 0.7],
        "Bodies/racket/nutation_deg": [10.0, 11.0, 12.0],
        "Sensors/gyro/data:x": [0.1, 0.2, 0.3],  # Another triplet
        "Sensors/gyro/data:y": [0.1, 0.2, 0.3],
        "Sensors/gyro/data:z": [0.1, 0.2, 0.3],
    }
    return pl.DataFrame(data)


# --- IO & Initialization Tests ---


def test_from_metadata(tmp_path: Path, sample_data: MojoDataFrame):
    """Verifies that from_metadata reads 0 rows but preserves schema."""
    path = tmp_path / "test.parquet"
    sample_data.write_parquet(path)

    meta_df = MojoDataFrame.from_metadata(path)
    assert isinstance(meta_df, pl.DataFrame)
    assert meta_df.height == 0
    assert len(meta_df.columns) == len(sample_data.columns)


def test_from_columns(tmp_path: Path, sample_data: MojoDataFrame):
    """Verifies that only specific columns are loaded."""
    path = tmp_path / "test.parquet"
    sample_data.write_parquet(path)

    cols = [TIME_COLUMN_NAME, "Bodies/racket/xpos:x"]
    col_df = MojoDataFrame.read_parquet(path, columns=cols)
    assert col_df.columns == cols
    assert col_df.height == 3


# --- Selection Logic Tests ---


def test_select_category(sample_data: MojoDataFrame):
    """Tests filtering by top-level SignalCategory."""
    bodies = sample_data.mojo.select_category(SignalCategory.BODIES)
    assert all(c.startswith("Bodies/") for c in bodies.columns)
    assert "Joints/hinge_1/qpos" not in bodies.columns


def test_select_name(sample_data: MojoDataFrame):
    """Tests filtering by object name across categories."""
    racket = sample_data.mojo.select_name("racket")
    # Should include xpos, xiquat, and nutation
    assert "Bodies/racket/xpos:x" in racket.columns
    assert "Bodies/racket/nutation_deg" in racket.columns
    assert "Joints/hinge_1/qpos" not in racket.columns


def test_select_attribute(sample_data: MojoDataFrame):
    """Tests selecting a specific attribute (vector component) across channels."""
    x_attr = sample_data.mojo.select_attribute("x")
    assert x_attr.columns == [
        "Bodies/racket/xpos:x",
        "Bodies/racket/xiquat:x",
        "Sensors/gyro/data:x",
    ]

    # columns with no ':attr' suffix are not matched
    nutation = sample_data.mojo.select_attribute("nutation_deg")
    assert nutation.columns == []


def test_select_body(sample_data: MojoDataFrame):
    """Tests the specific body selection helper."""
    body_df = sample_data.mojo.select_body(BodyName("racket"))
    assert "Bodies/racket/xpos:x" in body_df.columns
    assert "Joints/hinge_1/qpos" not in body_df.columns


# --- Discovery & Manifest Tests ---


def test_discovery_properties(sample_data: MojoDataFrame):
    """Verifies internal identification of triplets and quaternions."""
    # Bases
    assert "Bodies/racket/xpos" in sample_data.mojo.rotatable_bases
    assert "Bodies/racket/xiquat" in sample_data.mojo.quaternion_bases

    # Ensure scalars are excluded from rotatable_bases
    assert "Bodies/racket/nutation_deg" not in sample_data.mojo.rotatable_bases

    # Expanded columns
    assert "Bodies/racket/xpos:x" in sample_data.mojo.rotatable_columns
    assert "Bodies/racket/xiquat:w" in sample_data.mojo.quaternion_columns


def test_get_manifest(sample_data: MojoDataFrame):
    """Ensures the manifest dictionary matches frontend expectations."""
    manifest = sample_data.mojo.get_manifest()
    assert manifest["all"] == sample_data.columns
    assert "Bodies/racket/xpos" in manifest["rotatable_vectors"]
    assert "Bodies/racket/xiquat" in manifest["available_quats"]


# --- Physics Transformation Tests ---


def test_with_rotation_identity(sample_data: MojoDataFrame):
    """Rotating by identity [0,0,0,1] should result in zero change."""
    # Our sample_data quat is already identity
    rotated = sample_data.mojo.with_rotation("Bodies/racket/xiquat", invert=True)

    for col in ["Bodies/racket/xpos:x", "Bodies/racket/xpos:y", "Bodies/racket/xpos:z"]:
        assert np.allclose(sample_data[col].to_numpy(), rotated[col].to_numpy())


def test_with_rotation_single_row_buffer_is_writable():
    """
    Regression test: with_rotation must work on a single-row DataFrame.

    Polars' to_numpy() defaults to writable=False and returns a zero-copy, read-only view
    when the selected columns are stored contiguously as a single chunk, the common case for
    a freshly-constructed single-row frame. with_rotation previously passed that view straight
    to scipy, which raised `ValueError: buffer source array is read-only`. The current
    implementation does pure numpy arithmetic (no third-party calls requiring a writable
    buffer), so this is now structurally prevented, but the test is kept as a guard.
    """
    single_row = MojoDataFrame.from_dict(
        {
            "Bodies/racket/xpos:x": [1.0],
            "Bodies/racket/xpos:y": [0.0],
            "Bodies/racket/xpos:z": [0.0],
            "Bodies/racket/xiquat:x": [0.0],
            "Bodies/racket/xiquat:y": [0.0],
            "Bodies/racket/xiquat:z": [0.0],
            "Bodies/racket/xiquat:w": [1.0],
        }
    )

    rotated = single_row.mojo.with_rotation("Bodies/racket/xiquat", invert=False)

    assert rotated.height == 1
    assert np.allclose(rotated["Bodies/racket/xpos:x"].to_numpy(), [1.0])


def test_with_rotation_matches_scipy():
    """Cross-check the hand-rolled quaternion rotation against scipy as a trusted oracle."""
    from scipy.spatial.transform import Rotation

    rng = np.random.default_rng(0)
    n = 25
    raw_quats = rng.normal(size=(n, 4))
    quats = raw_quats / np.linalg.norm(raw_quats, axis=1, keepdims=True)
    vecs = rng.normal(size=(n, 3))

    df = MojoDataFrame.from_dict(
        {
            "Bodies/racket/xpos:x": vecs[:, 0],
            "Bodies/racket/xpos:y": vecs[:, 1],
            "Bodies/racket/xpos:z": vecs[:, 2],
            "Bodies/racket/xiquat:x": quats[:, 0],
            "Bodies/racket/xiquat:y": quats[:, 1],
            "Bodies/racket/xiquat:z": quats[:, 2],
            "Bodies/racket/xiquat:w": quats[:, 3],
        }
    )

    for invert in (False, True):
        transformer = Rotation.from_quat(quats)
        if invert:
            transformer = transformer.inv()
        expected = transformer.apply(vecs)

        rotated = df.mojo.with_rotation("Bodies/racket/xiquat", invert=invert)
        actual = rotated.select(
            ["Bodies/racket/xpos:x", "Bodies/racket/xpos:y", "Bodies/racket/xpos:z"]
        ).to_numpy()

        assert np.allclose(actual, expected, atol=1e-10)


def test_with_rotation_does_not_mutate_source(sample_data: MojoDataFrame):
    """Regression test: with_rotation must not write into the source DataFrame's backing store."""
    pos_cols = ["Bodies/racket/xpos:x", "Bodies/racket/xpos:y", "Bodies/racket/xpos:z"]
    before = {col: sample_data[col].to_numpy().copy() for col in pos_cols}

    sample_data.mojo.with_rotation("Bodies/racket/xiquat", invert=False)

    for col in pos_cols:
        assert np.array_equal(sample_data[col].to_numpy(), before[col])


def test_with_rotation_90deg_z(sample_data: MojoDataFrame):
    """Tests a 90-degree Z-axis rotation."""
    # quat for 90deg about Z: [0, 0, sin(45), cos(45)]
    q90 = [0.0, 0.0, np.sin(np.pi / 4), np.cos(np.pi / 4)]

    # Create data with 90deg rotation
    rows = sample_data.height
    df_q = cast(
        MojoDataFrame,
        sample_data.with_columns(
            [
                pl.Series("Bodies/racket/xiquat:x", [q90[0]] * rows),
                pl.Series("Bodies/racket/xiquat:y", [q90[1]] * rows),
                pl.Series("Bodies/racket/xiquat:z", [q90[2]] * rows),
                pl.Series("Bodies/racket/xiquat:w", [q90[3]] * rows),
            ]
        ),
    )

    # Rotate World [1, 0, 0] by 90deg Z (invert=False) -> [0, 1, 0]
    rotated = df_q.mojo.with_rotation("Bodies/racket/xiquat", invert=False)

    v_x = rotated["Bodies/racket/xpos:x"][0]
    v_y = rotated["Bodies/racket/xpos:y"][0]

    assert np.allclose(v_x, 0.0, atol=1e-7)
    assert np.allclose(v_y, 1.0, atol=1e-7)


# --- Filter Logic Tests ---


def test_with_filters_omit_time(sample_data: MojoDataFrame):
    """Ensures filters skip the time column by default using real ScaleFilter."""
    # Factor 10, Offset 0 (Linear transform)
    filter_stack: list[AnyFilter] = [ScaleFilter(factor=10.0, offset=0.0)]

    filtered = sample_data.mojo.with_filters(filter_stack, omit_time=True)

    # Time should be untouched (0.1 remains 0.1)
    assert filtered[TIME_COLUMN_NAME][1] == 0.1
    # Data should be scaled (1.0 * 10 = 10.0)
    assert filtered["Bodies/racket/xpos:x"][0] == 10.0


def test_with_filter_map(sample_data: MojoDataFrame):
    """Tests applying specific real filters to specific columns."""
    filter_map: dict[str, list[AnyFilter]] = {
        "Joints/hinge_1/qpos": [ScaleFilter(factor=1.0, offset=1.0)],
        "Bodies/racket/nutation_deg": [
            ScaleFilter(factor=1.0, offset=1.0),
            ScaleFilter(factor=1.0, offset=1.0),
        ],
    }

    mapped = sample_data.mojo.with_filter_map(filter_map)

    # Base 0.5 + 1.0 = 1.5
    assert mapped["Joints/hinge_1/qpos"][0] == 1.5
    # Base 10.0 + 1.0 + 1.0 = 12.0
    assert mapped["Bodies/racket/nutation_deg"][0] == 12.0
    # Unmapped columns should be identical
    assert mapped["Bodies/racket/xpos:x"][0] == 1.0
