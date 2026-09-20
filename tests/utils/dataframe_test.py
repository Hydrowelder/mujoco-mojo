from pathlib import Path

import numpy as np
import polars as pl
import pytest

from mujoco_mojo.typing import BodyName, SignalCategory
from mujoco_mojo.utils.column import Column
from mujoco_mojo.utils.dataframe import MojoDataFrame, read_column_metadata
from mujoco_mojo.utils.defaults import TIME_COLUMN_NAME
from mujoco_mojo.utils.filters import AnyFilter, ScaleFilter
from mujoco_mojo.utils.signal_metadata import ColumnMetadata, TransformType


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


def test_read_column_metadata_returns_models(tmp_path: Path):
    import json

    path = tmp_path / "meta.parquet"
    pl.DataFrame({"a": [1.0]}).write_parquet(
        path,
        metadata={
            "column_metadata": json.dumps(
                {"a": {"unit": "meter", "transform_type": "point", "note": "x"}}
            )
        },
    )

    meta = read_column_metadata(path)
    assert meta["a"] == ColumnMetadata.model_validate(
        {"unit": "meter", "transform_type": "point", "note": "x"}
    )


def test_read_column_metadata_still_loads_an_invalid_entry(tmp_path: Path):
    """A file written by another version with a unit Pint rejects must still open."""
    import json

    path = tmp_path / "meta.parquet"
    pl.DataFrame({"a": [1.0], "b": [2.0]}).write_parquet(
        path,
        metadata={
            "column_metadata": json.dumps(
                {"a": {"unit": "not_a_unit"}, "b": {"unit": "meter"}}
            )
        },
    )

    meta = read_column_metadata(path)
    assert meta["a"].unit == "not_a_unit"
    assert meta["b"].unit == "meter"


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


def test_select_body_includes_scalar_channels():
    """A body's scalar channels (`Bodies/box:ke_trans`) belong to it as much as its vector groups."""
    df = MojoDataFrame.from_dict(
        {
            "Bodies/box/xpos:x": [1.0],
            "Bodies/box:ke_trans": [2.0],
            "Bodies/box2:ke_trans": [3.0],
            "Sites/box/xpos:x": [4.0],
        }
    )
    assert df.mojo.select_body(BodyName("box")).columns == [
        "Bodies/box/xpos:x",
        "Bodies/box:ke_trans",
    ]


def test_typed_selectors_match_names_literally():
    """Object names are compared as parts, so regex characters in a name do not match other objects."""
    df = MojoDataFrame.from_dict(
        {"Bodies/arm.1/xpos:x": [1.0], "Bodies/armX1/xpos:x": [2.0]}
    )
    assert df.mojo.select_body(BodyName("arm.1")).columns == ["Bodies/arm.1/xpos:x"]

    spiky = MojoDataFrame.from_dict(
        {"Bodies/(arm) #1+2/xpos:x": [1.0], "Bodies/(arm) #1/xpos:x": [2.0]}
    )
    assert spiky.mojo.select_body(BodyName("(arm) #1+2")).columns == [
        "Bodies/(arm) #1+2/xpos:x"
    ]


def test_columns_parses_the_frame_and_skips_free_form_names(sample_data: MojoDataFrame):
    df = MojoDataFrame.from_dict(
        {TIME_COLUMN_NAME: [0.0], "Bodies/a/xpos:x": [1.0], "My Output//x": [2.0]}
    )
    assert df.mojo.columns == [
        Column(category=TIME_COLUMN_NAME),
        Column(category="Bodies", subgroups=("a", "xpos"), attr="x"),
    ]


def test_select_accepts_columns_and_strings(sample_data: MojoDataFrame):
    by_string = sample_data.mojo.select("Bodies/racket/xpos")
    assert by_string.columns == [
        "Bodies/racket/xpos:x",
        "Bodies/racket/xpos:y",
        "Bodies/racket/xpos:z",
    ]
    by_column = sample_data.mojo.select(
        Column(category="Bodies", subgroups=("racket", "xpos"))
    )
    assert by_column.columns == by_string.columns


def test_select_takes_several_columns_and_an_attr_only_column(
    sample_data: MojoDataFrame,
):
    every_x = sample_data.mojo.select(Column(category="Bodies", attr="x"))
    assert every_x.columns == ["Bodies/racket/xpos:x", "Bodies/racket/xiquat:x"]
    both = sample_data.mojo.select(TIME_COLUMN_NAME, "Sensors/gyro")
    assert both.columns == [
        TIME_COLUMN_NAME,
        "Sensors/gyro/data:x",
        "Sensors/gyro/data:y",
        "Sensors/gyro/data:z",
    ]


