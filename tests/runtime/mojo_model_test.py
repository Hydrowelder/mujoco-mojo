import pytest

from mujoco_mojo.mojo_model import MojoModel, UserData


class MyData(UserData):
    value: int = 0


class OtherData(UserData):
    label: str = "x"


def test_trial_dir_raises_before_set():
    """trial_dir raises RuntimeError when accessed inside the generator (before workspace is created)."""
    model = MojoModel()
    with pytest.raises(
        RuntimeError, match="trial_dir is not available inside the generator"
    ):
        _ = model.trial_dir


def test_trial_dir_returns_path_when_set(tmp_path):
    """trial_dir returns the path once set."""
    model = MojoModel()
    model._trial_dir = tmp_path
    assert model.trial_dir == tmp_path


def test_get_user_data_raises_when_none():
    """`get_user_data` raises ValueError when user_data is None."""
    model = MojoModel()
    assert model.user_data is None
    with pytest.raises(ValueError, match="Unable to get user_data"):
        model.get_user_data(MyData)


def test_get_user_data_returns_directly_when_type_matches():
    """`get_user_data` returns the stored instance unchanged when the type already matches."""
    model = MojoModel()
    data = MyData(value=42)
    model.user_data = data
    result = model.get_user_data(MyData)
    assert result is data
    assert result.value == 42


def test_get_user_data_revalidates_when_type_mismatches():
    """`get_user_data` re-validates a base UserData instance into the requested subclass."""
    model = MojoModel()
    # store as plain UserData with extra fields allowed
    model.user_data = UserData.model_validate({"value": 7})
    result = model.get_user_data(MyData)
    assert isinstance(result, MyData)
    assert result.value == 7
