"""SLURM submission settings, limit checks, and scheduler queries."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field, field_validator

from mujoco_mojo.base import MojoBaseModel
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.statusing import JobStatus

__all__ = [
    "UNKNOWN_LIMIT",
    "SlurmConfig",
    "SlurmJob",
    "SlurmSubmission",
    "array_problem",
    "build_submission_script",
    "cpu_problem",
    "mem_problem",
    "normalize_to_mb",
    "parse_job_id",
    "slurm_job_active",
    "slurm_time_to_seconds",
    "time_problem",
]

logger = get_logger(__name__)

UNKNOWN_LIMIT = "<UNKNOWN>"
"""What the limit lookups return when SLURM cannot say."""

_MEMORY_SIZE = re.compile(r"\s*(\d+(?:\.\d+)?|\.\d+)\s*([KMGTP]?)B?\s*")


# --- parsing SLURM's own formats ---


def normalize_to_mb(mem_str: str) -> int:
    """Converts SLURM memory strings (e.g., '1000', '1G', '1024M', '125.9G') to integer MB, or 0 if the string isn't a recognizable size. Decimal values are supported, and a bare number is MB like it is for SLURM."""
    match = _MEMORY_SIZE.fullmatch(mem_str.upper())
    if not match:
        return 0

    number, unit = match.groups()
    value = float(number)

    # SLURM units are powers of 1024
    multipliers = {
        "K": 1 / 1024,
        "M": 1,
        "G": 1024,
        "T": 1024**2,
        "P": 1024**3,
    }
    return int(value * multipliers.get(unit or "M", 1))


def slurm_time_to_seconds(time_str: str) -> int:
    """Converts a SLURM time limit to total seconds, or -1 for `UNLIMITED`. Accepts every format `--time` does: `minutes`, `minutes:seconds`, `hours:minutes:seconds`, `days-hours`, `days-hours:minutes`, and `days-hours:minutes:seconds`."""
    time_str = time_str.strip()
    if time_str.upper() in {"UNLIMITED", "INFINITE"}:
        return -1

    # with a day count, what follows is hours[:minutes[:seconds]]
    if "-" in time_str:
        days_part, rest = time_str.split("-", 1)
        hms = [int(p) for p in rest.split(":")]
        hours, minutes, seconds = hms + [0] * (3 - len(hms))
        return int(days_part) * 86400 + hours * 3600 + minutes * 60 + seconds

    parts = [int(p) for p in time_str.split(":")]
    if len(parts) == 3:  # HH:MM:SS
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:  # MM:SS
        return parts[0] * 60 + parts[1]
    if len(parts) == 1:  # MM
        return parts[0] * 60
    return 0


def parse_job_id(sbatch_output: str) -> str | None:
    """The job id from `sbatch --parsable` output (`12345`, or `12345;cluster` on a federated setup), or `None` if there is none."""
    first = sbatch_output.strip().split(";")[0].strip()
    return first if first.isdigit() else None


# --- configuration ---


class SlurmConfig(MojoBaseModel):
    """
    Everything a SLURM submission needs that the job itself doesn't already know.

    The interactive wizard fills one in from its prompts, and Python code can build one directly and pass it to `MojoRunner.submit_slurm`; both use the same submission code, so a job submitted either way gets the same script.
    """

    job_name: str | None = None
    """Name shown in the queue. Defaults to `mojo-sim-` followed by the job's id."""

    partition: str | None = None
    """Partition to submit to. `None` leaves the choice to SLURM's default."""

    cpus_per_task: int = Field(default=1, ge=1)
    """CPUs for each trial."""

    mem: str | None = None
    """Memory for each trial as a SLURM size, decimals allowed (`512M`, `4G`, `1.5G`). `None` leaves it to the cluster default."""

    time_limit: str = "01:00:00"
    """Time limit for each trial, in any format `sbatch --time` accepts."""

    max_concurrent: int | None = Field(default=None, ge=1)
    """Most trials that may run at once. `None` lets SLURM decide."""

    add_root_to_pythonpath: bool = True
    """Whether the submission script adds `project_root` to `PYTHONPATH`, so the generator and runtime can be imported on the compute node."""

    project_root: Path = Field(default_factory=lambda: Path.cwd().resolve())
    """Directory the trials `cd` into before they run."""

    @field_validator("mem")
    @classmethod
    def _mem_is_a_size(cls, value: str | None) -> str | None:
        if value is not None and normalize_to_mb(value) <= 0:
            msg = (
                f"'{value}' is not a SLURM memory size (for example 512M, 4G, or 1.5G)."
            )
            raise ValueError(msg)
        return value

    @field_validator("time_limit")
    @classmethod
    def _time_is_a_slurm_time(cls, value: str) -> str:
        try:
            slurm_time_to_seconds(value)
        except ValueError:
            msg = f"'{value}' is not a SLURM time limit (for example 01:00:00, 90, or 1-12:00:00)."
            raise ValueError(msg) from None
        return value