def test_select_with_no_match_is_empty(sample_data: MojoDataFrame):
    assert sample_data.mojo.select("Bodies/nothing").columns == []


def _pose_frame() -> MojoDataFrame:
    return MojoDataFrame.from_dict(
        {
            TIME_COLUMN_NAME: [0.0, 0.1],
            "Sites/A/xpos:x": [1.0, 4.0],
            "Sites/A/xpos:y": [2.0, 5.0],
            "Sites/A/xpos:z": [3.0, 6.0],
            # deliberately not in w, x, y, z order: columns are read by name
            "Sites/A/quat:x": [0.0, 0.0],
            "Sites/A/quat:y": [0.0, 0.0],
            "Sites/A/quat:z": [0.0, 1.0],
            "Sites/A/quat:w": [1.0, 0.0],
        }
    )


def test_pose_at_reads_one_row_by_column_name():
    first = _pose_frame().mojo.pose_at(0, "Sites/A")
    assert np.allclose(first.pos, [1.0, 2.0, 3.0])
    assert np.allclose(first.quat, [1.0, 0.0, 0.0, 0.0])  # w, x, y, z

    second = _pose_frame().mojo.pose_at(1, Column(category="Sites", subgroups=("A",)))
    assert np.allclose(second.pos, [4.0, 5.0, 6.0])
    assert np.allclose(second.quat, [0.0, 0.0, 0.0, 1.0])


def test_pose_at_raises_naming_the_missing_columns():
    df = _pose_frame().drop("Sites/A/quat:w", "Sites/A/xpos:z")
    with pytest.raises(ValueError, match="Sites/A/quat:w") as excinfo:
        df.mojo.pose_at(0, "Sites/A")
    assert "Sites/A/xpos:z" in str(excinfo.value)
    assert "Sites/A/xpos:x" not in str(excinfo.value)


