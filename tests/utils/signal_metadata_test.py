import pint
import pytest

from mujoco_mojo.utils.filters.filters import ureg
from mujoco_mojo.utils.signal_metadata import (
    ColumnMetadata,
    Dimension,
    TransformType,
    angle_metadata,
    angular_rate_metadata,
    dim,
    dimensionless_metadata,
    force_or_torque,
    merge_signal_metadata,
    torque_metadata,
    unit,
)


def test_torque_and_energy_are_not_aliased_but_are_dimensionally_equal() -> None:
    """TORQUE and ENERGY must stay distinct enum members (not collapsed by Python's enum aliasing), while still being the same Pint dimensionality so Pint accepts either as valid."""
    assert Dimension.TORQUE is not Dimension.ENERGY
    assert ureg.get_dimensionality(Dimension.TORQUE.value) == ureg.get_dimensionality(
        Dimension.ENERGY.value
    )


def test_dim_and_unit_build_expected_metadata() -> None:
    assert dim(Dimension.LENGTH).model_dump() == {"dimension": "[length]"}
    assert unit("meter").model_dump() == {"unit": "meter"}


def test_torque_metadata_includes_quantity_hint() -> None:
    assert torque_metadata().model_dump() == {
        "dimension": Dimension.TORQUE.value,
        "quantity": "torque",
    }


def test_angle_and_angular_rate_metadata_use_radian_unit() -> None:
    assert angle_metadata().model_dump() == {"unit": "radian"}
    assert angular_rate_metadata().model_dump() == {"unit": "radian / second"}
    assert angular_rate_metadata(per="second ** 2").model_dump() == {
        "unit": "radian / second ** 2"
    }


def test_dimensionless_metadata() -> None:
    assert dimensionless_metadata().model_dump() == {"dimension": "[]"}


def test_force_or_torque_dispatches_on_joint_type() -> None:
    import mujoco

    assert force_or_torque(int(mujoco.mjtJoint.mjJNT_SLIDE)) == dim(Dimension.FORCE)
    assert force_or_torque(int(mujoco.mjtJoint.mjJNT_HINGE)) == torque_metadata()
    assert force_or_torque(int(mujoco.mjtJoint.mjJNT_BALL)) == torque_metadata()
    assert force_or_torque(int(mujoco.mjtJoint.mjJNT_FREE)) == torque_metadata()


def test_merge_signal_metadata_with_no_builtin_or_user() -> None:
    assert not merge_signal_metadata(None, "xpos", None)
    assert not merge_signal_metadata(None, "xpos", {})
    assert not merge_signal_metadata(None, "xpos", {"other": {"a": "b"}})


def test_merge_signal_metadata_user_only() -> None:
    merged = merge_signal_metadata(None, "xpos", {"xpos": {"display_name": "X"}})
    assert merged.model_dump() == {"display_name": "X"}


def test_merge_signal_metadata_builtin_only() -> None:
    merged = merge_signal_metadata(dim(Dimension.LENGTH), "xpos", None)
    assert merged.model_dump() == {"dimension": "[length]"}


def test_merge_signal_metadata_user_overrides_builtin_keys() -> None:
    merged = merge_signal_metadata(
        dim(Dimension.LENGTH),
        "xpos",
        {"xpos": {"dimension": "[time]", "display_name": "X"}},
    )
    assert merged.model_dump() == {"dimension": "[time]", "display_name": "X"}


def test_transform_type_metadata_builds_expected_metadata() -> None:
    assert TransformType.POINT.metadata.model_dump() == {"transform_type": "point"}
    assert TransformType.VECTOR.metadata.model_dump() == {"transform_type": "vector"}
    assert TransformType.QUATERNION.metadata.model_dump() == {
        "transform_type": "quaternion"
    }


# --- ColumnMetadata ---


