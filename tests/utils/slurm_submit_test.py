import io
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt

import mujoco_mojo as mojo
import mujoco_mojo.utils.runner as runner_module
from mujoco_mojo.stochas import NamedValueDict
from mujoco_mojo.utils.runner import MojoRunner, MonteCarloConfig
from mujoco_mojo.utils.slurm import (
    SlurmConfig,
    array_problem,
    build_submission_script,
    cpu_problem,
    mem_problem,
    parse_job_id,
    slurm_job_active,
    time_problem,
)
from mujoco_mojo.utils.defaults import NAMED_VALUES_FNAME
from mujoco_mojo.utils.statusing import JOB_STATUS_FNAME, JobStatus


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keeps a real `~/.mujoco-mojo` or project settings file out of the generated scripts."""
    monkeypatch.setattr(
        "mujoco_mojo.settings.GLOBAL_SETTINGS_FILE", tmp_path / "no-global.toml"
    )
    monkeypatch.setattr(
        "mujoco_mojo.settings.project_settings_file",
        lambda: tmp_path / "no-project" / "settings.toml",
    )


def _generate(mojo_model: Any, overrides: Any, *args: Any, **kwargs: Any) -> Any:
    return mojo_model


def _runner(workdir: Path, n_trial: int = 3, **extra: Any) -> MojoRunner:
    return MojoRunner(
        generator=_generate,
        generator_path="sim.generate",
        workdir=workdir,
        config=MonteCarloConfig(n_trial=n_trial, n_proc=1, resume=True),
        **extra,
    )


def _console() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    return Console(file=buffer, width=300, force_terminal=False), buffer


class FakeSlurm:
    """Stands in for `sbatch`, `scontrol`, and `squeue`, recording what was called."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.sbatch_stdout = "4242\n"
        self.sbatch_returncode = 0
        self.sbatch_stderr = ""

    def __call__(
        self, command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess:
        self.calls.append(list(command))
        if command[0] == "sbatch":
            return subprocess.CompletedProcess(
                command, self.sbatch_returncode, self.sbatch_stdout, self.sbatch_stderr
            )
        # scontrol and anything else: the cluster cannot say, so no limits are known
        return subprocess.CompletedProcess(command, 1, "", "")

    @property
    def sbatch_calls(self) -> list[list[str]]:
        return [call for call in self.calls if call[0] == "sbatch"]


@pytest.fixture
def slurm(monkeypatch: pytest.MonkeyPatch) -> FakeSlurm:
    fake = FakeSlurm()
    monkeypatch.setattr(subprocess, "run", fake)
    return fake


# --- the configuration ---


def test_the_config_defaults_ask_for_little() -> None:
    config = SlurmConfig()

    assert config.cpus_per_task == 1
    assert config.mem is None
    assert config.partition is None
    assert config.max_concurrent is None
    assert config.time_limit == "01:00:00"
    assert config.add_root_to_pythonpath is True
    assert config.project_root == Path.cwd().resolve()


@pytest.mark.parametrize("mem", ["512M", "4G", "1.5G", "125.9G", "2048", "1T"])
def test_the_config_accepts_slurm_memory_sizes(mem: str) -> None:
    assert SlurmConfig(mem=mem).mem == mem


@pytest.mark.parametrize("mem", ["", "lots", "4 gigs", "1.2.3G"])
def test_the_config_rejects_what_is_not_a_memory_size(mem: str) -> None:
    with pytest.raises(ValidationError, match="memory size"):
        SlurmConfig(mem=mem)


@pytest.mark.parametrize(
    "time_limit",
    ["01:00:00", "90", "5:30", "1-12", "1-12:30", "1-12:30:15", "UNLIMITED"],
)
def test_the_config_accepts_every_slurm_time_format(time_limit: str) -> None:
    assert SlurmConfig(time_limit=time_limit).time_limit == time_limit


@pytest.mark.parametrize("time_limit", ["soon", "1.5", "1-"])
def test_the_config_rejects_what_is_not_a_time(time_limit: str) -> None:
    with pytest.raises(ValidationError, match="time limit"):
        SlurmConfig(time_limit=time_limit)


def test_cpus_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        SlurmConfig(cpus_per_task=0)


def test_the_concurrency_limit_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        SlurmConfig(max_concurrent=0)


# --- the script ---


def _script(config: SlurmConfig, **kwargs: Any) -> str:
    return build_submission_script(
        job_name=kwargs.pop("job_name", "my-job"),
        array_range=kwargs.pop("array_range", "0-4"),
        workdir=Path("/work"),
        config=config,
        worker_command=kwargs.pop("worker_command", "mujoco-mojo run single"),
        **kwargs,
    )


def test_a_full_request_becomes_sbatch_lines() -> None:
    config = SlurmConfig(
        partition="compute",
        cpus_per_task=4,
        mem="1.5G",
        time_limit="1-12:00:00",
        max_concurrent=2,
        project_root=Path("/proj"),
    )

    script = _script(config)

    assert script.startswith("#!/bin/bash\n")
    assert "#SBATCH --job-name=my-job\n" in script
    assert "#SBATCH --array=0-4%2\n" in script
    assert "#SBATCH --output=/work/logs/trial_%a.log\n" in script
    assert "#SBATCH --cpus-per-task=4\n" in script
    assert "#SBATCH --mem=1.5G\n" in script
    assert "#SBATCH --time=1-12:00:00\n" in script
    assert "#SBATCH --partition=compute\n" in script
    assert "cd /proj\n" in script
    assert "export PYTHONPATH=$PYTHONPATH:/proj\n" in script
    assert script.rstrip().endswith("mujoco-mojo run single")


def test_what_was_not_asked_for_is_left_out() -> None:
    script = _script(SlurmConfig(add_root_to_pythonpath=False))

    assert "--mem" not in script
    assert "--partition" not in script
    assert "%" not in script.split("--array=")[1].split("\n")[0]
    assert "PYTHONPATH" not in script


def test_extra_lines_from_settings_are_added() -> None:
    script = _script(
        SlurmConfig(),
        extra_sbatch_lines=["#SBATCH --account=proj123"],
        extra_env_lines=['export MY_VAR="x"'],
    )

    assert "#SBATCH --account=proj123\n" in script
    assert 'export MY_VAR="x"\n' in script
    # the directives stay together, ahead of the first command
    assert script.index("--account") < script.index("cd ")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("12345\n", "12345"),
        ("12345;cluster\n", "12345"),
        ("Submitted batch job 5", None),
        ("", None),
    ],
)
def test_parse_job_id(text: str, expected: str | None) -> None:
    assert parse_job_id(text) == expected


