"""
What SensAI can say about a job's input distributions and what each trial drew from them: the distributions themselves, one trial's draws, and the trials that drew an input far from its middle.

Each function reads the job's saved distributions and the trials' saved draws through `trial_dists.py`, the same code the Dojo's distributions panel uses, so SensAI and the panel cannot disagree on a draw, its unit or its z-score. Every function returns words, or for `trials_beyond` the trial numbers the plot agent pins, so the model never retypes a number it looked up.

How far out a draw is: where the Dojo's panel gives a z-score (a distribution with a mean and a spread, see `has_z_score`) it is that z-score. For any other distribution, a uniform say, the draw's percentile is read as the equivalent on a normal curve (the 97.7th percentile is 2). The answer says which of the two it is.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import stochas
from pydantic import BaseModel

from mujoco_mojo.utils.layers.dojo.trial_dists import (
    extract_sampled_labels,
    has_z_score,
    read_distributions,
    read_named_values,
    safe_param,
    sampled_values_in_dist_unit,
    split_nominal,
    z_and_percentile,
)
from mujoco_mojo.utils.statusing import JobStatus

from .job_report import trial_numbers

__all__ = [
    "Draw",
    "Outliers",
    "describe_distributions",
    "describe_input_outliers",
    "describe_trial_inputs",
    "find_outliers",
    "trials_beyond",
]

# a draw at the very edge of its distribution has a percentile of 0 or 100, which is infinitely far out on a normal curve, so it is kept just inside
_TAIL = 1e-12

_MAX_LINE = 400
_MAX_OUTLIERS_SHOWN = 30


class Draw(BaseModel):
    """One trial's draw of one input, and how far out it is."""

    trial: int
    value: float
    sigmas: float
    """Signed distance from the middle of the distribution, in standard deviations."""


class Outliers(BaseModel):
    """The trials that drew an input at least some distance from its middle."""

    name: str
    dist_type: str
    unit: str
    """The unit the distribution was declared in, empty when it has none."""
    exact: bool
    """True when `sigmas` are z-scores, False when they are read off the percentile."""
    drawn: int
    """How many trials have a numeric draw of this input."""
    beyond: list[Draw]


def _dists(job: JobStatus) -> stochas.DistributionDict | str:
    """The job's distributions, or the sentence that says why there are none to give."""
    try:
        found = read_distributions(job.workdir)
    except ValueError as exc:
        return f"The job's distributions could not be read: {exc}"
    if not found:
        return "This job has no input distributions: nothing was sampled."
    return found


def _cut(text: str, length: int = _MAX_LINE) -> str:
    text = " ".join(text.split())
    return text if len(text) <= length else text[: length - 3].rstrip() + "..."


def _param_text(name: str, value: object) -> str:
    shown = safe_param(value)
    return f"{name}={shown:.6g}" if isinstance(shown, float) else f"{name}={shown}"


def _describe_dist(dist: stochas.AnyDist) -> str:
    nominal, label = split_nominal(dist.nominal if dist.has_nominal else None)
    facts: list[str] = []
    if dist.category:
        facts.append(f"category {dist.category}")
    if dist.unit is not None:
        facts.append(f"unit {dist.unit}")
    if label is not None:
        facts.append(f"nominal {label}")
    elif nominal is not None:
        facts.append(f"nominal {nominal:.6g}")
    facts += [_param_text(k, v) for k, v in dist.table_params.items()]
    if dist.display_name:
        facts.append(f'shown as "{dist.display_name}"')
    if dist.source:
        facts.append(f"source {dist.source}")
    line = f"- {dist.name} ({dist.dist_type}): {', '.join(facts)}"
    if dist.comment:
        line += f". {dist.comment}"
    return _cut(line)


def describe_distributions(job: JobStatus) -> str:
    """The input distributions the job's trials were drawn from: each one's name, type, category, unit, nominal value, parameters (which say its range or spread), and any display name, source and comment."""
    dists = _dists(job)
    if isinstance(dists, str):
        return dists
    lines = [
        f"{len(dists)} input distribution(s), which each trial drew its inputs from:"
    ]
    lines += [_describe_dist(d) for d in dists.values()]
    return "\n".join(lines)


def _unit_text(dist: stochas.AnyDist) -> str:
    return f" {dist.unit}" if dist.unit is not None else ""


def _draw_text(dist: stochas.AnyDist, named_raw: dict[str, object]) -> str:
    labels = extract_sampled_labels(named_raw, dist.name)
    if labels:
        return ", ".join(labels)
    values = sampled_values_in_dist_unit(named_raw, dist)
    if not values:
        return "no number or label saved (a permutation, or nothing)"
    z_score, percentile = z_and_percentile(dist, values[0])
    text = f"{values[0]:.6g}{_unit_text(dist)}"
    if z_score is not None:
        text += f", {z_score:+.2f} standard deviations from the mean"
    if percentile is not None:
        text += f", percentile {percentile:g}"
    if len(values) > 1:
        text += f" (and {len(values) - 1} more value{'s' if len(values) > 2 else ''})"
    return text


