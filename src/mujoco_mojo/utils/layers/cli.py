"""Defines the CLI for mujoco-mojo."""

import ast
import importlib
import logging
import sys
from collections.abc import Callable
from enum import StrEnum
from importlib.metadata import version
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any, Literal, overload

import typer
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# get logger is not called at the top of this module since it MUST be called after setup_logger is run
# but since setup_logger doesnt know its verbosity until runtime get_logger needs to be called AS NEEDED
from mujoco_mojo.meta import MUJOCO_MOJO_DIR
from mujoco_mojo.utils.log import get_logger, setup_logger
from mujoco_mojo.utils.statusing import ExecutionMode
from mujoco_mojo.utils.utils import get_local_ip

from ..defaults import (
    DEFAULT_MC_N_TRIAL,
    DEFAULT_MODEL_CONFIG_NAME,
    DEFAULT_N_PROC,
    DEFAULT_OP_DIRECTION,
    DEFAULT_OP_EVALS_PER_TRIAL,
    DEFAULT_OP_N_TRIAL,
    DEFAULT_OP_PRUNE_FAILED_TRIALS,
    DEFAULT_OP_REFINE_SEARCH_FACTOR,
    DEFAULT_OP_SAMPLER,
    DEFAULT_OP_STUDY_NAME,
    DEFAULT_OP_TIMEOUT,
    DEFAULT_RESUME,
    DEFAULT_RUNTIME,
    DEFAULT_SEED,
    DEFAULT_WORKDIR,
    DEFAULT_XML_NAME,
    SamplerOptions,
)

console = Console()

VERSION = version("mujoco-mojo")


# "MUJOCO" and "MOJO" in the ANSI Shadow figlet font
_LOGO_LINES = [
    "███╗   ███╗██╗   ██╗     ██╗ ██████╗  ██████╗ ██████╗       ███╗   ███╗ ██████╗      ██╗ ██████╗ ",
    "████╗ ████║██║   ██║     ██║██╔═══██╗██╔════╝██╔═══██╗      ████╗ ████║██╔═══██╗     ██║██╔═══██╗",
    "██╔████╔██║██║   ██║     ██║██║   ██║██║     ██║   ██║      ██╔████╔██║██║   ██║     ██║██║   ██║",
    "██║╚██╔╝██║██║   ██║██   ██║██║   ██║██║     ██║   ██║      ██║╚██╔╝██║██║   ██║██   ██║██║   ██║",
    "██║ ╚═╝ ██║╚██████╔╝╚█████╔╝╚██████╔╝╚██████╗╚██████╔╝      ██║ ╚═╝ ██║╚██████╔╝╚█████╔╝╚██████╔╝",
    "╚═╝     ╚═╝ ╚═════╝  ╚════╝  ╚═════╝  ╚═════╝ ╚═════╝       ╚═╝     ╚═╝ ╚═════╝  ╚════╝  ╚═════╝ ",
]

_SHADES = [
    "#67e8f9",
    "#22d3ee",
    "#06b6d4",
    "#0891b2",
    "#0e7490",
    "#155e75",
]


def print_logo():
    body = Text(justify="center")
    for i, (line, shade) in enumerate(zip(_LOGO_LINES, _SHADES)):
        body.append(line, style=f"bold {shade}")
        if i != len(_LOGO_LINES) - 1:
            body.append("\n")

    console.print(
        Panel(
            Align.center(body),
            expand=False,
            border_style="cyan",
            subtitle=f"[dim]v{VERSION}[/dim]",
        )
    )


def _setup_cli_logging(verbose: int, quiet: int) -> logging.Logger:
    level = logging.INFO - (verbose * 10) + (quiet * 10)
    return setup_logger(level=level)


