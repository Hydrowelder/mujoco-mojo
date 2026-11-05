"""
`Inertial.from_random` draws an inertial from distributions and redraws any that are not physical. These tests pin what a caller gets back and what is left on the model, so the method can be restructured without changing either.

Expected values come from a separate copy of each distribution seeded the same way, so they follow whatever stream the installed numpy produces instead of being typed in.
"""

import logging
from collections.abc import Callable
from typing import Any, NamedTuple, cast

import numpy as np
import pytest

from mujoco_mojo.mjcf.mujoco_attr.body_attr import Inertial
from mujoco_mojo.mjcf.orientation import Euler, Quat
from mujoco_mojo.mjcf.position import Pos
from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.stochas import (
    DistName,
    NamedValue,
    NamedValueDict,
    NormalDistribution,
    UniformDistribution,
    UnitDescriptor,
    UnitSystem,
    ValueName,
)
from mujoco_mojo.typing import EulerSeq

SEED = 42
TRIAL = 1
INERTIA = (0.1, 0.1, 0.1)
"""A valid set of principal moments, for tests that are not about the inertia."""


def required[T](value: T | None) -> T:
    """Narrows an optional field that the test has already arranged to be set."""
    assert value is not None
    return value


def stored(model: MojoModel, name: str) -> float:
    """The single number registered under `name`, whatever shape it is stored in."""
    return float(np.squeeze(model.named[name].value))


def make_model() -> MojoModel:
    return MojoModel().with_seed(SEED).with_trial_num(TRIAL)


def uniform(
    name: str, low: float, high: float, unit: UnitDescriptor | None = None
) -> UniformDistribution:
    return UniformDistribution(name=DistName(name), low=low, high=high, unit=unit)


def normal(name: str, mu: float, sigma: float) -> NormalDistribution:
    return NormalDistribution(name=DistName(name), mu=mu, sigma=sigma)


def twin_draws(
    make_dist: Callable[[], UniformDistribution | NormalDistribution],
    count: int,
    model: MojoModel | None = None,
    seed: int = SEED,
    trial: int = TRIAL,
) -> list[float]:
    """The first `count` values a fresh copy of the distribution draws for the given seed and trial."""
    model = model or make_model()
    twin = make_dist().with_seed(seed).with_trial_num(trial)
    return [
        float(twin.sample_to_named_value(unit_system=model.us).value.squeeze())
        for _ in range(count)
    ]


def is_physical(moments: list[float]) -> bool:
    try:
        Inertial(mass=1.0, pos=Pos(pos=np.zeros(3)), diaginertia=np.asarray(moments))
    except ValueError:
        return False
    return True


def moments_needing_attempts(attempts: int) -> tuple[list[str], list[list[float]]]:
    """Names for three distributions whose draws are rejected until attempt number `attempts`, with the draws of every attempt up to it."""
    for i in range(1000):
        names = [f"moment_{i}_{axis}" for axis in "xyz"]
        streams = [
            twin_draws(lambda n=n: uniform(n, -0.5, 1.0), attempts) for n in names
        ]
        rounds = [[stream[k] for stream in streams] for k in range(attempts)]
        valid = [is_physical(r) for r in rounds]
        if valid == [False] * (attempts - 1) + [True]:
            return names, rounds
    pytest.fail(f"no draws found that need exactly {attempts} attempts")


# the draws a caller gets back, and what is registered


def test_the_first_valid_draw_is_returned_and_registered() -> None:
    model = make_model()
    mass = normal("mass", 2.0, 0.1)
    pos = (uniform("pos_x", -1, 1), uniform("pos_y", -1, 1), uniform("pos_z", -1, 1))

    item = Inertial.from_random(
        mojo_model=model, mass=mass, pos=pos, diaginertia=np.asarray(INERTIA)
    )

    expected_mass = twin_draws(lambda: normal("mass", 2.0, 0.1), 1)[0]
    expected_pos = [
        twin_draws(lambda n=f"pos_{axis}": uniform(n, -1, 1), 1)[0] for axis in "xyz"
    ]
    assert item.mass == expected_mass
    assert np.array_equal(item.pos.pos, expected_pos)
    assert np.array_equal(required(item.diaginertia), INERTIA)
    assert isinstance(item.orientation, Quat)
    assert item.fullinertia is None

    # everything drawn is registered, in the order it was drawn, and nothing else
    assert list(model.dists) == ["mass", "pos_x", "pos_y", "pos_z"]
    assert list(model.named) == ["mass", "pos_x", "pos_y", "pos_z"]
    assert model.dists["mass"] is mass
    assert model.dists["pos_y"] is pos[1]
    assert stored(model, "mass") == expected_mass
    for axis, value in zip("xyz", expected_pos, strict=True):
        assert stored(model, f"pos_{axis}") == value