# --- checking a request against the cluster ---


def test_limit_problems_describe_what_exceeds() -> None:
    assert "CPUs (8)" in str(cpu_problem(8, "4"))
    assert "memory (4G)" in str(mem_problem("4G", "2G"))
    assert "time (2-00:00:00)" in str(time_problem("2-00:00:00", "1-00:00:00"))
    assert "(2000)" in str(array_problem(2000, 1001))


def test_nothing_is_a_problem_when_it_fits_or_is_unknown() -> None:
    assert cpu_problem(4, "4") is None
    assert cpu_problem(64, "<UNKNOWN>") is None
    assert mem_problem(None, "2G") is None
    assert mem_problem("1.5G", "2G") is None
    assert mem_problem("64G", "<UNKNOWN>") is None
    assert time_problem("12:00:00", "1-00:00:00") is None
    assert time_problem("99-00:00:00", "UNLIMITED") is None
    assert time_problem("99-00:00:00", "<UNKNOWN>") is None
    assert array_problem(10, 1001) is None


# --- asking the scheduler ---


@pytest.mark.parametrize(
    ("returncode", "stdout", "stderr", "expected"),
    [
        (0, "RUNNING\nPENDING\n", "", True),
        (0, "", "", False),
        (1, "", "slurm_load_jobs error: Invalid job id specified", False),
        (1, "", "squeue: error: Unable to contact slurm controller", None),
    ],
)
def test_slurm_job_active(
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
    stdout: str,
    stderr: str,
    expected: bool | None,
) -> None:
    def fake(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    monkeypatch.setattr(subprocess, "run", fake)

    assert slurm_job_active("42") is expected


def test_slurm_job_active_is_unknown_without_squeue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        raise FileNotFoundError("squeue")

    monkeypatch.setattr(subprocess, "run", missing)

    assert slurm_job_active("42") is None


# --- preparing the workdir without asking anything ---


def test_prepare_creates_the_logs_folder_and_the_status_file(tmp_path: Path) -> None:
    runner = _runner(tmp_path / "work")
    (tmp_path / "work").mkdir()

    job = runner.prepare_slurm_job()

    assert job is not None
    assert job.to_run == [0, 1, 2]
    assert (tmp_path / "work" / "logs").is_dir()
    status = JobStatus.model_validate_json(
        (tmp_path / "work" / JOB_STATUS_FNAME).read_text()
    )
    assert status.n_trial == 3
    assert status.slurm_job_id is None
    assert not job.has_overrides


def _sampling_generator(
    mojo_model: Any, overrides: Any, *args: Any, **kwargs: Any
) -> Any:
    mojo_model.sample_dist(
        mojo.NormalDistribution(
            name=mojo.DistName("stiffness"), mu=1.0, sigma=0.1, category="springs"
        )
    )
    return mojo_model


def test_prepare_persists_global_overrides_for_the_workers(tmp_path: Path) -> None:
    from numpydantic import NDArray

    # a real overrides file: the named values a trial wrote, which is what `--overrides` takes
    sampler = MojoRunner(
        generator=_sampling_generator,
        workdir=tmp_path / "sampled",
        config=MonteCarloConfig(n_trial=1, n_proc=1),
    )
    sampler.run()
    named_file = next((tmp_path / "sampled" / "trials").rglob(NAMED_VALUES_FNAME))
    overrides = NamedValueDict[NDArray].model_validate_json(named_file.read_text())
    assert len(overrides) > 0

    runner = _runner(tmp_path / "work")
    job = runner.prepare_slurm_job(overrides)

    assert job is not None
    assert job.has_overrides
    assert job.overrides_path.read_text() == overrides.model_dump_json()
    assert f'--overrides "{job.overrides_path}"' in runner.slurm_worker_command(job)


def test_prepare_only_queues_trials_that_are_not_done_when_resuming(
    tmp_path: Path,
) -> None:
    workdir = tmp_path / "work"
    runner = _runner(workdir)
    runner.run(trial_nums=[0, 1])

    job = runner.prepare_slurm_job()

    assert job is not None
    assert job.to_run == [2]


def test_prepare_has_nothing_to_do_when_every_trial_is_done(tmp_path: Path) -> None:
    runner = _runner(tmp_path / "work")
    runner.run()

    assert runner.prepare_slurm_job() is None


# --- submitting without prompts ---


def test_dry_run_writes_the_script_and_submits_nothing(
    tmp_path: Path, slurm: FakeSlurm
) -> None:
    runner = _runner(tmp_path / "work")
    console, output = _console()

    submission = runner.submit_slurm(
        SlurmConfig(job_name="dry", mem="1.5G"), submit=False, console=console
    )

    assert submission is not None
    assert not submission.submitted
    assert slurm.sbatch_calls == []
    script = submission.script_path.read_text()
    assert "#SBATCH --job-name=dry\n" in script
    assert "#SBATCH --mem=1.5G\n" in script
    assert "Nothing was submitted" in output.getvalue()
    assert (tmp_path / "work" / "logs").is_dir()
    assert (tmp_path / "work" / JOB_STATUS_FNAME).exists()


def test_submit_runs_sbatch_and_saves_the_job_id(
    tmp_path: Path, slurm: FakeSlurm
) -> None:
    runner = _runner(tmp_path / "work")
    console, output = _console()

    submission = runner.submit_slurm(SlurmConfig(), console=console)

    assert submission is not None
    assert submission.submitted
    assert submission.job_id == "4242"
    assert slurm.sbatch_calls == [["sbatch", "--parsable", str(submission.script_path)]]
    saved = json.loads((tmp_path / "work" / JOB_STATUS_FNAME).read_text())
    assert saved["slurm_job_id"] == "4242"
    assert "Submitted batch job 4242" in output.getvalue()


def test_a_failed_sbatch_is_reported_and_no_job_id_is_saved(
    tmp_path: Path, slurm: FakeSlurm
) -> None:
    slurm.sbatch_returncode = 1
    slurm.sbatch_stderr = "sbatch: error: invalid partition specified: nope\n"
    runner = _runner(tmp_path / "work")

    submission = runner.submit_slurm(SlurmConfig(), console=_console()[0])

    assert submission is not None
    assert not submission.submitted
    assert "invalid partition" in submission.message
    saved = json.loads((tmp_path / "work" / JOB_STATUS_FNAME).read_text())
    assert saved["slurm_job_id"] is None


def test_submit_without_sbatch_installed_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        if command[0] == "sbatch":
            raise FileNotFoundError("sbatch")
        return subprocess.CompletedProcess(command, 1, "", "")

    monkeypatch.setattr(subprocess, "run", missing)
    runner = _runner(tmp_path / "work")

    submission = runner.submit_slurm(SlurmConfig(), console=_console()[0])

    assert submission is not None
    assert not submission.submitted
    assert "Could not run sbatch" in submission.message


def test_a_request_over_a_cluster_limit_is_an_error_unless_skipped(
    tmp_path: Path, slurm: FakeSlurm, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        MojoRunner, "get_slurm_cpu_limit", staticmethod(lambda partition_name: "4")
    )
    monkeypatch.setattr(
        MojoRunner,
        "get_slurm_node_mem_limit",
        staticmethod(lambda partition_name: "2G"),
    )
    config = SlurmConfig(cpus_per_task=16, mem="8G")

    with pytest.raises(ValueError, match="CPUs \\(16\\)") as raised:
        _runner(tmp_path / "work").submit_slurm(config, console=_console()[0])
    assert "memory (8G)" in str(raised.value)
    assert slurm.sbatch_calls == []

    submission = _runner(tmp_path / "work").submit_slurm(
        config, skip_checks=True, console=_console()[0]
    )
    assert submission is not None
    assert submission.submitted


def test_submit_has_nothing_to_do_when_every_trial_is_done(
    tmp_path: Path, slurm: FakeSlurm
) -> None:
    runner = _runner(tmp_path / "work")
    runner.run()
    console, output = _console()

    assert runner.submit_slurm(SlurmConfig(), console=console) is None
    assert slurm.sbatch_calls == []
    assert "Nothing to submit" in output.getvalue()


def test_the_worker_command_passes_the_arguments_and_the_padding(
    tmp_path: Path,
) -> None:
    runner = _runner(
        tmp_path / "work", n_trial=200, args=["a"], kwargs={"mode": "fast"}
    )
    (tmp_path / "work").mkdir()
    job = runner.prepare_slurm_job()
    assert job is not None

    command = runner.slurm_worker_command(job)

    assert '--generator "sim.generate"' in command
    assert '--arg "a"' in command
    assert '--kwarg "mode=fast"' in command
    assert "--padding 3" in command
    assert "--trial-num $SLURM_ARRAY_TASK_ID" in command


# --- the wizard fills a config and uses the same code ---


class ScriptedPrompts:
    """Answers the wizard's prompts by matching a fragment of the question."""

    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers
        self.asked: list[str] = []

    def __call__(self, question: str, **kwargs: Any) -> Any:
        self.asked.append(question)
        for fragment, answer in self.answers.items():
            if fragment in question:
                return answer
        pytest.fail(f"unexpected prompt: {question!r}")


def _script_the_wizard(
    monkeypatch: pytest.MonkeyPatch, answers: dict[str, Any]
) -> ScriptedPrompts:
    prompts = ScriptedPrompts(answers)
    monkeypatch.setattr(Prompt, "ask", staticmethod(prompts))
    monkeypatch.setattr(IntPrompt, "ask", staticmethod(prompts))
    monkeypatch.setattr(Confirm, "ask", staticmethod(prompts))
    monkeypatch.setattr(
        MojoRunner, "get_slurm_partitions", staticmethod(lambda: ([], None))
    )
    # PYTHONPATH may or may not already hold the project root on this machine
    monkeypatch.delenv("PYTHONPATH", raising=False)
    return prompts


WIZARD_ANSWERS: dict[str, Any] = {
    "[white]Job Name[/]": "wizard-job",
    "[white]Partition[/]": "compute",
    "[white]CPUs per task[/]": 2,
    "[white]Memory per node[/]": "1.5G",
    "[white]Time limit[/]": "12:00:00",
    "[white]Max concurrent tasks[/]": "2",
    "automatically include it": True,
    "trials to SLURM now": True,
    "up to date": False,
}


def test_the_wizard_produces_the_script_the_non_interactive_path_does(
    tmp_path: Path, slurm: FakeSlurm, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = tmp_path / "work"
    _script_the_wizard(monkeypatch, WIZARD_ANSWERS)
    wizard_runner = _runner(workdir)
    (workdir).mkdir()

    had_fails = wizard_runner.orchestrate_slurm_monte_carlo()

    assert had_fails is False
    wizard_script = (workdir / "mujoco_mojo_submit.sh").read_text()

    # the same request, given as a config to the prompt-free path
    config = SlurmConfig(
        job_name="wizard-job",
        partition="compute",
        cpus_per_task=2,
        mem="1.5G",
        time_limit="12:00:00",
        max_concurrent=2,
    )
    _runner(workdir).submit_slurm(config, submit=False, console=_console()[0])

    assert (workdir / "mujoco_mojo_submit.sh").read_text() == wizard_script
    assert "#SBATCH --mem=1.5G\n" in wizard_script
    assert "#SBATCH --array=0-2%2\n" in wizard_script


def test_the_wizard_saves_the_job_id_and_offers_the_watch_command(
    tmp_path: Path, slurm: FakeSlurm, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    _script_the_wizard(monkeypatch, WIZARD_ANSWERS)
    watched: list[Path] = []
    monkeypatch.setattr(
        runner_module, "watch_job", lambda path, **kwargs: watched.append(path)
    )

    _runner(workdir).orchestrate_slurm_monte_carlo()

    assert (
        json.loads((workdir / JOB_STATUS_FNAME).read_text())["slurm_job_id"] == "4242"
    )
    assert watched == []


def test_the_wizard_asks_about_watching_just_before_submitting(
    tmp_path: Path, slurm: FakeSlurm, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    prompts = _script_the_wizard(monkeypatch, WIZARD_ANSWERS | {"up to date": True})
    watched: list[Path] = []
    monkeypatch.setattr(
        runner_module, "watch_job", lambda path, **kwargs: watched.append(path)
    )

    _runner(workdir).orchestrate_slurm_monte_carlo()

    submit_at = next(
        i for i, q in enumerate(prompts.asked) if "trials to SLURM now" in q
    )
    assert "up to date" in prompts.asked[submit_at + 1]
    assert [call[0] for call in slurm.calls].count("sbatch") == 1
    # the watcher started only after the job was submitted
    assert watched == [workdir]


def test_declining_to_submit_leaves_the_script_and_does_not_watch(
    tmp_path: Path, slurm: FakeSlurm, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    _script_the_wizard(monkeypatch, WIZARD_ANSWERS | {"trials to SLURM now": False})

    _runner(workdir).orchestrate_slurm_monte_carlo()

    assert (workdir / "mujoco_mojo_submit.sh").exists()
    assert slurm.sbatch_calls == []
    assert json.loads((workdir / JOB_STATUS_FNAME).read_text())["slurm_job_id"] is None


def test_the_wizard_reprompts_for_a_memory_size_that_is_not_one(
    tmp_path: Path, slurm: FakeSlurm, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    replies = iter(["lots", "2G"])
    answers = WIZARD_ANSWERS | {"[white]Memory per node[/]": None}
    prompts = _script_the_wizard(monkeypatch, answers)

    def memory_first(question: str, **kwargs: Any) -> Any:
        if "[white]Memory per node[/]" in question:
            prompts.asked.append(question)
            return next(replies)
        return prompts(question, **kwargs)

    monkeypatch.setattr(Prompt, "ask", staticmethod(memory_first))

    _runner(workdir).orchestrate_slurm_monte_carlo()

    assert "#SBATCH --mem=2G\n" in (workdir / "mujoco_mojo_submit.sh").read_text()


# --- mistakes are caught before anything is written ---


def _strict_generate(mojo_model: Any, overrides: Any, mode: str = "fast") -> Any:
    return mojo_model


def test_a_misspelled_kwarg_is_rejected_before_the_workdir_is_touched(
    tmp_path: Path, slurm: FakeSlurm
) -> None:
    workdir = tmp_path / "work"
    runner = MojoRunner(
        generator=_strict_generate,
        generator_path="sim.generate",
        workdir=workdir,
        config=MonteCarloConfig(n_trial=3, n_proc=1, resume=True),
        kwargs={"modee": "slow"},
    )

    with pytest.raises(ValueError, match="modee"):
        runner.submit_slurm(SlurmConfig(), NamedValueDict(), None, clean_workdir=False)

    assert not workdir.exists()
    assert slurm.sbatch_calls == []


def _custom_runtime(*args: Any, **kwargs: Any) -> Any:
    return None


def _assert_refused_before_anything_is_written(
    runner: MojoRunner, slurm: FakeSlurm, missing: str
) -> None:
    with pytest.raises(ValueError, match=missing):
        runner.submit_slurm(SlurmConfig(), NamedValueDict(), None)

    assert not runner.workdir.exists()
    assert slurm.sbatch_calls == []


def test_the_workers_need_an_import_path_for_the_generator(
    tmp_path: Path, slurm: FakeSlurm
) -> None:
    runner = MojoRunner(
        generator=_generate,
        workdir=tmp_path / "work",
        config=MonteCarloConfig(n_trial=3, n_proc=1, resume=True),
    )

    _assert_refused_before_anything_is_written(runner, slurm, "generator_path")


def test_the_workers_need_an_import_path_for_a_custom_runtime(
    tmp_path: Path, slurm: FakeSlurm
) -> None:
    runner = MojoRunner(
        generator=_generate,
        generator_path="sim.generate",
        runtime=_custom_runtime,
        workdir=tmp_path / "work",
        config=MonteCarloConfig(n_trial=3, n_proc=1, resume=True),
    )

    _assert_refused_before_anything_is_written(runner, slurm, "runtime_path")
