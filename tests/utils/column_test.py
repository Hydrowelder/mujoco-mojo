import re

import pytest
from pydantic import ValidationError

from mujoco_mojo.typing import SignalCategory
from mujoco_mojo.utils.column import (
    MATRIX_ATTRS,
    Column,
    covering_pattern,
    fan_out,
    pose_column_names,
    pose_missing_error,
)
from mujoco_mojo.utils.signal_metadata import ColumnMetadata


def test_str_builds_the_column_name() -> None:
    column = Column(category="Bodies", subgroups=("box1", "xpos"), attr="x")
    assert str(column) == "Bodies/box1/xpos:x"


def test_str_without_subgroups_or_attr() -> None:
    assert str(Column(category="time")) == "time"
    assert str(Column(category="Bodies", subgroups=("box1",), attr="ke_trans")) == (
        "Bodies/box1:ke_trans"
    )


def test_signal_category_is_stored_as_a_plain_string() -> None:
    column = Column(category=SignalCategory.BODIES, subgroups=("box1",))
    assert column.category == "Bodies"
    assert type(column.category) is str


def test_empty_parts_are_dropped_like_the_old_key_building() -> None:
    column = Column(category="Sensors", subgroups=("acc", "", "accelerometer"), attr="")
    assert column.subgroups == ("acc", "accelerometer")
    assert column.attr is None
    assert str(column) == "Sensors/acc/accelerometer"


@pytest.mark.parametrize(
    ("kwargs", "part"),
    [
        ({"category": "Bod/ies"}, "category"),
        ({"category": "Bodies:x"}, "category"),
        ({"category": "Bodies", "subgroups": ("left/rear",)}, "subgroup"),
        ({"category": "Bodies", "subgroups": ("x:vel",)}, "subgroup"),
        ({"category": "Bodies", "attr": "a:b"}, "attr"),
        ({"category": "Bodies", "attr": "a/b"}, "attr"),
    ],
)
def test_a_part_that_would_corrupt_the_grammar_is_rejected(
    kwargs: dict, part: str
) -> None:
    """The error names the offending part, instead of the name silently parsing into different positions."""
    with pytest.raises(ValueError, match=part):
        Column(**kwargs)


def test_empty_category_is_rejected() -> None:
    with pytest.raises(ValueError, match="category"):
        Column(category="")


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Column.model_validate({"category": "Bodies", "component": "x"})


def test_column_is_frozen_and_hashable() -> None:
    column = Column(category="Bodies", subgroups=("box1",), attr="x")
    with pytest.raises(ValidationError):
        setattr(column, "attr", "y")
    assert column == Column(category="Bodies", subgroups=("box1",), attr="x")
    assert len({column, Column(category="Bodies", subgroups=("box1",), attr="x")}) == 1


def test_metadata_is_part_of_the_column() -> None:
    plain = Column(category="Bodies")
    assert not plain.metadata
    tagged = Column(category="Bodies", metadata=ColumnMetadata(unit="meter"))
    assert tagged.metadata.unit == "meter"
    assert plain != tagged


@pytest.mark.parametrize(
    "name",
    [
        "time",
        "Bodies/box1:ke_trans",
        "Bodies/box1/xpos:x",
        "Sensors/acc/accelerometer:m",
        "Proximities/box1_to_box2/fromto/box1:z",
        "Requirements/time_is_not_negative:result",
        "Loads/thruster/force",
    ],
)
def test_parse_is_the_inverse_of_str(name: str) -> None:
    assert str(Column.parse(name)) == name


def test_parse_splits_the_parts() -> None:
    column = Column.parse("Proximities/pair/fromto/g1:x")
    assert column.category == "Proximities"
    assert column.subgroups == ("pair", "fromto", "g1")
    assert column.attr == "x"


@pytest.mark.parametrize("name", ["", "a//b", "/a", "a/", "a:", "a:b:c"])
def test_parse_rejects_malformed_names(name: str) -> None:
    with pytest.raises(ValueError):
        Column.parse(name)


def test_parse_can_attach_metadata() -> None:
    column = Column.parse("Bodies/box1/xpos:x", ColumnMetadata(dimension="[length]"))
    assert column.metadata.dimension == "[length]"