def test_a_draw_is_stored_squeezed_only_when_it_is_one_component_of_a_vector() -> None:
    """Pins the shapes as they are today: a component drawn for a vector is stored as a scalar array, a value drawn whole keeps the one-sample shape."""
    model = make_model()

    Inertial.from_random(
        mojo_model=model,
        mass=normal("mass", 2.0, 0.1),
        pos=(uniform("pos_x", -1, 1), 0.0, 0.0),
        diaginertia=np.asarray(INERTIA),
    )

    assert model.named["mass"].value.shape == (1,)
    assert model.named["pos_x"].value.shape == ()


def test_the_distributions_take_the_models_seed_and_trial() -> None:
    model = make_model()
    mass = normal("mass", 2.0, 0.1).with_seed(7).with_trial_num(3)

    Inertial.from_random(
        mojo_model=model, mass=mass, pos=np.zeros(3), diaginertia=np.asarray(INERTIA)
    )

    assert (mass.seed, mass.trial_num) == (SEED, TRIAL)


def test_reset_rng_false_keeps_the_distributions_own_seed_and_trial() -> None:
    model = make_model()
    mass = normal("mass", 2.0, 0.1).with_seed(7).with_trial_num(3)

    item = Inertial.from_random(
        mojo_model=model,
        mass=mass,
        pos=np.zeros(3),
        diaginertia=np.asarray(INERTIA),
        reset_rng=False,
    )

    assert (mass.seed, mass.trial_num) == (7, 3)
    assert (
        item.mass == twin_draws(lambda: normal("mass", 2.0, 0.1), 1, seed=7, trial=3)[0]
    )
    # still registered, as the docstring promises
    assert model.dists["mass"] is mass
    assert stored(model, "mass") == item.mass


def test_values_are_converted_into_the_models_base_unit() -> None:
    model = make_model().with_unit_system(UnitSystem.si())
    inch = required(model.us).inch

    item = Inertial.from_random(
        mojo_model=model,
        mass=1.0,
        pos=(uniform("pos_x", 1, 2, unit=inch), 0.0, 0.0),
        diaginertia=np.asarray(INERTIA),
    )

    expected = twin_draws(lambda: uniform("pos_x", 1, 2, unit=inch), 1, model=model)[0]
    assert item.pos.pos[0] == expected
    assert stored(model, "pos_x") == expected
    assert 0.0254 <= item.pos.pos[0] <= 0.0508


def test_plain_numbers_register_nothing() -> None:
    model = make_model()

    item = Inertial.from_random(
        mojo_model=model,
        mass=3,
        pos=Pos(pos=np.array([1.0, 2.0, 3.0])),
        diaginertia=np.asarray(INERTIA),
    )

    assert item.mass == 3.0
    assert isinstance(item.mass, float)
    assert np.array_equal(item.pos.pos, [1.0, 2.0, 3.0])
    assert list(model.dists) == []
    assert list(model.named) == []


def test_a_vector_of_plain_numbers_in_a_tuple_is_accepted() -> None:
    item = Inertial.from_random(
        mojo_model=make_model(),
        mass=1.0,
        pos=(1.0, 2.0, 3.0),
        diaginertia=(0.1, 0.2, 0.2),
    )

    assert np.array_equal(item.pos.pos, [1.0, 2.0, 3.0])
    assert np.array_equal(required(item.diaginertia), [0.1, 0.2, 0.2])


