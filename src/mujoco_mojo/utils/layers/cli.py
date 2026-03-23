"""Defines the CLI for mujoco-mojo."""

import ast
import importlib
import logging
import socket
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.panel import Panel

# get logger is not called at the top of this module since it MUST be called after setup_logger is run
# but since setup_logger doesnt know its verbosity until runtime get_logger needs to be called AS NEEDED
from mujoco_mojo.utils.log import get_logger, setup_logger
from mujoco_mojo.utils.statusing import ExecutionMode

from ..defaults import (
    DEFAULT_MC_N_PROC,
    DEFAULT_MC_N_TRIAL,
    DEFAULT_MODEL_CONFIG_NAME,
    DEFAULT_RESUME,
    DEFAULT_RUNTIME,
    DEFAULT_SEED,
    DEFAULT_WORKDIR,
    DEFAULT_XML_NAME,
)

console = Console()


def get_local_ip():
    """Returns the actual local IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually need to connect to 8.8.8.8 to work
        s.connect(("8.8.8.8", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def _setup_cli_logging(verbose: int, quiet: int) -> logging.Logger:
    level = logging.INFO - (verbose * 10) + (quiet * 10)
    return setup_logger(level=level)


def _load_func(path: str) -> Any:
    """Helper to dynamically import user logic, supporting classes and methods."""
    if "." not in sys.path:
        sys.path.insert(0, ".")

    parts = path.split(".")

    # try to find the longest importable module path
    mod = None
    attr_parts = None
    for i in range(len(parts) - 1, 0, -1):
        mod_path = ".".join(parts[:i])
        try:
            mod = importlib.import_module(mod_path)
            attr_parts = parts[i:]
            break
        except ImportError:
            continue

    if mod is None or attr_parts is None:
        logger = get_logger(__name__)
        console.print(
            f"[bold red]Error:[/bold red] Could not find module for [bold green]`{path}`[/bold green]"
        )
        logger.error(f"Could not find module for `{path}`", extra={"file_only": True})
        raise typer.Exit(code=1)

    # drill down to the attributes (Class -> Method)
    try:
        obj = mod
        for part in attr_parts:
            obj = getattr(obj, part)
        return obj
    except AttributeError as e:
        logger = get_logger(__name__)
        console.print(
            f"[bold red]Error:[/bold red] [bold green]`{path}`[/bold green] not found: {e}"
        )
        logger.exception(f"`{path}`not found: {e}", extra={"file_only": True})
        raise typer.Exit(code=1)


def _smart_parse(value: str) -> Any:
    """Tries to convert CLI strings to Python types (int, float, bool)."""
    try:
        # ast.literal_eval handles 10 -> int, 10.5 -> float, True -> bool
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        # Fallback to raw string if it's not a basic literal
        return value


def _process_kwargs(kwargs: list[str]) -> dict[str, Any]:
    """Parses Keyword Args of the format: ["key=val", "name=gable"] into {"key": "val", "name": "gable"}"""
    processed_kwargs = {}
    for kv in kwargs:
        if "=" not in kv:
            logger = get_logger(__name__)
            console.print(
                f"[bold red]Error:[/bold red] Invalid Key-Value pair '{kv}'. Use `'key=value'`."
            )
            logger.error(
                f"Invalid Key-Value pair '{kv}'. Use `'key=value'`.",
                extra={"file_only": True},
            )
            raise typer.Exit(1)
        k, v = kv.split("=", 1)
        processed_kwargs[k] = _smart_parse(v)
    return processed_kwargs


# this `if True` is just so I can collapse this code block
if True:
    # main
    VerboseType = Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            help="Increase verbosity (can be repeated, e.g., -vv for DEBUG).",
            count=True,
        ),
    ]
    QuietType = Annotated[
        int,
        typer.Option(
            "--quiet",
            "-q",
            help="Decrease verbosity (can be repeated, e.g., -qq for ERROR).",
            count=True,
        ),
    ]

    # mojo runner
    GeneratorType = Annotated[
        str,
        typer.Option(
            "--generator",
            "-g",
            help="Path to generator (e.g. 'sim.gen')",
            show_default=False,
        ),
    ]
    RuntimeType = Annotated[
        str | None,
        typer.Option(
            "--runtime",
            "-r",
            help="Optional runtime path",
        ),
    ]
    PostProcessorType = Annotated[
        str | None,
        typer.Option(
            "--post-processor",
            "-p",
            help="Optional runtime path",
        ),
    ]
    WorkdirType = Annotated[
        Path,
        typer.Option(
            "--workdir",
            "-w",
            help="Workspace directory. The job will be executed out of this directory. It will be made if it does not already exist.",
        ),
    ]
    ModelConfigNameType = Annotated[
        str,
        typer.Option(
            "--model-config-name",
            "-mcn",
            help="Name for model dump file (e.g. 'model_config.json')",
        ),
    ]
    XMLNameType = Annotated[
        str,
        typer.Option(
            "--xml-name",
            "-xml",
            help="Name for XML file (e.g. 'model.xml')",
        ),
    ]
    ResumeType = Annotated[
        bool,
        typer.Option("--resume/--no-resume", help="Resume from previous state on disk"),
    ]
    CleanWorkdirType = Annotated[
        bool,
        typer.Option(
            "--clean-workdir",
            "-cw",
            help="Delete the workdir before running (mutually exclusive with --resume)",
        ),
    ]
    GenArgsType = Annotated[
        list[str],
        typer.Option(
            "--gen-arg",
            "-ga",
            help=(
                "Positional arg for the [bold cyan]generator[/bold cyan]. "
                "Repeat for multiple values (e.g., [italic]--gen-arg high_friction --gen-arg 1.5[/italic]). "
                "Values are [bold yellow]smart-parsed[/bold yellow] (e.g., '1.5' becomes a float)."
            ),
        ),
    ]
    GenKwargsType = Annotated[
        list[str],
        typer.Option(
            "--gen-kwarg",
            "-gk",
            help=(
                "Keyword arg (key=value) for the [bold cyan]generator[/bold cyan]. "
                "Example: [italic]--gen-kwarg mode='fast' --gen-kwarg complexity=10[/italic]. "
                "Strings with special characters should be [underline]single-quoted[/underline] inside the double quotes."
            ),
        ),
    ]
    RunArgsType = Annotated[
        list[str],
        typer.Option(
            "--run-arg",
            "-ra",
            help=(
                "Positional arg for the [bold magenta]runtime[/bold magenta]. "
                "Repeat for multiple values. Useful for passing flags directly to the physics engine."
            ),
        ),
    ]
    RunKwargsType = Annotated[
        list[str],
        typer.Option(
            "--run-kwarg",
            "-rk",
            help=(
                "Keyword arg (key=value) for the [bold magenta]runtime[/bold magenta]. "
                "Example: [italic]--run-kwarg solver='Newton' --run-kwarg iterations=5[/italic]."
            ),
        ),
    ]
    ExecutionModeType = Annotated[
        ExecutionMode,
        typer.Option(
            "--execution-mode",
            "-em",
            help="The strategy used to execute trials.",
            case_sensitive=False,
        ),
    ]
    TrialIdType = Annotated[
        list[int],
        typer.Option(
            "--trial-id",
            "-tid",
            help="Specific trial IDs to run ([italic]-tid 5 -tid 42[/italic])",
        ),
    ]
    SeedType = Annotated[
        int | None,
        typer.Option(
            "--seed",
            "-s",
            help="Seed to use for the job.",
        ),
    ]
    OverridesType = Annotated[
        Path | None,
        typer.Option(
            "--overrides",
            "-o",
            help="File which contains NamedValue overrides to use in all trials.",
        ),
    ]

    # monte carlo
    NTrialType = Annotated[
        int,
        typer.Option(
            "--n-trial",
            "-nt",
            help="Number of trials to be performed in the job.",
        ),
    ]
    NProcType = Annotated[
        int,
        typer.Option(
            "--n-proc",
            "-np",
            help="Parallel processes to use in executing tasks (such as running Monte Carlo or status file proccessing for the Dojo process)."
            " [bold red underline]Be a good citizen.[/bold red underline] It is easy to abuse this command. Only use what resouces you [bold white underline]absolutely need[/bold white underline].",
        ),
    ]

    # Dojo
    DojoWorkdirType = Annotated[
        Path,
        typer.Argument(
            help="Workspace directory to build the Dojo process for. This should be the same argument as what is used for other mujoco-mojo run commands.",
        ),
    ]
    DojoHostType = Annotated[
        str,
        typer.Option(
            "--host",
            "-h",
            help="What host IP should be used to serve the Dojo process.",
        ),
    ]
    DojoPortType = Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            help="Port number to use to serve the Dojo process.",
        ),
    ]

# initialize the CLI with rich formatting
cli_app = typer.Typer(
    name="mujoco-mojo",
    help="[bold cyan]MuJoCo Mojo:[/bold cyan] High-performance and extensible physics simulation manager",
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={
        "help_option_names": [
            # "-h",
            "--help",
        ]
    },
)


def version_callback(value: bool):
    if value:
        console.print(
            f"[bold cyan]mujoco-mojo[/bold cyan] [bold white]{version('mujoco-mojo')}"
        )
        raise typer.Exit()


# create a run group for the run commands
run_app = typer.Typer(
    help="Execution commands for various Mojo functions (Monte Carlo, Dojo, etc.)."
)
cli_app.add_typer(run_app, name="run")


@cli_app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = False,
):
    """
    [bold cyan]MuJoCo Mojo:[/bold cyan] High-performance and extensible physics simulation manager.
    """


def _prepare_runner(
    generator: GeneratorType,
    runtime: RuntimeType,
    workdir: WorkdirType,
    model_config_name: ModelConfigNameType,
    seed: SeedType,
    xml_name: XMLNameType,
    gen_args: GenArgsType,
    gen_kwargs: GenKwargsType,
    run_args: RunArgsType,
    run_kwargs: RunKwargsType,
):
    from mujoco_mojo.utils.runner import MojoRunner

    assert generator is not None, (
        "Generator cannot be None to make a MojoRunner. Please contact a MuJoCo Mojo developer."
    )

    # proccess args and kwargs
    processed_gen_args = [_smart_parse(a) for a in gen_args]
    processed_gen_kwargs = _process_kwargs(gen_kwargs)
    processed_run_args = [_smart_parse(a) for a in run_args]
    processed_run_kwargs = _process_kwargs(run_kwargs)

    # resolve code paths
    gen_func = _load_func(generator)
    run_func = _load_func(runtime) if runtime else None

    return MojoRunner(
        generator=gen_func,
        generator_path=generator,  # needed for SLURM
        runtime=run_func,
        runtime_path=runtime,  # needed for SLURM
        workdir=workdir,
        seed=seed,
        model_config_name=model_config_name,
        xml_name=xml_name,
        gen_args=processed_gen_args,
        gen_kwargs=processed_gen_kwargs,
        run_args=processed_run_args,
        run_kwargs=processed_run_kwargs,
    )


@run_app.command(name="monte-carlo")
def run_monte_carlo(
    ctx: typer.Context,
    generator: GeneratorType,
    runtime: RuntimeType = DEFAULT_RUNTIME,
    workdir: WorkdirType = DEFAULT_WORKDIR,
    n_trial: NTrialType = DEFAULT_MC_N_TRIAL,
    n_proc: NProcType = DEFAULT_MC_N_PROC,
    resume: ResumeType = DEFAULT_RESUME,
    seed: SeedType = DEFAULT_SEED,
    clean_workdir: CleanWorkdirType = False,
    model_config_name: ModelConfigNameType = DEFAULT_MODEL_CONFIG_NAME,
    xml_name: XMLNameType = DEFAULT_XML_NAME,
    execution_mode: ExecutionModeType = ExecutionMode.LOCAL,
    overrides: OverridesType = None,
    trial_ids: TrialIdType = [],
    gen_args: GenArgsType = [],
    gen_kwargs: GenKwargsType = [],
    run_args: RunArgsType = [],
    run_kwargs: RunKwargsType = [],
    verbose: VerboseType = 0,
    quiet: QuietType = 0,
) -> None:
    """
    [bold yellow]Execute a Monte Carlo campaign.[/bold yellow]

    This command handles the directory setup, distribution salting, and parallel execution of physics trials.
    """
    from numpydantic import NDArray

    from mujoco_mojo.process_manager import NamedValueDict
    from mujoco_mojo.utils.runner import MojoRunner, MonteCarloConfig

    logger = _setup_cli_logging(verbose=verbose, quiet=quiet)

    workdir = workdir.resolve()

    logger.info("Initializing Monte Carlo with CLI!")

    dojo_cmd = f"mujoco-mojo dojo {workdir}"
    console.print(
        Panel(
            "[bold green]Campaign Initialized![/]\n\n"
            "[white]To monitor progress and view results, run:[/]\n"
            f"    [bold yellow]{dojo_cmd}[/]",
            title="[cyan]Launch Control[/]",
            expand=False,
            border_style="cyan",
        )
    )

    global_overrides = None
    if overrides:
        overrides = overrides.resolve()
        logger.info(f"Retrieving global NamedValue overrides from `{overrides}`")
        global_overrides = NamedValueDict[NDArray].model_validate_json(
            overrides.read_text()
        )

        if len(global_overrides) == 0:
            logger.warning(
                "Global NamedValue overrides had no entries. Continuing anyway."
            )
        else:
            logger.info(
                f"Global NamedValue overrides had {len(global_overrides)} entries."
            )

    if n_trial != 0 and trial_ids:
        logger.warning(
            "n-trials was not set to 0 with trial IDs provided. Setting n-trials to 0 and continuing."
        )
        n_trial = 0

    runner: MojoRunner = _prepare_runner(
        generator=generator,
        runtime=runtime,
        workdir=workdir,
        model_config_name=model_config_name,
        seed=seed,
        xml_name=xml_name,
        gen_args=gen_args,
        gen_kwargs=gen_kwargs,
        run_args=run_args,
        run_kwargs=run_kwargs,
    )

    # 2. build config
    runner.config = MonteCarloConfig(n_trial=n_trial, n_proc=n_proc)

    # 3. run
    console.print(
        f"[bold magenta]Starting {n_trial} trials[/bold magenta] (using {n_proc} workers)..."
    )
    logger.info(
        f"Starting {n_trial} trials (using {n_proc} workers)...",
        extra={"file_only": True},
    )
    _results, had_fails = runner.run(
        resume=resume,
        global_overrides=global_overrides
        if global_overrides
        else NamedValueDict[NDArray](),
        clean_workdir=clean_workdir,
        execution_mode=execution_mode,
        trial_ids=trial_ids,
    )

    match execution_mode:
        case ExecutionMode.LOCAL:
            if had_fails:
                preamble = "[bold red]Monte Carlo finished with failures![/bold red]"
                logger.error(
                    f"Monte Carlo finished with failures! See results in {runner.workdir.resolve()}",
                    extra={"file_only": True},
                )
            else:
                preamble = "[bold green]Monte Carlo finished![/bold green]"
                logger.info(
                    f"Monte Carlo finished! See results in {runner.workdir.resolve()}",
                    extra={"file_only": True},
                )
            console.print(
                f"\n{preamble} Results located at [italic underline]{runner.workdir.resolve()}[/italic underline]"
            )
        case ExecutionMode.SLURM:
            if had_fails:
                finished_msg = (
                    "[bold red]Failed to orchestrate SLURM Monte Carlo![/bold red]"
                )
                logger.error(
                    "Failed to orchestrate SLURM Monte Carlo!",
                    extra={"file_only": True},
                )
            else:
                finished_msg = (
                    "[bold green]SLURM Monte Carlo orchestration finished![/bold green]"
                )
                logger.info(
                    "SLURM Monte Carlo orchestration finished!",
                    extra={"file_only": True},
                )
            console.print(f"\n{finished_msg}")

    raise typer.Exit()


@cli_app.command(name="dojo")
def run_dojo(
    ctx: typer.Context,
    workdir: DojoWorkdirType,
    host: DojoHostType = "127.0.0.1",
    port: DojoPortType = 8000,
    n_proc: NProcType = 1,
    verbose: VerboseType = 0,
    quiet: QuietType = 0,
) -> None:
    """
    [bold yellow]Launch the Mojo Dojo to monitor the progress of a running job.[/bold yellow]

    This command reads status files in the workdir to give live updates.
    """
    _logger = _setup_cli_logging(verbose=verbose, quiet=quiet)

    import uvicorn

    import mujoco_mojo.utils.layers.dojo.shared as shared
    from mujoco_mojo.utils.layers.dojo.main import dojo_app
    from mujoco_mojo.utils.statusing import JOB_STATUS_FNAME, JobStatus

    status_file = (workdir / JOB_STATUS_FNAME).resolve()
    if not status_file.exists():
        console.print(
            f"[bold red]Error:[/bold red] No status file found at {status_file}"
        )
        raise typer.Exit(code=1)

    # read job status file for monitoring and inject
    job = JobStatus.model_validate_json(status_file.read_text())
    job.refresh_from_disk(n_proc=n_proc)

    shared.CURRENT_JOB = job
    shared.set_globals(workdir=workdir, owner=job.started_by)

    # detect ip
    local_ip = get_local_ip()
    connection_info = f"Local: [bold cyan u]http://127.0.0.1:{port}[/bold cyan u]"

    if host == "0.0.0.0":
        connection_info += (
            f"\nMobile: [bold cyan u]http://{local_ip}:{port}[/bold cyan u]"
        )
    else:
        connection_info += "\n\n[dim]Tip: To view on other devices, run with[/dim] [yellow]--host 0.0.0.0[/yellow]"

    console.print(
        Panel(
            f"""[bold green]MuJoCo Mojo Dojo is Live![/bold green]\n\n{connection_info}\n\n[yellow]Press CTRL+C to stop[/yellow]""",
            border_style="cyan",
            title="Mojo Dojo",
            subtitle=f"Workers: {n_proc}",
        )
    )
    uvicorn.run(dojo_app, host=host, port=port, log_level="warning")


@run_app.command(name="optimize")
def run_optimizer(
    verbose: VerboseType = 0,
    quiet: QuietType = 0,
) -> None:
    """[dim]Placeholder for future optimization command...[/dim]"""
    _logger = _setup_cli_logging(verbose=verbose, quiet=quiet)
    console.print("[yellow]Optimization engine coming soon![/yellow]")


if __name__ == "__main__":
    cli_app()