def test_hash_is_stable_and_follows_equality() -> None:
    a = Column(category="Bodies", subgroups=("box1",), attr="x")
    b = Column(category="Bodies", subgroups=("box1",), attr="x")
    assert hash(a) == hash(a) == hash(b)
    assert hash(a) != hash(Column(category="Bodies", subgroups=("box1",), attr="y"))
    assert hash(a) != hash(
        Column(
            category="Bodies",
            subgroups=("box1",),
            attr="x",
            metadata=ColumnMetadata(unit="m"),
        )
    )


def test_metadata_accepts_a_plain_dict() -> None:
    column = Column.model_validate(
        {
            "category": "Sensors",
            "subgroups": ("Foo",),
            "metadata": {"dimension": "[length]", "display_name": "Foo"},
        }
    )
    assert isinstance(column.metadata, ColumnMetadata)
    assert column.metadata.model_dump() == {
        "dimension": "[length]",
        "display_name": "Foo",
    }


def test_metadata_none_means_empty() -> None:
    assert not Column.model_validate({"category": "Bodies", "metadata": None}).metadata


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        ({"dimension": "not_a_dimension"}, "Invalid signal metadata dimension"),
        ({"unit": "not_a_unit"}, "Invalid signal metadata unit"),
        ({"dimension": "[length]", "unit": "newton"}, "do not"),
        ({"transform_type": "not_a_kind"}, "Invalid signal metadata transform_type"),
    ],
)
def test_metadata_is_validated_when_the_column_is_built(
    metadata: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        Column.model_validate(
            {"category": "Sensors", "subgroups": ("Foo",), "metadata": metadata}
        )


def test_fan_out_builds_one_column_per_attr_sharing_the_rest() -> None:
    meta = ColumnMetadata(dimension="[length]")
    columns = fan_out("Bodies", ("box1", "xpos"), "xyz", meta)
    assert [str(c) for c in columns] == [
        "Bodies/box1/xpos:x",
        "Bodies/box1/xpos:y",
        "Bodies/box1/xpos:z",
    ]
    assert all(c.metadata == meta for c in columns)


def test_fan_out_without_metadata_is_empty() -> None:
    (column,) = fan_out("Bodies", ("box1",), ["ke_trans"])
    assert not column.metadata


def test_matrix_attrs_are_the_nine_flattened_elements() -> None:
    assert MATRIX_ATTRS == tuple("012345678")
    columns = fan_out("Bodies", ("box1", "xmat"), MATRIX_ATTRS)
    assert str(columns[8]) == "Bodies/box1/xmat:8"


def test_model_copy_does_not_carry_a_stale_hash() -> None:
    original = Column(category="Bodies", subgroups=("box1",), attr="x")
    hash(original)
    changed = original.model_copy(update={"attr": "y"})
    assert hash(changed) == hash(
        Column(category="Bodies", subgroups=("box1",), attr="y")
    )
    assert changed != original


def test_parse_is_cached_and_equals_a_built_column() -> None:
    parsed = Column.parse("Bodies/box1/xpos:x")
    assert parsed is Column.parse("Bodies/box1/xpos:x")
    built = Column(category="Bodies", subgroups=("box1", "xpos"), attr="x")
    assert parsed == built
    assert hash(parsed) == hash(built)


def test_parse_with_metadata_does_not_change_the_cached_column() -> None:
    tagged = Column.parse("Bodies/box1/xpos:x", ColumnMetadata(unit="meter"))
    assert tagged.metadata.unit == "meter"
    assert not Column.parse("Bodies/box1/xpos:x").metadata


def test_covers_selects_a_subtree() -> None:
    body = Column(category="Bodies", subgroups=("box1",))
    assert body.covers(Column.parse("Bodies/box1/xpos:x"))
    assert body.covers(Column.parse("Bodies/box1:ke_trans"))
    assert body.covers(Column.parse("Bodies/box1"))
    assert not body.covers(Column.parse("Bodies/box2/xpos:x"))
    assert not body.covers(Column.parse("Bodies/box10/xpos:x"))
    assert not body.covers(Column.parse("Sites/box1/xpos:x"))


def test_covers_an_attr_matches_every_object() -> None:
    every_x = Column(category="Bodies", attr="x")
    assert every_x.covers(Column.parse("Bodies/a/xpos:x"))
    assert every_x.covers(Column.parse("Bodies/b/xvelp:x"))
    assert not every_x.covers(Column.parse("Bodies/a/xpos:y"))


def test_pose_column_names_follow_the_writer_grammar() -> None:
    pos, quat = pose_column_names("Sites/A")
    assert pos == ("Sites/A/xpos:x", "Sites/A/xpos:y", "Sites/A/xpos:z")
    assert quat == (
        "Sites/A/quat:w",
        "Sites/A/quat:x",
        "Sites/A/quat:y",
        "Sites/A/quat:z",
    )
    assert pose_column_names(Column(category="Sites", subgroups=("A",))) == (pos, quat)


def test_pose_column_names_accept_other_channels() -> None:
    pos, quat = pose_column_names("Bodies/b", "xipos", "xiquat")
    assert pos[0] == "Bodies/b/xipos:x"
    assert quat[3] == "Bodies/b/xiquat:z"


def test_pose_column_names_reject_a_single_column() -> None:
    with pytest.raises(ValueError, match="names a single column"):
        pose_column_names("Sites/A/xpos:x")


def test_pose_missing_error_names_every_missing_column() -> None:
    pos, quat = pose_column_names("Sites/A")
    assert pose_missing_error("Sites/A", {*pos, *quat}) is None
    error = pose_missing_error("Sites/A", {*pos, "Sites/A/quat:w"})
    assert error is not None
    message = str(error)
    for name in ("Sites/A/quat:x", "Sites/A/quat:y", "Sites/A/quat:z"):
        assert name in message
    assert "Sites/A/xpos:x" not in message


def test_in_is_covers_with_the_child_on_the_left() -> None:
    body = Column(category="Bodies", subgroups=("box1",))
    assert Column.parse("Bodies/box1/xpos:x") in body
    assert Column.parse("Bodies/box2/xpos:x") not in body
    assert "Bodies/box1:ke_trans" in body
    assert "Bodies/box2:ke_trans" not in body
    # a name outside the grammar is simply not contained
    assert "Bodies//box1" not in body


def test_in_does_not_change_equality() -> None:
    body = Column(category="Bodies", subgroups=("box1",))
    full = Column.parse("Bodies/box1/xpos:x")
    assert body != full
    assert body not in [full]
    assert full in [Column.parse("Bodies/box1/xpos:x")]


_NAMES = [
    "time",
    "Bodies/box1/xpos:x",
    "Bodies/box1/xpos:y",
    "Bodies/box1:ke_trans",
    "Bodies/box1",
    "Bodies/box10/xpos:x",
    "Bodies/box2/xvelp:x",
    "Bodies:x",
    "Sites/box1/xpos:x",
    "Bodies/a.b/xpos:x",
    "Bodies/aXb/xpos:x",
    "Bodies/(arm) #1/xpos:x",
]


@pytest.mark.parametrize(
    "wanted",
    [
        Column(category="Bodies"),
        Column(category="Bodies", subgroups=("box1",)),
        Column(category="Bodies", subgroups=("box1", "xpos")),
        Column(category="Bodies", subgroups=("box1", "xpos"), attr="x"),
        Column(category="Bodies", attr="x"),
        Column(category="Bodies", subgroups=("box1",), attr="ke_trans"),
        Column(category="time"),
        Column(category="Bodies", subgroups=("a.b",)),
        Column(category="Bodies", subgroups=("(arm) #1",)),
    ],
)
def test_covering_pattern_agrees_with_covers(wanted: Column) -> None:
    """The regex used to select inside polars and `covers` must never drift apart."""
    pattern = re.compile(covering_pattern([wanted]))
    for name in _NAMES:
        assert bool(pattern.fullmatch(name)) == (name in wanted), name


def test_covering_pattern_matches_any_of_several_columns() -> None:
    pattern = re.compile(
        covering_pattern(
            [Column(category="time"), Column(category="Sites", subgroups=("box1",))]
        )
    )
    assert [n for n in _NAMES if pattern.fullmatch(n)] == [
        "time",
        "Sites/box1/xpos:x",
    ]