def test_fullinertia_is_drawn_per_component_and_leaves_no_orientation() -> None:
    model = make_model()
    diagonal = (
        uniform("diag_0", 1.0, 2.0),
        uniform("diag_1", 1.0, 2.0),
        uniform("diag_2", 1.0, 2.0),
    )
    off = (
        uniform("off_0", -0.1, 0.1),
        uniform("off_1", -0.1, 0.1),
        uniform("off_2", -0.1, 0.1),
    )

    item = Inertial.from_random(
        mojo_model=model,
        mass=1.0,
        pos=np.zeros(3),
        fullinertia=(*diagonal, *off),
    )

    expected = [
        twin_draws(lambda n=f"diag_{i}": uniform(n, 1.0, 2.0), 1)[0] for i in range(3)
    ] + [twin_draws(lambda n=f"off_{i}": uniform(n, -0.1, 0.1), 1)[0] for i in range(3)]
    assert item.diaginertia is None
    assert item.orientation is None
    assert np.array_equal(required(item.fullinertia), expected)
    assert list(model.named) == [f"diag_{i}" for i in range(3)] + [
        f"off_{i}" for i in range(3)
    ]


# orientation


def test_no_orientation_gives_the_identity_quaternion() -> None:
    item = Inertial.from_random(
        mojo_model=make_model(),
        mass=1.0,
        pos=np.zeros(3),
        diaginertia=np.asarray(INERTIA),
    )

    assert isinstance(item.orientation, Quat)
    assert np.array_equal(item.orientation.quat, Quat().quat)


def test_an_orientation_object_is_used_as_given() -> None:
    orientation = Quat(quat=np.array([0.0, 1.0, 0.0, 0.0]))

    item = Inertial.from_random(
        mojo_model=make_model(),
        mass=1.0,
        pos=np.zeros(3),
        diaginertia=np.asarray(INERTIA),
        orientation=orientation,
    )

    assert item.orientation is orientation


def test_an_orientation_tuple_is_drawn_and_keeps_its_euler_sequence() -> None:
    model = make_model()
    roll = uniform("roll", 0, 10)

    item = Inertial.from_random(
        mojo_model=model,
        mass=1.0,
        pos=np.zeros(3),
        diaginertia=np.asarray(INERTIA),
        orientation=(Euler, [roll, 0.0, 0.0], EulerSeq.ZYX),
    )

    expected = twin_draws(lambda: uniform("roll", 0, 10), 1)[0]
    assert isinstance(item.orientation, Euler)
    assert np.array_equal(item.orientation.euler, [expected, 0.0, 0.0])
    assert item.orientation.eulerseq == EulerSeq.ZYX
    assert stored(model, "roll") == expected
    assert model.dists["roll"] is roll


def test_an_orientation_of_the_wrong_kind_is_a_type_error() -> None:
    with pytest.raises(TypeError, match="orientation must be None"):
        Inertial.from_random(
            mojo_model=make_model(),
            mass=1.0,
            pos=np.zeros(3),
            diaginertia=np.asarray(INERTIA),
            orientation=cast(Any, "sideways"),
        )


# redrawing


def test_a_rejected_draw_is_replaced_by_the_next_one_from_the_same_stream() -> None:
    names, rounds = moments_needing_attempts(3)
    model = make_model()

    item = Inertial.from_random(
        mojo_model=model,
        mass=1.0,
        pos=np.zeros(3),
        diaginertia=(
            uniform(names[0], -0.5, 1.0),
            uniform(names[1], -0.5, 1.0),
            uniform(names[2], -0.5, 1.0),
        ),
    )

    # the third attempt is the first physical one, and it is the one that is kept
    assert np.array_equal(required(item.diaginertia), rounds[2])
    assert list(model.named) == names
    assert list(model.dists) == names
    for name, value in zip(names, rounds[2], strict=True):
        assert stored(model, name) == value