def test_column_metadata_omits_unset_fields() -> None:
    """Unset fields are left out of every dump, so the footer JSON only carries what was tagged."""
    meta = ColumnMetadata(dimension="[length]")
    assert meta.model_dump() == {"dimension": "[length]"}
    assert meta.model_dump(mode="json") == {"dimension": "[length]"}
    assert ColumnMetadata().model_dump() == {}


def test_column_metadata_keeps_extra_fields() -> None:
    meta = ColumnMetadata.model_validate({"unit": "meter", "display_name": "Length"})
    assert meta.model_dump() == {"unit": "meter", "display_name": "Length"}
    assert meta.display_name == "Length"  # pyright: ignore[reportAttributeAccessIssue]


def test_column_metadata_serializes_transform_type_as_a_plain_string() -> None:
    dumped = ColumnMetadata(transform_type=TransformType.POINT).model_dump(mode="json")
    assert dumped == {"transform_type": "point"}
    assert isinstance(dumped["transform_type"], str)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"dimension": "not_a_dimension"}, "Invalid signal metadata dimension"),
        ({"unit": "not_a_unit"}, "Invalid signal metadata unit"),
        ({"dimension": "[length]", "unit": "newton"}, "do not"),
        ({"transform_type": "diagonal"}, "Invalid signal metadata transform_type"),
    ],
)
def test_column_metadata_rejects_invalid_values(
    kwargs: dict[str, str], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        ColumnMetadata(**kwargs)  # pyright: ignore[reportArgumentType]


def test_column_metadata_accepts_matching_unit_and_dimension() -> None:
    meta = ColumnMetadata(dimension="[length] / [time]", unit="meter / second")
    assert meta.unit == "meter / second"


def test_column_metadata_merge_right_side_wins_and_keeps_extras() -> None:
    left = ColumnMetadata.model_validate(
        {"dimension": "[length]", "note": "a", "quantity": "x"}
    )
    right = ColumnMetadata.model_validate({"dimension": "[time]", "extra": "b"})
    merged = left | right
    assert merged.model_dump() == {
        "dimension": "[time]",
        "quantity": "x",
        "note": "a",
        "extra": "b",
    }
    # neither operand is mutated
    assert left.dimension == "[length]"


def test_column_metadata_merge_does_not_erase_with_unset_fields() -> None:
    assert (dim(Dimension.LENGTH) | ColumnMetadata()).dimension == "[length]"


def test_column_metadata_truthiness_follows_whether_anything_is_set() -> None:
    assert not ColumnMetadata()
    assert ColumnMetadata(unit="meter")


def test_column_metadata_validated_checks_unchecked_merges() -> None:
    """Per-timestep merges skip validation, so registration must still catch a bad value."""
    unchecked = ColumnMetadata.unchecked({"unit": "not_a_unit"})
    with pytest.raises(ValueError, match="Invalid signal metadata unit"):
        ColumnMetadata.validated(unchecked)


def test_column_metadata_lenient_keeps_an_invalid_entry() -> None:
    meta = ColumnMetadata.lenient({"unit": "not_a_unit", "label": "x"})
    assert meta.unit == "not_a_unit"
    assert meta.model_dump() == {"unit": "not_a_unit", "label": "x"}


def test_column_metadata_json_schema_lists_the_declared_fields() -> None:
    """The Lab's Signal Out node is generated from this schema, so it must cover every declared field."""
    schema = ColumnMetadata.model_json_schema()
    assert set(schema["properties"]) == set(ColumnMetadata.model_fields)
    assert {"unit", "dimension", "quantity", "transform_type"} <= set(
        schema["properties"]
    )
    assert all(p.get("description") for p in schema["properties"].values())


def test_all_dimension_expressions_are_valid_pint_dimensions() -> None:
    """Every Dimension member must parse as a valid Pint dimension expression."""
    for member in Dimension:
        try:
            ureg.get_dimensionality(member.value)
        except (pint.UndefinedUnitError, pint.DefinitionSyntaxError) as e:
            pytest.fail(f"Dimension.{member.name} ({member.value!r}) is invalid: {e}")
