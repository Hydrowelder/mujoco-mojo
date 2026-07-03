import pint
import pytest

from mujoco_mojo.utils.filters.filters import ureg
from mujoco_mojo.utils.signal_metadata import (
    Dimension,
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


def test_dim_and_unit_build_expected_dicts() -> None:
    assert dim(Dimension.LENGTH) == {"dimension": "[length]"}
    assert unit("meter") == {"unit": "meter"}


def test_torque_metadata_includes_quantity_hint() -> None:
    assert torque_metadata() == {
        "dimension": Dimension.TORQUE.value,
        "quantity": "torque",
    }


def test_angle_and_angular_rate_metadata_use_radian_unit() -> None:
    assert angle_metadata() == {"unit": "radian"}
    assert angular_rate_metadata() == {"unit": "radian / second"}
    assert angular_rate_metadata(per="second ** 2") == {"unit": "radian / second ** 2"}


def test_dimensionless_metadata() -> None:
    assert dimensionless_metadata() == {"dimension": "[]"}


def test_force_or_torque_dispatches_on_joint_type() -> None:
    import mujoco

    assert force_or_torque(int(mujoco.mjtJoint.mjJNT_SLIDE)) == dim(Dimension.FORCE)
    assert force_or_torque(int(mujoco.mjtJoint.mjJNT_HINGE)) == torque_metadata()
    assert force_or_torque(int(mujoco.mjtJoint.mjJNT_BALL)) == torque_metadata()
    assert force_or_torque(int(mujoco.mjtJoint.mjJNT_FREE)) == torque_metadata()


def test_merge_signal_metadata_with_no_builtin_or_user() -> None:
    assert merge_signal_metadata(None, "xpos", None) is None
    assert merge_signal_metadata(None, "xpos", {}) is None
    assert merge_signal_metadata(None, "xpos", {"other": {"a": "b"}}) is None


def test_merge_signal_metadata_user_only() -> None:
    assert merge_signal_metadata(None, "xpos", {"xpos": {"display_name": "X"}}) == {
        "display_name": "X"
    }


def test_merge_signal_metadata_builtin_only() -> None:
    assert merge_signal_metadata(dim(Dimension.LENGTH), "xpos", None) == {
        "dimension": "[length]"
    }


def test_merge_signal_metadata_user_overrides_builtin_keys() -> None:
    merged = merge_signal_metadata(
        dim(Dimension.LENGTH),
        "xpos",
        {"xpos": {"dimension": "[time]", "display_name": "X"}},
    )
    assert merged == {"dimension": "[time]", "display_name": "X"}


def test_all_dimension_expressions_are_valid_pint_dimensions() -> None:
    """Every Dimension member must parse as a valid Pint dimension expression."""
    for member in Dimension:
        try:
            ureg.get_dimensionality(member.value)
        except (pint.UndefinedUnitError, pint.DefinitionSyntaxError) as e:
            pytest.fail(f"Dimension.{member.name} ({member.value!r}) is invalid: {e}")
