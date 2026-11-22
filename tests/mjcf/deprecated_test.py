"""Tests for the warnings on deprecated MJCF attributes."""

import logging
import warnings
from typing import Any

import pytest

from mujoco_mojo.mjcf import (
    Compiler,
    Light,
    Mujoco,
    Size,
    Statistic,
    WorldBody,
)
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import LightName, LightType

# each deprecated attribute, the model it lives on, a value other than its default, and a word its message has to contain
DEPRECATED: list[tuple[type[XMLModel], str, Any, str]] = [
    (Light, "directional", True, "LightType.DIRECTIONAL"),
    (Size, "njmax", 10, "memory"),
    (Size, "nconmax", 10, "backwards compatibility"),
    (Size, "nstack", 10, "memory"),
    (Statistic, "meaninertia", 2.0, "will remove it"),
    (Compiler, "settotalmass", 5.0, "mj_setTotalmass"),
]
IDS = [f"{cls.__name__}.{name}" for cls, name, _, _ in DEPRECATED]


@pytest.mark.parametrize(("cls", "name", "value", "word"), DEPRECATED, ids=IDS)
def test_setting_a_deprecated_attribute_warns_once_on_the_callers_line(
    cls: type[XMLModel], name: str, value: Any, word: str
) -> None:
    with pytest.warns(DeprecationWarning, match=name) as caught:
        cls(**{name: value})

    assert len(caught) == 1
    assert word in str(caught[0].message)
    assert caught[0].filename == __file__


def test_setting_a_deprecated_attribute_is_also_logged_on_the_callers_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Python hides a `DeprecationWarning` that does not come from `__main__`, so Reloaded and `mojo.log` need the log record."""
    with caplog.at_level(logging.WARNING), pytest.warns(DeprecationWarning):
        Light(directional=True)

    records = [r for r in caplog.records if "Light.directional" in r.getMessage()]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert records[0].pathname == __file__


@pytest.mark.parametrize(("cls", "name", "value", "word"), DEPRECATED, ids=IDS)
def test_leaving_a_deprecated_attribute_at_its_default_does_not_warn(
    cls: type[XMLModel], name: str, value: Any, word: str
) -> None:
    default = cls.model_fields[name].default

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        cls()
        cls(**{name: default})


def test_an_object_passed_into_other_models_warns_only_once() -> None:
    """Pydantic runs `after` validators again on an object that is passed into another model."""
    with pytest.warns(DeprecationWarning, match="meaninertia"):
        statistic = Statistic(meaninertia=2.0)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        Mujoco(statistics=[statistic], worldbody=WorldBody())
        Mujoco(statistics=[statistic], worldbody=WorldBody())
        statistic.model_copy()


def test_an_object_with_two_deprecated_attributes_warns_about_both() -> None:
    with pytest.warns(DeprecationWarning) as caught:
        Size(njmax=10, nstack=10)

    assert len(caught) == 2


def test_reloading_a_saved_config_does_not_warn_about_fields_nobody_set() -> None:
    """A saved config holds every field, defaults included, so the deprecated ones are in it."""
    saved = Compiler().model_dump_json()
    assert "settotalmass" in saved

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        Compiler.model_validate_json(saved)


def test_reading_a_deprecated_attribute_still_warns() -> None:
    light = Light()

    with pytest.warns(DeprecationWarning, match="Light.directional"):
        _ = light.directional


def test_a_model_using_elements_with_deprecated_attributes_compiles_without_warning() -> (
    None
):
    """Writing the model to XML reads every attribute, the deprecated ones included, which must stay quiet. The filters here are the repo's own, which turn any other warning into an error."""
    model = Mujoco(
        worldbody=WorldBody(
            lights=[Light(name=LightName("sun"), type=LightType.DIRECTIONAL)]
        ),
        statistics=[Statistic(meansize=1.0)],
        sizes=[Size(memory="16M")],
        compilers=[Compiler()],
    )

    with warnings.catch_warnings(record=True) as caught:
        model.to_mj_model()

    assert not [w for w in caught if issubclass(w.category, DeprecationWarning)]