@overload
def _load_func(
    path: str, _return_module: Literal[False] = False
) -> Callable[..., Any]: ...
@overload
def _load_func(
    path: str, _return_module: Literal[True]
) -> tuple[Callable[..., Any], ModuleType]: ...
def _load_func(
    path: str, _return_module: bool = False
) -> Callable[..., Any] | tuple[Callable[..., Any], ModuleType]:
    """
    Helper to dynamically import user logic, supporting classes and methods.

    If `_return_module` is set, returns a `(obj, module)` tuple, where `module` is the importable module the dotted path resolved against (e.g. a package `__init__` re-exporting a class), as opposed to the module the attribute is actually defined in. Reloading that module is what's needed to pick up re-exported names after an edit.
    """
    if "." not in sys.path:
        sys.path.insert(0, ".")

    parts = path.split(".")

    # try to find the longest importable module path
    mod = None
    attr_parts = None
    import_error: Exception | None = None
    for i in range(len(parts) - 1, 0, -1):
        mod_path = ".".join(parts[:i])
        try:
            mod = importlib.import_module(mod_path)
            attr_parts = parts[i:]
            break
        except ModuleNotFoundError as e:
            # only keep trying shorter prefixes if mod_path itself (or one of its
            # parent packages) is what's missing - otherwise mod_path exists but
            # failed to import for some other reason, which is a real error
            if e.name == mod_path or mod_path.startswith(f"{e.name}."):
                continue
            import_error = e
            break
        except Exception as e:
            import_error = e
            break

    if import_error is not None:
        logger = get_logger(__name__)
        console.print(
            f"[bold red]Error:[/bold red] Failed to import module for [bold green]`{path}`[/bold green]: {import_error}"
        )
        logger.error(
            f"Failed to import module for `{path}`",
            exc_info=import_error,
            extra={"file_only": True},
        )
        raise typer.Exit(code=1)

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
    except AttributeError as e:
        logger = get_logger(__name__)
        console.print(
            f"[bold red]Error:[/bold red] [bold green]`{path}`[/bold green] not found: {e}"
        )
        logger.exception(f"`{path}`not found: {e}", extra={"file_only": True})
        raise typer.Exit(code=1)

    if not callable(obj):
        logger = get_logger(__name__)
        console.print(
            f"[bold red]Error:[/bold red] [bold green]`{path}`[/bold green] resolved to a "
            f"[bold]{type(obj).__name__}[/bold], which is not callable."
        )
        logger.error(
            f"`{path}` resolved to a non-callable {type(obj).__name__}",
            extra={"file_only": True},
        )
        raise typer.Exit(code=1)

    if _return_module:
        return obj, mod
    return obj


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
            help="Runtime path to use to run dynamics (e.g. 'sim.run')",
        ),
    ]
    ObjectiveType = Annotated[
        str,
        typer.Option(
            "--objective",
            "-ob",
            help="Objective function path to score the model (e.g. 'sim.score')",
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
        str | None,
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
        typer.Option(
            "--resume/--no-resume",
            help="Resume from previous state on disk",
        ),
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
    TrialNumType = Annotated[
        int,
        typer.Option(
            "--trial-num",
            "-tn",
            help="Specific trial number to run ([italic]-tn 5[/italic])",
        ),
    ]
    TrialNumsType = Annotated[
        list[int],
        typer.Option(
            "--trial-num",
            "-tn",
            help="Specific trial numbers to run ([italic]-tn 5 -tn 42[/italic])",
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
    HostType = Annotated[
        str,
        typer.Option(
            "--host",
            "-h",
            help="What host IP should be used to serve the process.",
        ),
    ]
    PortType = Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            help="Port number to use to serve the process.",
        ),
    ]
    DojoPassword = Annotated[
        str | None,
        typer.Option(
            "--password",
            "-pw",
            help="Enable Basic Auth protection",
        ),
    ]

    # Reloaded
    ConfigPathFileType = Annotated[
        Path | None,
        typer.Option(
            "--config",
            "-c",
            help="File which contains a model config definition. Mutually exclusive with the generator option.",
        ),
    ]
    ReloadedGeneratorType = Annotated[
        str | None,
        typer.Option(
            "--generator",
            "-g",
            help="Path to generator (e.g. 'sim.gen')",
        ),
    ]

    class UserInterface(StrEnum):
        OPENGL = "opengl"
        MJVISER = "mjviser"
        VISER = "viser"

    WatchType = Annotated[
        bool,
        typer.Option(
            "--watch/--no-watch",
            help="Automatically reload when [dim]*.py[/dim] source files change.",
        ),
    ]

    RecordType = Annotated[
        bool,
        typer.Option(
            "--record/--no-record",
            help="Record telemetry to a per-trial 'telemetry.parquet' so the run can be inspected with [dim]mujoco-mojo dojo[/dim]. Off by default since interactive sessions can run indefinitely.",
        ),
    ]

    UIType = Annotated[
        UserInterface,
        typer.Option(
            "--user-interface",
            "-ui",
            help=(
                "Which viewer type to use. OpenGL requires X11 forwarding but is ideal for local development. The Viser viewers require you to install those dependencies (they are available in the "
                r"[bold]mujoco-mojo\[reloaded][/bold] group)"
            ),
            case_sensitive=False,
        ),
    ]

    # optimize
    StudyNameType = Annotated[
        str,
        typer.Option(
            "--study-name",
            "-sn",
            help="Unique identifier for the Optuna study. Useful for resuming or tracking in a database.",
        ),
    ]
    DirectionType = Annotated[
        Literal["minimize", "maximize"],
        typer.Option(
            "--direction",
            "-d",
            help="The optimization goal. Either 'minimize' or 'maximize'.",
        ),
    ]
    SamplerType = Annotated[
        SamplerOptions,
        typer.Option(
            "--sampler",
            "-sm",
            help="The search algorithm to use (e.g., 'tpe' for Bayesian, 'cmaes', or 'random').",
        ),
    ]
    StorageType = Annotated[
        bool,
        typer.Option(
            "--storage",
            "-st",
            help="Whether or not to use database storage. Required for multi-process optimization.",
        ),
    ]
    TimeoutType = Annotated[
        float | None,
        typer.Option(
            "--timeout",
            "-to",
            help="Stop searching for new design parameters after N seconds have elapsed.",
        ),
    ]
    EvalsPerTrialType = Annotated[
        int,
        typer.Option(
            help="Number of evaluations (different seeds) per trial to average."
        ),
    ]
    RefineSearchFactorType = Annotated[
        float | None,
        typer.Option(
            help="Shrink search bounds by this factor on resume (0.1 = aggressive)."
        ),
    ]
    PruneFailedTrialsType = Annotated[
        bool,
        typer.Option(help="Immediately stop trials that hit physics instabilities."),
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
        console.print(f"[bold cyan]mujoco-mojo[/bold cyan] [bold white]{VERSION}")
        raise typer.Exit()


# create a run group for the run commands
run_app = typer.Typer(
    help="Execution commands for various Mojo generators and solvers (Monte Carlo, optimization, etc.)."
)
cli_app.add_typer(run_app, name="run")

# settings subcommand group
settings_app = typer.Typer(
    help=f"Manage global mujoco-mojo settings at [bold cyan]~/{MUJOCO_MOJO_DIR.relative_to(Path.home())}/settings.toml[/bold cyan].",
    no_args_is_help=True,
)
cli_app.add_typer(settings_app, name="settings")


@cli_app.callback(
    epilog="Check out the [link=https://hydrowelder.github.io/mujoco-mojo/]full documentation[/link] for more info."
)
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
    objective: ObjectiveType | None,
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
    objective_func = _load_func(objective) if objective else None

    return MojoRunner(
        generator=gen_func,
        generator_path=generator,  # needed for SLURM
        runtime=run_func,
        runtime_path=runtime,  # needed for SLURM
        objective=objective_func,
        objective_path=objective,
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
    n_proc: NProcType = DEFAULT_N_PROC,
    resume: ResumeType = DEFAULT_RESUME,
    seed: SeedType = DEFAULT_SEED,
    clean_workdir: CleanWorkdirType = False,
    model_config_name: ModelConfigNameType = DEFAULT_MODEL_CONFIG_NAME,
    xml_name: XMLNameType = DEFAULT_XML_NAME,
    execution_mode: ExecutionModeType = ExecutionMode.LOCAL,
    overrides: OverridesType = None,
    trial_nums: TrialNumsType = [],
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

    from mujoco_mojo.stochas import NamedValueDict
    from mujoco_mojo.utils.runner import MojoRunner, MonteCarloConfig

    logger = _setup_cli_logging(verbose=verbose, quiet=quiet)

    print_logo()

    workdir = workdir.resolve()

    logger.info("Initializing Monte Carlo with CLI!")

    dojo_cmd = f'mujoco-mojo dojo "{workdir}"'
    console.print(
        Panel(
            "[bold green]Campaign Initialized![/]\n\n"
            "[white]To monitor progress and view results, run:[/]\n"
            f"    [bold yellow]{dojo_cmd}[/]",
            title="[cyan]Monte Carlo Initialized[/]",
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

    if n_trial != 0 and trial_nums:
        logger.warning(
            "n-trials was not set to 0 with trial IDs provided. Setting n-trials to 0 and continuing."
        )
        n_trial = 0

    runner: MojoRunner = _prepare_runner(
        generator=generator,
        runtime=runtime,
        workdir=workdir,
        objective=None,
        model_config_name=model_config_name,
        seed=seed,
        xml_name=xml_name,
        gen_args=gen_args,
        gen_kwargs=gen_kwargs,
        run_args=run_args,
        run_kwargs=run_kwargs,
    )

    # 2. build config
    runner.config = MonteCarloConfig(n_trial=n_trial, n_proc=n_proc, resume=resume)

    # 3. run
    console.print(
        f"[bold magenta]Starting {n_trial} trials[/bold magenta] (using {n_proc} workers)..."
    )
    logger.info(
        f"Starting {n_trial} trials (using {n_proc} workers)...",
        extra={"file_only": True},
    )
    had_fails = runner.run(
        global_overrides=global_overrides
        if global_overrides
        else NamedValueDict[NDArray](),
        clean_workdir=clean_workdir,
        execution_mode=execution_mode,
        trial_nums=trial_nums,
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


@run_app.command(name="single")
def run_single(
    ctx: typer.Context,
    generator: GeneratorType,
    runtime: RuntimeType = DEFAULT_RUNTIME,
    workdir: WorkdirType = DEFAULT_WORKDIR,
    n_trial: NTrialType = 1,
    n_proc: NProcType = DEFAULT_N_PROC,
    resume: ResumeType = DEFAULT_RESUME,
    seed: SeedType = DEFAULT_SEED,
    clean_workdir: CleanWorkdirType = False,
    model_config_name: ModelConfigNameType = DEFAULT_MODEL_CONFIG_NAME,
    xml_name: XMLNameType = DEFAULT_XML_NAME,
    execution_mode: ExecutionModeType = ExecutionMode.LOCAL,
    overrides: OverridesType = None,
    trial_nums: TrialNumsType = [],
    gen_args: GenArgsType = [],
    gen_kwargs: GenKwargsType = [],
    run_args: RunArgsType = [],
    run_kwargs: RunKwargsType = [],
    verbose: VerboseType = 0,
    quiet: QuietType = 0,
) -> None:
    """
    [bold yellow]Execute a single trial.[/bold yellow]

    This command handles the directory setup, distribution salting, and execution of a single physics trial.
    """
    from numpydantic import NDArray

    from mujoco_mojo.stochas import NamedValueDict
    from mujoco_mojo.utils.runner import MojoRunner, MonteCarloConfig

    logger = _setup_cli_logging(verbose=verbose, quiet=quiet)

    print_logo()

    workdir = workdir.resolve()

    logger.info("Initializing single trial with CLI!")

    dojo_cmd = f'mujoco-mojo dojo "{workdir}"'
    console.print(
        Panel(
            "[bold green]Trial Ready![/]\n\n"
            "[white]To monitor progress and view results, run:[/]\n"
            f"    [bold yellow]{dojo_cmd}[/]",
            title="[cyan]Single Run Initialized[/]",
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

    if n_trial != 0 and trial_nums:
        logger.warning(
            "n-trials was not set to 0 with trial IDs provided. Setting n-trials to 0 and continuing."
        )
        n_trial = 0

    runner: MojoRunner = _prepare_runner(
        generator=generator,
        runtime=runtime,
        workdir=workdir,
        objective=None,
        model_config_name=model_config_name,
        seed=seed,
        xml_name=xml_name,
        gen_args=gen_args,
        gen_kwargs=gen_kwargs,
        run_args=run_args,
        run_kwargs=run_kwargs,
    )

    runner.config = MonteCarloConfig(n_trial=n_trial, n_proc=n_proc, resume=resume)

    trial_id = trial_nums[0] if trial_nums else 0
    console.print(f"[bold magenta]Running trial {trial_id}[/bold magenta]...")
    logger.info(f"Running trial {trial_id}...", extra={"file_only": True})

    had_fails = runner.run(
        global_overrides=global_overrides
        if global_overrides
        else NamedValueDict[NDArray](),
        clean_workdir=clean_workdir,
        execution_mode=execution_mode,
        trial_nums=trial_nums,
    )

    match execution_mode:
        case ExecutionMode.LOCAL:
            if had_fails:
                preamble = "[bold red]Trial finished with failures![/bold red]"
                logger.error(
                    f"Trial finished with failures! See results in {runner.workdir.resolve()}",
                    extra={"file_only": True},
                )
            else:
                preamble = "[bold green]Trial finished![/bold green]"
                logger.info(
                    f"Trial finished! See results in {runner.workdir.resolve()}",
                    extra={"file_only": True},
                )
            console.print(
                f"\n{preamble} Results located at [italic underline]{runner.workdir.resolve()}[/italic underline]"
            )
        case ExecutionMode.SLURM:
            if had_fails:
                finished_msg = "[bold red]Failed to orchestrate SLURM trial![/bold red]"
                logger.error(
                    "Failed to orchestrate SLURM trial!",
                    extra={"file_only": True},
                )
            else:
                finished_msg = (
                    "[bold green]SLURM trial orchestration finished![/bold green]"
                )
                logger.info(
                    "SLURM trial orchestration finished!",
                    extra={"file_only": True},
                )
            console.print(f"\n{finished_msg}")

    raise typer.Exit()


@cli_app.command(name="init")
def init_project(
    optimizer: Annotated[
        bool,
        typer.Option(
            "--optimizer/--no-optimizer",
            "-op/-nop",
            help="Include an [bold cyan]objective[/bold cyan] function stub for use with [bold]mujoco-mojo run optimization[/bold].",
        ),
    ] = False,
) -> None:
    """
    [bold yellow]Initialize a new empty mujoco-mojo project.[/bold yellow]

    Writes a [bold cyan]simulation.py[/bold cyan] scaffold to the current directory containing stub implementations of [bold]generate[/bold], [bold]runtime[/bold], and [bold]UserData[/bold]. Pass [bold cyan]--optimizer[/bold cyan] to also include an [bold]objective[/bold] stub.
    """
    import os
    from importlib.resources import files

    tmpl = files("mujoco_mojo.templates")

    py_dest = Path("simulation.py")
    run_dest = Path("run.sh")
    reloaded_dest = Path("reloaded.sh")

    conflicts = [p for p in (py_dest, run_dest, reloaded_dest) if p.exists()]
    if conflicts:
        names = ", ".join(f"[bold cyan]{p}[/bold cyan]" for p in conflicts)
        console.print(
            f"[bold red]Error:[/bold red] {names} already exist. "
            "Remove them first or rename them before running init."
        )
        raise typer.Exit(code=1)

    py_template = "optimization.py" if optimizer else "monte_carlo.py"
    sh_template = "run_opt.sh" if optimizer else "run_mc.sh"

    py_dest.write_text(
        tmpl.joinpath(py_template).read_text(encoding="utf-8"), encoding="utf-8"
    )
    run_dest.write_text(
        tmpl.joinpath(sh_template).read_text(encoding="utf-8"), encoding="utf-8"
    )
    reloaded_dest.write_text(
        tmpl.joinpath("reloaded.sh").read_text(encoding="utf-8"), encoding="utf-8"
    )

    os.chmod(run_dest, 0o755)
    os.chmod(reloaded_dest, 0o755)

    w = max(len(str(p)) for p in (py_dest, run_dest, reloaded_dest))
    console.print(
        Panel(
            f"[bold green]Project initialized![/bold green]\n\n"
            f"  [bold cyan]{str(py_dest).ljust(w)}[/bold cyan]  - simulation stubs\n"
            f"  [bold cyan]{str(run_dest).ljust(w)}[/bold cyan]  - run the campaign\n"
            f"  [bold cyan]{str(reloaded_dest).ljust(w)}[/bold cyan]  - interactive viewer\n\n"
            f"[white]Get started:[/white]\n"
            f"    [bold yellow]bash run.sh[/bold yellow]",
            title="[cyan]Mojo Init[/cyan]",
            expand=False,
            border_style="cyan",
        )
    )
    from mujoco_mojo.settings import SETTINGS_FILE

    if not SETTINGS_FILE.exists():
        console.print("\n[bold yellow]Global Settings[/bold yellow]")
        console.print(
            "No user settings file found. Initialize it with:\n"
            "    [bold cyan]mujoco-mojo settings init[/bold cyan]"
        )

    if not Path("typings", "mujoco").exists():
        console.print("\n[bold yellow]Type Hints Setup[/bold yellow]")
        console.print(
            "[bold white]MuJoCo does not ship Python type stubs.[/bold white] "
            "Generate them once for Pylance/Pyright autocomplete:\n\n"
            "[bold yellow]"
            "pip install pybind11-stubgen\n"
            "pybind11-stubgen mujoco -o typings/ --numpy-array-wrap-with-annotated"
            "[/bold yellow]\n\n"
            "Run from the project root. Then add to [bold cyan]pyproject.toml[/bold cyan]:\n\n"
            "[dim]"
            "\\[tool.pyright]\n"
            'stubPath = "typings"\n'
            'venvPath = "."\n'
            'venv    = ".venv"'
            "[/dim]\n\n"
            "[dim]Enum errors? Run: "
            "python typings/patch_mujoco_enums.py typings/mujoco/_enums.pyi[/dim]"
        )


@settings_app.command(name="init")
def settings_init(
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite an existing settings file (will not overwrite existing settings).",
        ),
    ] = False,
) -> None:
    """
    [bold yellow]Initialize the global settings file with defaults.[/bold yellow]

    Writes [bold cyan]~/.mujoco-mojo/settings.toml[/bold cyan] and generates a JSON schema for TOML editor intellisense. Safe to re-run to regenerate the schema.
    """
    import json

    from mujoco_mojo.settings import SETTINGS_DIR, SETTINGS_FILE, MujocoMojoSettings

    schema_file = SETTINGS_DIR / "settings.schema.json"
    taplo_file = SETTINGS_DIR / ".taplo.toml"
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)

    if SETTINGS_FILE.exists() and not force:
        setting_msg = f"[yellow]Settings already exist:[/yellow] {SETTINGS_FILE} [dim](Pass [bold]--force[/bold] to overwrite.)[/dim]"
    else:
        MujocoMojoSettings().save()
        setting_msg = f"[green]Settings written:[/green] {SETTINGS_FILE}"

    schema = MujocoMojoSettings.model_json_schema()
    schema_file.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    # taplo requires a file:// URI for the schema url - a relative path is not supported
    schema_uri = schema_file.as_uri()
    taplo_file.write_text(
        f'[[rule]]\ninclude = ["settings.toml"]\n\n[rule.schema]\nurl = "{schema_uri}"\n',
        encoding="utf-8",
    )

    console.print(
        Panel(
            f"{setting_msg}",
            # f"[green]Schema:[/green]      {schema_file}\n"
            # f"[green]Taplo config:[/green] {taplo_file}\n\n"
            # "[white]TOML intellisense is now active for any taplo-powered editor (VS Code Even Better TOML, Neovim, etc.) with no additional configuration.",
            title="[cyan]Settings Initialized[/cyan]",
            expand=False,
            border_style="cyan",
        )
    )


@settings_app.command(name="show")
def settings_show() -> None:
    """
    [bold yellow]Display the current effective settings.[/bold yellow]

    Resolves values from all sources in priority order: environment variables, TOML file, then defaults. The API key is always masked.
    """
    import tomli_w
    from rich.syntax import Syntax

    from mujoco_mojo.settings import SETTINGS_FILE, MujocoMojoSettings

    settings = MujocoMojoSettings()
    d = settings.model_dump()
    d["sensai"]["api_key"] = "***"

    toml_str = tomli_w.dumps(d).rstrip("\n")

    if SETTINGS_FILE.exists():
        try:
            source = "~/" + str(SETTINGS_FILE.relative_to(Path.home()))
        except ValueError:
            source = str(SETTINGS_FILE)
    else:
        source = "defaults only"

    console.print(
        Panel(
            Syntax(toml_str, "toml", theme="ansi_dark"),
            title="[cyan]MuJoCo Mojo Settings[/cyan]",
            subtitle=f"[dim]{source}[/dim]",
            expand=False,
            border_style="cyan",
        )
    )


@settings_app.command(name="set")
def settings_set_cmd(
    key: Annotated[
        str,
        typer.Argument(
            help="Dotted key path (e.g. [bold cyan]sensai.model_name[/bold cyan])",
            show_default=False,
        ),
    ],
    value: Annotated[
        str,
        typer.Argument(
            help="Value to assign. Integers, floats, and [bold]True[/bold]/[bold]False[/bold] are auto-parsed.",
            show_default=False,
        ),
    ],
) -> None:
    """
    [bold yellow]Update a setting in the global settings file.[/bold yellow]

    Example: [bold cyan]mujoco-mojo settings set sensai.model_name llama3.1:8b[/bold cyan]
    """
    from pydantic import ValidationError

    from mujoco_mojo.settings import SETTINGS_FILE, MujocoMojoSettings

    if not SETTINGS_FILE.exists():
        console.print(
            "[bold red]Error:[/bold red] No settings file found. "
            "Run [bold cyan]mujoco-mojo settings init[/bold cyan] first."
        )
        raise typer.Exit(code=1)

    settings = MujocoMojoSettings()
    data = settings.model_dump()

    parts = key.split(".")
    target: dict[str, Any] = data
    for part in parts[:-1]:
        if part not in target or not isinstance(target[part], dict):
            console.print(
                f"[bold red]Error:[/bold red] Unknown settings path: [bold cyan]{key}[/bold cyan]"
            )
            raise typer.Exit(code=1)
        target = target[part]

    leaf = parts[-1]
    if leaf not in target:
        console.print(
            f"[bold red]Error:[/bold red] Unknown settings key: [bold cyan]{key}[/bold cyan]"
        )
        raise typer.Exit(code=1)

    parsed = _smart_parse(value)
    target[leaf] = parsed

    try:
        updated = MujocoMojoSettings.model_validate(data)
    except ValidationError as e:
        console.print(f"[bold red]Validation error:[/bold red] {e}")
        raise typer.Exit(code=1)

    updated.save()
    console.print(f"[green]Updated[/green] [bold cyan]{key}[/bold cyan] = {parsed!r}")


@cli_app.command(name="reloaded")
def run_reloaded(
    generator: ReloadedGeneratorType = None,
    runtime: RuntimeType = DEFAULT_RUNTIME,
    workdir: WorkdirType = DEFAULT_WORKDIR,
    ui: UIType = UserInterface.OPENGL,
    overrides_path: OverridesType = None,
    trial_num: TrialNumType = 0,
    seed: SeedType = DEFAULT_SEED,
    config_path: ConfigPathFileType = None,
    model_config_name: ModelConfigNameType = DEFAULT_MODEL_CONFIG_NAME,
    xml_name: XMLNameType = DEFAULT_XML_NAME,
    watch: WatchType = True,
    record: RecordType = True,
    gen_args: GenArgsType = [],
    gen_kwargs: GenKwargsType = [],
    run_args: RunArgsType = [],
    run_kwargs: RunKwargsType = [],
    host: HostType = "127.0.0.1",
    port: PortType = 8080,
    verbose: int = 0,
    quiet: int = 0,
) -> None:
    """
    [bold yellow]Run a development session with the native OpenGL viewer or a web browser based GUI.[/bold yellow]

    Manual trigger to regenerate and reload the MJCF model for rapid prototyping.
    """
    from .reloaded import MojoReloaded

    _logger = _setup_cli_logging(verbose=verbose, quiet=quiet)

    # initialize and resolve
    overrides_path = None if not overrides_path else overrides_path.resolve()
    processed_gen_args = [_smart_parse(a) for a in gen_args]
    processed_gen_kwargs = _process_kwargs(gen_kwargs)
    processed_run_args = [_smart_parse(a) for a in run_args]
    processed_run_kwargs = _process_kwargs(run_kwargs)

    MojoReloaded(
        generator=generator,
        runtime=runtime,
        workdir=workdir,
        ui=ui,
        overrides_path=overrides_path,
        config_path=config_path,
        trial_num=trial_num,
        seed=seed,
        model_config_name=model_config_name,
        xml_name=xml_name,
        watch=watch,
        record=record,
        gen_args=processed_gen_args,
        gen_kwargs=processed_gen_kwargs,
        run_args=processed_run_args,
        run_kwargs=processed_run_kwargs,
        host=host,
        port=port,
    ).run()


@cli_app.command(name="dojo")
def run_dojo(
    ctx: typer.Context,
    workdir: DojoWorkdirType,
    host: HostType = "127.0.0.1",
    port: PortType = 8000,
    n_proc: NProcType = 1,
    password: DojoPassword = None,
    verbose: VerboseType = 0,
    quiet: QuietType = 0,
) -> None:
    """
    [bold yellow]Launch the Mojo Dojo to monitor the progress of a running job.[/bold yellow]

    This command reads status files in the workdir to give live updates.
    """
    _logger = _setup_cli_logging(verbose=verbose, quiet=quiet)

    import warnings

    import uvicorn

    # fastmcp (a transitive dependency of the sensai agent) pulls in key_value.aio,
    # which calls beartype_this_package() on itself. beartype then trips over
    # numpydantic's NDArray metaclass, which breaks isinstance() checks.
    # this is purely a third-party incompatibility; suppress the noise.
    warnings.filterwarnings("ignore", module=r"key_value\.")

    import mujoco_mojo.utils.layers.dojo.shared as shared
    from mujoco_mojo.utils.layers.dojo.main import dojo_app
    from mujoco_mojo.utils.statusing import JOB_STATUS_FNAME, JobStatus, JobType

    status_file = (workdir / JOB_STATUS_FNAME).resolve()
    if not status_file.exists():
        console.print(
            f"[bold red]Error:[/bold red] No status file found at {status_file}"
        )
        raise typer.Exit(code=1)

    # read job status file for monitoring and inject
    job = JobStatus.model_validate_json(status_file.read_text())
    job.refresh_from_disk(n_proc=n_proc, persist=False)

    shared.CURRENT_JOB = job
    shared.AUTH_PASSWORD = password
    shared.set_globals(workdir=workdir, owner=job.started_by, job_type=job.job_type)

    if job.job_type == JobType.OPTIMIZE:
        from mujoco_mojo.utils.layers.dojo.routers.morph import mount_optuna_engine

        db_path = f"sqlite:///{workdir / 'study.db'}"
        mount_optuna_engine(dojo_app, db_path)

    # detect ip
    local_ip = get_local_ip()
    if password:
        connection_info = "[yellow]Auth enabled. Use [u]any[/u] username and your provided password.[/yellow]\n\n"
    else:
        connection_info = ""

    connection_info += f"Local: [bold cyan u]http://127.0.0.1:{port}[/bold cyan u]"

    if host == "0.0.0.0":
        connection_info += (
            f"\nMobile: [bold cyan u]http://{local_ip}:{port}[/bold cyan u]"
        )
    else:
        connection_info += "\n\n[dim]Tip: To view on other devices (and to make pages shareable), run with[/dim] [yellow]--host 0.0.0.0[/yellow]"

    console.print(
        Panel(
            f"""[bold green]MuJoCo Mojo Dojo is Live![/bold green]\n\n{connection_info}\n\n[yellow]Press CTRL+C to stop[/yellow]""",
            border_style="cyan",
            expand=False,
            title="Mojo Dojo",
            subtitle=f"Workers: {n_proc}",
        )
    )

    # uvicorn.run(dojo_app, host=host, port=port, log_level="info")
    uvicorn.run(dojo_app, host=host, port=port, log_level="critical")


@run_app.command(name="optimization")
def run_optimizer(
    ctx: typer.Context,
    generator: GeneratorType,
    objective: ObjectiveType,
    runtime: RuntimeType = DEFAULT_RUNTIME,
    workdir: WorkdirType = DEFAULT_WORKDIR,
    n_trial: NTrialType = DEFAULT_OP_N_TRIAL,
    n_proc: NProcType = DEFAULT_N_PROC,
    timeout: TimeoutType = DEFAULT_OP_TIMEOUT,
    study_name: StudyNameType = DEFAULT_OP_STUDY_NAME,
    direction: DirectionType = DEFAULT_OP_DIRECTION,
    sampler: SamplerType = DEFAULT_OP_SAMPLER,
    storage: StorageType = True,
    resume: ResumeType = DEFAULT_RESUME,
    seed: SeedType = DEFAULT_SEED,
    evals_per_trial: EvalsPerTrialType = DEFAULT_OP_EVALS_PER_TRIAL,
    refine_search_factor: RefineSearchFactorType = DEFAULT_OP_REFINE_SEARCH_FACTOR,
    prune_failed_trials: PruneFailedTrialsType = DEFAULT_OP_PRUNE_FAILED_TRIALS,
    clean_workdir: CleanWorkdirType = False,
    model_config_name: ModelConfigNameType = DEFAULT_MODEL_CONFIG_NAME,
    xml_name: XMLNameType = DEFAULT_XML_NAME,
    overrides: OverridesType = None,
    gen_args: GenArgsType = [],
    gen_kwargs: GenKwargsType = [],
    run_args: RunArgsType = [],
    run_kwargs: RunKwargsType = [],
    verbose: VerboseType = 0,
    quiet: QuietType = 0,
) -> None:
    """
    [bold yellow]Execute an automated Design Optimization study.[/bold yellow]

    This command uses Optuna to intelligently navigate the search space defined by [bold cyan]model.design_float[/bold cyan] and [bold cyan]model.design_categorical[/bold cyan] calls within your generator.
    """
    import optuna
    from numpydantic import NDArray

    from mujoco_mojo.stochas import NamedValueDict
    from mujoco_mojo.utils.runner import MojoRunner, OptimizerConfig

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    logger = _setup_cli_logging(verbose=verbose, quiet=quiet)
    print_logo()

    workdir = workdir.resolve()

    dojo_cmd = f'mujoco-mojo dojo "{workdir}"'
    console.print(
        Panel(
            f"[bold green]Optimization Engine Engaged![/]\n\n"
            f"[white]Study:[/]      [cyan]{study_name}[/]\n"
            f"[white]Direction:[/]  [magenta]{direction}[/]\n"
            f"[white]Sampler:[/]    [yellow]{sampler}[/]\n\n"
            f"[white]To monitor live progress, run:[/]\n"
            f"    [bold yellow]{dojo_cmd}[/]",
            title="[cyan]Optimizer Initialized[/]",
            expand=False,
            border_style="cyan",
        )
    )

    global_overrides = None
    if overrides:
        overrides = overrides.resolve()
        logger.info(f"Loading global NamedValue overrides from `{overrides}`")
        global_overrides = NamedValueDict[NDArray].model_validate_json(
            overrides.read_text()
        )

    runner: MojoRunner = _prepare_runner(
        generator=generator,
        runtime=runtime,
        workdir=workdir,
        objective=objective,
        model_config_name=model_config_name,
        seed=seed,
        xml_name=xml_name,
        gen_args=gen_args,
        gen_kwargs=gen_kwargs,
        run_args=run_args,
        run_kwargs=run_kwargs,
    )

    runner.config = OptimizerConfig(
        n_trial=n_trial,
        n_proc=n_proc,
        timeout=timeout,
        study_name=study_name,
        direction=direction,
        sampler=sampler,
        storage=f"sqlite:///{workdir / 'study.db'}" if storage else None,
        resume=resume,
        evals_per_trial=evals_per_trial,
        refine_search_factor=refine_search_factor,
        prune_failed_trials=prune_failed_trials,
    )

    had_fails = runner.run(
        global_overrides=global_overrides
        if global_overrides
        else NamedValueDict[NDArray](),
        clean_workdir=clean_workdir,
        execution_mode=ExecutionMode.LOCAL,
    )

    if had_fails:
        console.print(
            f"\n[bold red]Optimization finished with errors.[/] See logs in {workdir}"
        )
    else:
        console.print(
            f"\n[bold green]Optimization study complete![/] Best parameters saved to [italic]{workdir}/best_params.json[/italic]"
        )

    raise typer.Exit()


if __name__ == "__main__":
    cli_app()