def _unknown_trial(job: JobStatus, trial_num: int) -> str | None:
    """The sentence that says the trial is not there, or None when it is."""
    if trial_num in job.trial_nums:
        return None
    if not job.trial_nums:
        return "This job has no trials yet."
    return f"There is no trial {trial_num} in this job. Its trials are {min(job.trial_nums)}-{max(job.trial_nums)}."


def describe_trial_inputs(job: JobStatus, trial_num: int) -> str:
    """What one trial drew for each input, in the unit the input was declared in, with how far from the mean the draw is."""
    if (missing := _unknown_trial(job, trial_num)) is not None:
        return missing
    dists = _dists(job)
    if isinstance(dists, str):
        return dists
    named_raw = read_named_values(job.trial_num_to_path(trial_num))
    if not named_raw:
        return f"Trial {trial_num} saved no sampled values (it may not have started)."
    lines = [f"Trial {trial_num} drew:"]
    lines += [f"  {d.name}: {_draw_text(d, named_raw)}" for d in dists.values()]
    return "\n".join(lines)


def _pick_dist(dists: stochas.DistributionDict, name: str) -> stochas.AnyDist | str:
    """The input `name` means: the one with exactly that name (ignoring case), else the only one whose name contains it, else the sentence that says which names there are."""
    wanted = name.strip().lower()
    names = list(dists)
    exact = [n for n in names if n.lower() == wanted]
    partial = [n for n in names if wanted in n.lower()]
    chosen = exact or (partial if wanted and len(partial) == 1 else [])
    if chosen:
        return dists[chosen[0]]
    return f"No input is named '{name}'. The inputs are: {', '.join(names)}."


def _sigmas(dist: stochas.AnyDist, value: float) -> float | None:
    """How many standard deviations `value` is from the middle of `dist`: the z-score where there is one, else the percentile read as the same on a normal curve. None when the distribution cannot say."""
    if has_z_score(dist):
        return z_and_percentile(dist, value)[0]
    try:
        percentile = min(max(float(dist.cdf(value)), _TAIL), 1 - _TAIL)
    except Exception:
        return None
    return NormalDist().inv_cdf(percentile)


def find_outliers(job: JobStatus, name: str, min_sigma: float) -> Outliers | str:
    """
    The trials that drew the input `name` (its name or part of it) at least `min_sigma` standard deviations from the middle of its distribution, or the sentence that says why there is nothing to give.

    Every trial's saved draws are read, so call it off the event loop.
    """
    if not math.isfinite(min_sigma) or min_sigma <= 0:
        return f"min_sigma must be a number above 0, such as 2, not {min_sigma}."
    dists = _dists(job)
    if isinstance(dists, str):
        return dists
    dist = _pick_dist(dists, name)
    if isinstance(dist, str):
        return dist

    draws: list[Draw] = []
    for trial in sorted(job.trial_nums):
        values = sampled_values_in_dist_unit(
            read_named_values(job.trial_num_to_path(trial)), dist
        )
        if not values:
            continue
        sigmas = _sigmas(dist, values[0])
        if sigmas is not None:
            draws.append(Draw(trial=trial, value=values[0], sigmas=sigmas))
    if not draws:
        return f"No trial has a number saved for '{dist.name}', so there is no distance to measure. An input drawn as a label or a permutation has none."
    return Outliers(
        name=dist.name,
        dist_type=dist.dist_type,
        unit=str(dist.unit) if dist.unit is not None else "",
        exact=has_z_score(dist),
        drawn=len(draws),
        beyond=[d for d in draws if abs(d.sigmas) >= min_sigma],
    )


def trials_beyond(job: JobStatus, name: str, min_sigma: float) -> list[int] | str:
    """The numbers of the trials that drew the input `name` at least `min_sigma` standard deviations from the middle of its distribution, in order, or the sentence that says why there are none to give. Reads every trial's draws, so call it off the event loop."""
    found = find_outliers(job, name, min_sigma)
    if isinstance(found, str):
        return found
    return sorted(d.trial for d in found.beyond)


def describe_input_outliers(
    job: JobStatus, name: str, min_sigma: float = 2.0, count: int = 15
) -> str:
    """The trials that drew an input far from its mean, most extreme first, with each draw and its distance. Reads every trial's draws, so call it off the event loop."""
    found = find_outliers(job, name, min_sigma)
    if isinstance(found, str):
        return found
    head = (
        f"{found.name} ({found.dist_type}): {len(found.beyond)} of {found.drawn} "
        f"trials drew it {min_sigma:g} or more standard deviations from its mean."
    )
    if not found.exact:
        head += " It is not measured by a z-score, so each distance is what the draw's percentile would be on a normal curve."
    if not found.beyond:
        return head
    ordered = sorted(found.beyond, key=lambda d: -abs(d.sigmas))
    shown = ordered[: max(1, min(count, _MAX_OUTLIERS_SHOWN))]
    unit = f" {found.unit}" if found.unit else ""
    lines = [head, "Most extreme first:"]
    lines += [f"  trial {d.trial}: {d.value:.6g}{unit}, {d.sigmas:+.2f}" for d in shown]
    lines.append(f"All of them: {trial_numbers(d.trial for d in ordered)}.")
    return "\n".join(lines)