def test_pose_arrays_returns_the_whole_trajectory():
    pos, quat = _pose_frame().mojo.pose_arrays("Sites/A")
    assert pos.shape == (2, 3)
    assert quat.shape == (2, 4)
    assert np.allclose(pos, [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    assert np.allclose(quat, [[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]])


def test_pose_arrays_raises_naming_the_missing_columns():
    with pytest.raises(ValueError, match="Sites/B/xpos:x"):
        _pose_frame().mojo.pose_arrays("Sites/B")


def test_pose_at_matches_pose_arrays():
    df = _pose_frame()
    pos, quat = df.mojo.pose_arrays("Sites/A")
    for i in range(df.height):
        pose = df.mojo.pose_at(i, "Sites/A")
        assert np.allclose(pose.pos, pos[i])
        assert np.allclose(pose.quat, quat[i])


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


def test_change_frame_raises_when_untagged():
    """change_frame refuses to guess: any rotatable/quaternion column without a transform_type tag raises, rather than silently applying the wrong transform."""
    df = MojoDataFrame.from_dict(
        {
            "Bodies/frame/xpos:x": [1.0],
            "Bodies/frame/xpos:y": [0.0],
            "Bodies/frame/xpos:z": [0.0],
            "Bodies/frame/quat:x": [0.0],
            "Bodies/frame/quat:y": [0.0],
            "Bodies/frame/quat:z": [0.0],
            "Bodies/frame/quat:w": [1.0],
            "Bodies/target/xpos:x": [1.0],
            "Bodies/target/xpos:y": [0.0],
            "Bodies/target/xpos:z": [0.0],
        }
    )
    meta = {
        "Bodies/frame/xpos:x": ColumnMetadata(transform_type=TransformType.POINT),
        "Bodies/frame/quat:w": ColumnMetadata(transform_type=TransformType.QUATERNION),
        # "Bodies/target/xpos" is deliberately left untagged
    }
    with pytest.raises(ValueError, match="transform_type"):
        df.mojo.change_frame(
            "Bodies/frame/quat", "Bodies/frame/xpos", column_metadata=meta
        )


def test_change_frame_leaves_scalar_tagged_groups_untouched():
    """A group named `:x/:y/:z` (or `:w/:x/:y/:z`) that is not a vector can be tagged `scalar`: change_frame skips it instead of raising or rotating it, while still transforming the tagged point."""
    half = float(np.sqrt(0.5))
    df = MojoDataFrame.from_dict(
        {
            # a frame rotated 90 degrees about z, at the origin
            "Bodies/frame/xpos:x": [0.0],
            "Bodies/frame/xpos:y": [0.0],
            "Bodies/frame/xpos:z": [0.0],
            "Bodies/frame/quat:w": [half],
            "Bodies/frame/quat:x": [0.0],
            "Bodies/frame/quat:y": [0.0],
            "Bodies/frame/quat:z": [half],
            "Bodies/target/xpos:x": [1.0],
            "Bodies/target/xpos:y": [0.0],
            "Bodies/target/xpos:z": [0.0],
            # independent scalars that only happen to be named x/y/z
            "Custom/euler:x": [0.1],
            "Custom/euler:y": [0.2],
            "Custom/euler:z": [0.3],
            # four independent scalars named like a quaternion
            "Custom/gains:w": [1.0],
            "Custom/gains:x": [2.0],
            "Custom/gains:y": [3.0],
            "Custom/gains:z": [4.0],
        }
    )
    meta = {
        "Bodies/frame/xpos:x": ColumnMetadata(transform_type=TransformType.POINT),
        "Bodies/frame/quat:w": ColumnMetadata(transform_type=TransformType.QUATERNION),
        "Bodies/target/xpos:x": ColumnMetadata(transform_type=TransformType.POINT),
        "Custom/euler:x": TransformType.SCALAR.metadata,
        "Custom/gains:w": TransformType.SCALAR.metadata,
    }
    out = df.mojo.change_frame(
        "Bodies/frame/quat", "Bodies/frame/xpos", column_metadata=meta
    )

    # the target point was rotated by the inverse of the frame (+90 deg about z)
    assert out["Bodies/target/xpos:x"][0] == pytest.approx(0.0, abs=1e-12)
    assert out["Bodies/target/xpos:y"][0] == pytest.approx(-1.0)
    for col in ("Custom/euler:x", "Custom/euler:y", "Custom/euler:z"):
        assert out[col][0] == df[col][0]
    for col in ("Custom/gains:w", "Custom/gains:x", "Custom/gains:y", "Custom/gains:z"):
        assert out[col][0] == df[col][0]


def test_manifest_leaves_scalar_tagged_groups_out_of_rotation():
    """The Dojo rotates whatever the manifest lists, so a group tagged `scalar` must not be listed; an untagged group still is."""
    df = MojoDataFrame.from_dict(
        {
            "Bodies/a/xpos:x": [1.0],
            "Bodies/a/xpos:y": [1.0],
            "Bodies/a/xpos:z": [1.0],
            "Custom/euler:x": [0.1],
            "Custom/euler:y": [0.2],
            "Custom/euler:z": [0.3],
            "Custom/gains:w": [1.0],
            "Custom/gains:x": [2.0],
            "Custom/gains:y": [3.0],
            "Custom/gains:z": [4.0],
            "Bodies/a/quat:w": [1.0],
            "Bodies/a/quat:x": [0.0],
            "Bodies/a/quat:y": [0.0],
            "Bodies/a/quat:z": [0.0],
        }
    )
    without_metadata = df.mojo.get_manifest()
    assert "Custom/euler" in without_metadata["rotatable_vectors"]
    assert "Custom/gains" in without_metadata["available_quats"]

    meta = {
        "Custom/euler:x": TransformType.SCALAR.metadata,
        "Custom/gains:w": TransformType.SCALAR.metadata,
        "Bodies/a/xpos:x": TransformType.POINT.metadata,
    }
    manifest = df.mojo.get_manifest(column_metadata=meta)
    assert manifest["rotatable_vectors"] == ["Bodies/a/xpos"]
    assert manifest["available_quats"] == ["Bodies/a/quat"]


def test_change_frame_translates_rotates_and_composes():
    """End-to-end: change_frame re-expresses a point, a free vector, and a quaternion relative to a target frame, matching an independently computed scipy reference (not the bug report's own numbers, since their component-ordering convention relative to this codebase's is unverified)."""
    from scipy.spatial.transform import Rotation

    p_a = np.array([1.0, 2.0, 3.0])
    p_b = np.array([4.0, 5.0, 6.0])
    q_b = Rotation.from_euler("x", 90, degrees=True).as_quat()  # [x, y, z, w]
    q_a = Rotation.from_euler("z", 30, degrees=True).as_quat()
    v = np.array([1.0, 0.5, -0.25])  # a free vector, e.g. a velocity

    df = MojoDataFrame.from_dict(
        {
            "Bodies/A/xpos:x": [p_a[0]],
            "Bodies/A/xpos:y": [p_a[1]],
            "Bodies/A/xpos:z": [p_a[2]],
            "Bodies/A/quat:x": [q_a[0]],
            "Bodies/A/quat:y": [q_a[1]],
            "Bodies/A/quat:z": [q_a[2]],
            "Bodies/A/quat:w": [q_a[3]],
            "Bodies/A/xvelp:x": [v[0]],
            "Bodies/A/xvelp:y": [v[1]],
            "Bodies/A/xvelp:z": [v[2]],
            "Bodies/B/xpos:x": [p_b[0]],
            "Bodies/B/xpos:y": [p_b[1]],
            "Bodies/B/xpos:z": [p_b[2]],
            "Bodies/B/quat:x": [q_b[0]],
            "Bodies/B/quat:y": [q_b[1]],
            "Bodies/B/quat:z": [q_b[2]],
            "Bodies/B/quat:w": [q_b[3]],
        }
    )
    meta = {
        "Bodies/A/xpos:x": ColumnMetadata(transform_type=TransformType.POINT),
        "Bodies/A/quat:w": ColumnMetadata(transform_type=TransformType.QUATERNION),
        "Bodies/A/xvelp:x": ColumnMetadata(transform_type=TransformType.VECTOR),
        "Bodies/B/xpos:x": ColumnMetadata(transform_type=TransformType.POINT),
        "Bodies/B/quat:w": ColumnMetadata(transform_type=TransformType.QUATERNION),
    }

    result = df.mojo.change_frame(
        "Bodies/B/quat", "Bodies/B/xpos", column_metadata=meta
    )

    rb = Rotation.from_quat(q_b)
    expected_p = rb.inv().apply(p_a - p_b)
    expected_v = rb.inv().apply(v)
    expected_q_rot = rb.inv() * Rotation.from_quat(q_a)

    actual_p = result.select(
        ["Bodies/A/xpos:x", "Bodies/A/xpos:y", "Bodies/A/xpos:z"]
    ).to_numpy()[0]
    actual_v = result.select(
        ["Bodies/A/xvelp:x", "Bodies/A/xvelp:y", "Bodies/A/xvelp:z"]
    ).to_numpy()[0]
    # writable: polars can return a read-only zero-copy view, which older scipy rejects
    actual_q = result.select(
        ["Bodies/A/quat:x", "Bodies/A/quat:y", "Bodies/A/quat:z", "Bodies/A/quat:w"]
    ).to_numpy(writable=True)

    assert np.allclose(actual_p, expected_p, atol=1e-10)
    assert np.allclose(actual_v, expected_v, atol=1e-10)
    assert np.allclose(
        Rotation.from_quat(actual_q).as_matrix()[0],
        expected_q_rot.as_matrix(),
        atol=1e-10,
    )

    # B re-expressed in its own frame collapses to the origin, facing its own local axes
    b_p = result.select(
        ["Bodies/B/xpos:x", "Bodies/B/xpos:y", "Bodies/B/xpos:z"]
    ).to_numpy()[0]
    b_q = result.select(
        ["Bodies/B/quat:x", "Bodies/B/quat:y", "Bodies/B/quat:z", "Bodies/B/quat:w"]
    ).to_numpy()[0]
    assert np.allclose(b_p, [0.0, 0.0, 0.0], atol=1e-10)
    assert np.allclose(np.abs(b_q), [0.0, 0.0, 0.0, 1.0], atol=1e-10)


def _two_pose_frame() -> tuple[MojoDataFrame, dict[str, ColumnMetadata]]:
    """Two named poses (A, B) plus a velocity on A, and matching transform_type metadata."""
    from scipy.spatial.transform import Rotation

    p_a = [1.0, 2.0, 3.0]
    p_b = [4.0, 5.0, 6.0]
    q_a = Rotation.from_euler("z", 30, degrees=True).as_quat()
    q_b = Rotation.from_euler("x", 90, degrees=True).as_quat()
    df = MojoDataFrame.from_dict(
        {
            "Bodies/A/xpos:x": [p_a[0]],
            "Bodies/A/xpos:y": [p_a[1]],
            "Bodies/A/xpos:z": [p_a[2]],
            "Bodies/A/xpos:m": [float(np.linalg.norm(p_a))],
            "Bodies/A/quat:x": [q_a[0]],
            "Bodies/A/quat:y": [q_a[1]],
            "Bodies/A/quat:z": [q_a[2]],
            "Bodies/A/quat:w": [q_a[3]],
            "Bodies/A/xvelp:x": [1.0],
            "Bodies/A/xvelp:y": [0.5],
            "Bodies/A/xvelp:z": [-0.25],
            "Bodies/B/xpos:x": [p_b[0]],
            "Bodies/B/xpos:y": [p_b[1]],
            "Bodies/B/xpos:z": [p_b[2]],
            "Bodies/B/quat:x": [q_b[0]],
            "Bodies/B/quat:y": [q_b[1]],
            "Bodies/B/quat:z": [q_b[2]],
            "Bodies/B/quat:w": [q_b[3]],
        }
    )
    meta = {
        "Bodies/A/xpos:x": ColumnMetadata(transform_type=TransformType.POINT),
        "Bodies/A/quat:w": ColumnMetadata(transform_type=TransformType.QUATERNION),
        "Bodies/A/xvelp:x": ColumnMetadata(transform_type=TransformType.VECTOR),
        "Bodies/B/xpos:x": ColumnMetadata(transform_type=TransformType.POINT),
        "Bodies/B/quat:w": ColumnMetadata(transform_type=TransformType.QUATERNION),
    }
    return df, meta


def test_change_frame_round_trips_with_invert_false():
    """Re-expressing world -> B's frame -> world recovers the original columns. The frame's own columns are restored between the two calls, since B is itself transformed by the first call."""
    df, meta = _two_pose_frame()
    b_cols = [c for c in df.columns if c.startswith("Bodies/B/")]

    local = df.mojo.change_frame("Bodies/B/quat", "Bodies/B/xpos", column_metadata=meta)
    local = local.with_columns([df[c] for c in b_cols])
    restored = local.mojo.change_frame(
        "Bodies/B/quat", "Bodies/B/xpos", column_metadata=meta, invert=False
    )

    for col in [
        "Bodies/A/xpos:x",
        "Bodies/A/xpos:y",
        "Bodies/A/xpos:z",
        "Bodies/A/xvelp:x",
        "Bodies/A/xvelp:y",
        "Bodies/A/xvelp:z",
    ]:
        assert np.allclose(restored[col].to_numpy(), df[col].to_numpy(), atol=1e-10)


def test_change_frame_recomputes_point_magnitude():
    """A point's :m sibling is recomputed from the transformed x/y/z rather than left as the stale world-frame norm."""
    df, meta = _two_pose_frame()
    result = df.mojo.change_frame(
        "Bodies/B/quat", "Bodies/B/xpos", column_metadata=meta
    )

    xyz = result.select(
        ["Bodies/A/xpos:x", "Bodies/A/xpos:y", "Bodies/A/xpos:z"]
    ).to_numpy()
    assert np.allclose(
        result["Bodies/A/xpos:m"].to_numpy(), np.linalg.norm(xyz, axis=1)
    )
    assert not np.isclose(result["Bodies/A/xpos:m"][0], df["Bodies/A/xpos:m"][0])


def test_change_frame_reads_metadata_from_parquet_path(tmp_path: Path):
    """change_frame(path=...) reads transform_type tags from the parquet footer, matching an explicit column_metadata call."""
    import json

    df, meta = _two_pose_frame()
    path = tmp_path / "tel.parquet"
    df.write_parquet(
        path,
        metadata={
            "column_metadata": json.dumps(
                {k: v.model_dump(mode="json") for k, v in meta.items()}
            )
        },
    )

    from_path = df.mojo.change_frame("Bodies/B/quat", "Bodies/B/xpos", path=path)
    from_meta = df.mojo.change_frame(
        "Bodies/B/quat", "Bodies/B/xpos", column_metadata=meta
    )

    assert from_path.equals(from_meta)


def test_change_frame_raises_when_quaternion_mistagged():
    """A quaternion base tagged as something other than 'quaternion' raises instead of being composed."""
    df, meta = _two_pose_frame()
    meta["Bodies/A/quat:w"] = ColumnMetadata(transform_type=TransformType.VECTOR)
    with pytest.raises(ValueError, match="quaternion"):
        df.mojo.change_frame("Bodies/B/quat", "Bodies/B/xpos", column_metadata=meta)


def test_change_frame_raises_for_unknown_quat_or_origin_base():
    df, meta = _two_pose_frame()
    with pytest.raises(ValueError, match="quaternion base"):
        df.mojo.change_frame("Bodies/nope/quat", "Bodies/B/xpos", column_metadata=meta)
    with pytest.raises(ValueError, match="origin base"):
        df.mojo.change_frame("Bodies/B/quat", "Bodies/nope/xpos", column_metadata=meta)


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