@dataclass
class SlurmJob:
    """A job that is ready to be turned into a submission script."""

    status: JobStatus
    """The job's status tracker, already written to `job_status.json`."""

    to_run: list[int]
    """Trial numbers that still need to run."""

    overrides_path: Path
    """Where the global overrides are persisted, if there are any."""

    has_overrides: bool
    """Whether `overrides_path` holds overrides the workers need."""


@dataclass
class SlurmSubmission:
    """What came of writing, and possibly submitting, a submission script."""

    script_path: Path
    """The submission script that was written."""

    submitted: bool = False
    """Whether `sbatch` accepted it."""

    job_id: str | None = None
    """The SLURM job id, once submitted."""

    message: str = ""
    """What `sbatch` printed, or why it failed."""


# --- checking a request against the cluster ---


def cpu_problem(cpus: int, limit: str) -> str | None:
    """A description of how `cpus` exceeds the node CPU `limit`, or `None` if it fits or the limit is unknown."""
    if limit == UNKNOWN_LIMIT:
        return None
    try:
        node_cpus = int(limit)
    except ValueError:
        return None
    if cpus > node_cpus:
        return f"Requested CPUs ({cpus}) exceeds the physical node limit ({limit})."
    return None


def mem_problem(mem: str | None, limit: str) -> str | None:
    """A description of how `mem` exceeds the node memory `limit`, or `None` if it fits, was not requested, or the limit is unknown."""
    if mem is None:
        return None
    limit_mb = normalize_to_mb(limit)
    if limit_mb > 0 and normalize_to_mb(mem) > limit_mb:
        return f"Requested memory ({mem}) exceeds the partition node limit ({limit})."
    return None


def time_problem(time_limit: str, limit: str) -> str | None:
    """A description of how `time_limit` exceeds the partition's `MaxTime`, or `None` if it fits or the limit is unknown or unlimited."""
    if limit == UNKNOWN_LIMIT:
        return None
    try:
        requested = slurm_time_to_seconds(time_limit)
        allowed = slurm_time_to_seconds(limit)
    except ValueError:
        return None
    # -1 means unlimited
    if allowed != -1 and requested > allowed:
        return f"Requested time ({time_limit}) exceeds partition MaxTime ({limit})."
    return None


def array_problem(n_trials: int, max_array: int) -> str | None:
    """A description of how `n_trials` exceeds SLURM's `MaxArraySize`, or `None` if it fits."""
    if n_trials > max_array:
        return f"Trial count ({n_trials}) exceeds SLURM MaxArraySize ({max_array})."
    return None


# --- the submission script ---


def build_submission_script(
    *,
    job_name: str,
    array_range: str,
    workdir: Path,
    config: SlurmConfig,
    worker_command: str,
    extra_sbatch_lines: Sequence[str] = (),
    extra_env_lines: Sequence[str] = (),
) -> str:
    """
    The text of the sbatch script for a job array, one task per trial.

    Args:
        job_name: Name shown in the queue.
        array_range: The trials to run as SLURM writes them (`0-2,5`), without the concurrency throttle, which is added from `config`.
        workdir: The job's workdir, where the per-trial logs go.
        config: The resources to ask for.
        worker_command: What each array task runs.
        extra_sbatch_lines: Extra `#SBATCH` lines from the settings files.
        extra_env_lines: Extra `export` lines from the settings files.

    """
    array = array_range
    if config.max_concurrent is not None:
        array += f"%{config.max_concurrent}"

    directives = [
        f"#SBATCH --job-name={job_name}",
        f"#SBATCH --array={array}",
        f"#SBATCH --output={workdir}/logs/trial_%a.log",
        f"#SBATCH --cpus-per-task={config.cpus_per_task}",
    ]
    if config.mem is not None:
        directives.append(f"#SBATCH --mem={config.mem}")
    directives.append(f"#SBATCH --time={config.time_limit}")
    if config.partition:
        directives.append(f"#SBATCH --partition={config.partition}")
    directives.extend(extra_sbatch_lines)

    setup = [f"cd {config.project_root}"]
    if config.add_root_to_pythonpath:
        setup.append(f"export PYTHONPATH=$PYTHONPATH:{config.project_root}")
    if extra_env_lines:
        setup.append("")
        setup.append(
            "# Custom environment variables (global and/or project settings.toml)"
        )
        setup.extend(extra_env_lines)

    lines = [
        "#!/bin/bash",
        *directives,
        "",
        "# Move to the project root so imports work",
        *setup,
        "",
        "# Avoid concurrent array tasks racing to write .pyc files into the shared venv",
        "export PYTHONDONTWRITEBYTECODE=1",
        "",
        "# Execute the worker command",
        worker_command,
    ]
    return "\n".join(lines) + "\n"


# --- asking the scheduler ---


def slurm_job_active(job_id: str) -> bool | None:
    """
    Whether SLURM still has tasks of `job_id` queued or running.

    Returns `None` when that can't be determined (no `squeue` on this machine, or it failed for another reason), so callers can carry on without the scheduler's opinion. A job SLURM has already forgotten counts as no longer active.
    """
    try:
        result = subprocess.run(
            ["squeue", "-h", "-j", job_id, "-o", "%T"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0:
        return bool(result.stdout.strip())
    if "Invalid job id" in result.stderr:
        return False
    return None