def test_a_rejected_draw_is_also_redrawn_without_reseeding() -> None:
    names, rounds = moments_needing_attempts(2)
    model = make_model()
    dists = [uniform(n, -0.5, 1.0).with_seed(SEED).with_trial_num(TRIAL) for n in names]

    item = Inertial.from_random(
        mojo_model=model,
        mass=1.0,
        pos=np.zeros(3),
        diaginertia=(dists[0], dists[1], dists[2]),
        reset_rng=False,
    )

    assert np.array_equal(required(item.diaginertia), rounds[1])


def test_retries_stop_after_max_retries_with_a_runtime_error() -> None:
    model = make_model()
    always_bad = (
        uniform("bad_x", -1.0, 0.0),
        uniform("bad_y", -1.0, 0.0),
        uniform("bad_z", -1.0, 0.0),
    )

    with pytest.raises(
        RuntimeError, match=r"^Failed to generate valid Inertial after 3 retries\.$"
    ):
        Inertial.from_random(
            mojo_model=model,
            mass=1.0,
            pos=np.zeros(3),
            diaginertia=always_bad,
            max_retries=3,
        )

    # nothing sampled by a rejected attempt is left in the values
    assert list(model.named) == []


def test_no_retries_allowed_is_a_runtime_error_before_any_draw() -> None:
    with pytest.raises(RuntimeError, match=r"after 0 retries"):
        Inertial.from_random(
            mojo_model=make_model(),
            mass=1.0,
            pos=np.zeros(3),
            diaginertia=np.asarray(INERTIA),
            max_retries=0,
        )


def test_a_high_rejection_rate_is_warned_about(
    caplog: pytest.LogCaptureFixture,
) -> None:
    always_bad = (
        uniform("bad_x", -1.0, 0.0),
        uniform("bad_y", -1.0, 0.0),
        uniform("bad_z", -1.0, 0.0),
    )

    with caplog.at_level(logging.WARNING), pytest.raises(RuntimeError):
        Inertial.from_random(
            mojo_model=make_model(),
            mass=1.0,
            pos=np.zeros(3),
            diaginertia=always_bad,
            max_retries=4,
        )

    warned = [r for r in caplog.records if "High rejection rate" in r.getMessage()]
    # attempts 3 and 4 are past half of the 4 allowed
    assert len(warned) == 2


def test_an_error_other_than_an_invalid_inertial_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def broken(self: UniformDistribution, *args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise ValueError("the distribution broke")

    monkeypatch.setattr(UniformDistribution, "sample_to_named_value", broken)

    with pytest.raises(ValueError, match="the distribution broke"):
        Inertial.from_random(
            mojo_model=make_model(),
            mass=1.0,
            pos=(uniform("pos_x", -1, 1), 0.0, 0.0),
            diaginertia=np.asarray(INERTIA),
        )

    assert calls == 1


# arguments that are refused


def test_neither_inertia_given_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="diaginertia or fullinertia must be defined"):
        Inertial.from_random(mojo_model=make_model(), mass=1.0, pos=np.zeros(3))


def test_fullinertia_with_an_orientation_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="cannot simultaneously be defiend"):
        Inertial.from_random(
            mojo_model=make_model(),
            mass=1.0,
            pos=np.zeros(3),
            fullinertia=(2.0, 2.0, 2.0, 0.0, 0.0, 0.0),
            orientation=Quat(),
        )


def test_reusing_a_distribution_name_within_one_call_is_a_key_error() -> None:
    with pytest.raises(KeyError, match="already been registered"):
        Inertial.from_random(
            mojo_model=make_model(),
            mass=1.0,
            pos=np.zeros(3),
            diaginertia=(uniform("same", 0.1, 0.2), uniform("same", 0.1, 0.2), 0.1),
        )


def test_reusing_a_registered_distribution_name_in_a_second_call_is_a_key_error() -> (
    None
):
    model = make_model()
    Inertial.from_random(
        mojo_model=model,
        mass=normal("mass", 2.0, 0.1),
        pos=np.zeros(3),
        diaginertia=np.asarray(INERTIA),
    )

    with pytest.raises(KeyError, match="already been registered"):
        Inertial.from_random(
            mojo_model=model,
            mass=normal("mass", 2.0, 0.1),
            pos=np.zeros(3),
            diaginertia=np.asarray(INERTIA),
        )


# values already on the model


def test_a_draw_replaces_a_value_that_was_already_overridden() -> None:
    """Pins the behavior as it is today: the sampled value wins over an override with the same name."""
    overrides = NamedValueDict()
    overrides.update(NamedValue(name=ValueName("mass"), stored_value=np.array([5.0])))
    model = make_model().with_overrides(overrides)

    item = Inertial.from_random(
        mojo_model=model,
        mass=normal("mass", 2.0, 0.1),
        pos=np.zeros(3),
        diaginertia=np.asarray(INERTIA),
    )

    expected = twin_draws(lambda: normal("mass", 2.0, 0.1), 1)[0]
    assert item.mass == expected
    assert stored(model, "mass") == expected


# from_random inside an outer transaction


class NestedCase(NamedTuple):
    """What `i3 = i1 - i2` ends with, worked out from the draws alone."""

    names: tuple[str, str]
    masses: tuple[float, float]
    """The masses of the first pair that works."""

    outer_attempts: int


def nested_case(first_failure: str) -> NestedCase:
    """
    Names for two mass distributions whose draws make the given step fail first, with the outcome that follows.

    A mass is redrawn inside `from_random` while it is not positive, and the outer attempt is redone when `i1 - i2` is not positive. Each distribution keeps one stream throughout, so the pair that finally works is read straight off the two streams.
    """
    for i in range(500):
        names = (f"mass_a_{i}", f"mass_b_{i}")
        streams = [twin_draws(lambda n=n: normal(n, 0.5, 0.6), 60) for n in names]
        positions = [0, 0]
        failures: list[str] = []
        for outer_attempt in range(1, 7):
            drawn: list[float] = []
            for which, step in enumerate(("i1 redraw", "i2 redraw")):
                while streams[which][positions[which]] <= 0:
                    failures.append(step)
                    positions[which] += 1
                drawn.append(streams[which][positions[which]])
                positions[which] += 1
            if drawn[0] - drawn[1] > 0:
                if failures[:1] == [first_failure]:
                    return NestedCase(names, (drawn[0], drawn[1]), outer_attempt)
                break
            failures.append("i3 fail")
    pytest.fail(f"no draws found where {first_failure} comes first")


@pytest.mark.parametrize("first_failure", ["i1 redraw", "i2 redraw", "i3 fail"])
def test_from_random_twice_then_a_subtraction_survives_a_failure_at_any_step(
    first_failure: str,
) -> None:
    """
    Two inertials are drawn inside an outer transaction and subtracted. A non-positive mass is redrawn inside `from_random`; a subtraction that is not physical redoes the whole outer attempt.

    The distributions are seeded once and `reset_rng=False` keeps them that way. With the default, every outer attempt would reseed them and repeat the draws that just failed.
    """
    case = nested_case(first_failure)
    model = make_model()
    masses = tuple(
        normal(n, 0.5, 0.6).with_seed(SEED).with_trial_num(TRIAL) for n in case.names
    )
    outer_attempts = 0
    results: list[tuple[Inertial, Inertial, Inertial]] = []

    for attempt in model.transaction(retry_on=ValueError, max_retries=10):
        with attempt:
            outer_attempts += 1
            i1 = Inertial.from_random(
                mojo_model=model,
                mass=masses[0],
                pos=np.zeros(3),
                diaginertia=np.asarray((0.5, 0.5, 0.5)),
                reset_rng=False,
            )
            i2 = Inertial.from_random(
                mojo_model=model,
                mass=masses[1],
                pos=np.zeros(3),
                diaginertia=np.asarray(INERTIA),
                reset_rng=False,
            )
            results.append((i1, i2, i1 - i2))

    i1, i2, i3 = results[-1]
    assert (i1.mass, i2.mass) == case.masses
    assert i3.mass == i1.mass - i2.mass
    assert outer_attempts == case.outer_attempts
    # what the rejected outer attempts registered is gone, so each name is there once with its final value
    assert list(model.dists) == list(case.names)
    assert list(model.named) == list(case.names)
    assert stored(model, case.names[0]) == i1.mass
    assert stored(model, case.names[1]) == i2.mass
