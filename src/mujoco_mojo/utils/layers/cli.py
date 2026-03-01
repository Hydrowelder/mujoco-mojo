import ast
import importlib
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import print as rprint
from rich.panel import Panel

from ..defaults import (
    DEFAULT_MC_N_PROC,
    DEFAULT_MC_N_TRIAL,
    DEFAULT_MODEL_CONFIG_NAME,
    DEFAULT_RESUME,
    DEFAULT_RUNTIME,
    DEFAULT_WORKDIR,
    DEFAULT_XML_NAME,
)


def validate_generator(ctx: typer.Context, value: str | None):
    # If the user is just asking for help (-h), don't validate!
    help_requested = any(arg in sys.argv for arg in ["-h", "--help"])
    if ctx.resilient_parsing or help_requested:
        return value

    # If we are actually running and it's missing, THEN error
    if value is None:
        rprint("[bold red]Error:[/bold red] Missing option '--generator'.")
        rprint("Try 'mujoco-mojo run --help' for global options.")
        raise typer.Exit(code=1)
    return value


# mojo runner
GeneratorType = Annotated[
    str | None,
    typer.Option(
        "--generator",
        callback=validate_generator,
        help="Path to generator (e.g. 'sim.gen') [bold red][*required][/bold red]",
        show_default=False,
    ),
]  # the generator is technically required for running actual jobs, but to run the help command for subcommands (like `monte-carlo`) a default it set or it will crash
RuntimeType = Annotated[
    str | None,
    typer.Option("--runtime", help="Optional runtime path"),
]
WorkdirType = Annotated[
    Path,
    typer.Option("--workdir", help="Workspace directory"),
]
ModelConfigNameType = Annotated[
    str,
    typer.Option(
        "--model-config-name",
        help="Name for model dump file (e.g. 'model_config.json')",
    ),
]
XMLNameType = Annotated[
    str,
    typer.Option("--xml-name", help="Name for XML file (e.g. 'model.xml')"),
]
ResumeType = Annotated[
    bool,
    typer.Option("--resume/--no-resume", help="Resume from disk"),
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
            "Strings with special characters should be [bold red]single-quoted[/bold red] inside the double quotes."
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

# monte carlo
NTrialType = Annotated[
    int,
    typer.Option("--n-trial", help="Number of trials"),
]
NProcType = Annotated[
    int,
    typer.Option("--n-proc", help="Parallel processes"),
]

# initialize the CLI with rich formatting
app = typer.Typer(
    name="mujoco-mojo",
    help="[bold cyan]MuJoCo Mojo:[/bold cyan] High-performance and extensible physics simulation manager",
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# create a run group for the run commands
run_app = typer.Typer()
app.add_typer(run_app, name="run")


def version_callback(value: bool):
    if value:
        rprint(
            f"[bold cyan]mujoco-mojo[/bold cyan] [bold white]{version('mujoco-mojo')}"
        )
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
):
    """
    [bold cyan]MuJoCo Mojo:[/bold cyan] High-performance and extensible physics simulation manager.
    """


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
        rprint(
            f"[bold red]Error:[/bold red] Could not find module for [bold green]`{path}`[/bold green]"
        )
        raise typer.Exit(code=1)

    # drill down to the attributes (Class -> Method)
    try:
        obj = mod
        for part in attr_parts:
            obj = getattr(obj, part)
        return obj
    except AttributeError as e:
        rprint(
            f"[bold red]Error:[/bold red] [bold green]`{path}`[/bold green] not found: {e}"
        )
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
            rprint(
                f"[bold red]Error:[/bold red] Invalid Key-Value pair '{kv}'. Use key=value."
            )
            raise typer.Exit(1)
        k, v = kv.split("=", 1)
        processed_kwargs[k] = _smart_parse(v)
    return processed_kwargs


@run_app.callback()
def run_globals(
    ctx: typer.Context,
    generator: GeneratorType = None,
    runtime: RuntimeType = DEFAULT_RUNTIME,
    workdir: WorkdirType = DEFAULT_WORKDIR,
    model_config_name: ModelConfigNameType = DEFAULT_MODEL_CONFIG_NAME,
    xml_name: XMLNameType = DEFAULT_XML_NAME,
    resume: ResumeType = DEFAULT_RESUME,
    gen_args: GenArgsType = [],
    gen_kwargs: GenKwargsType = [],
    run_args: RunArgsType = [],
    run_kwargs: RunKwargsType = [],
):
    """
    [bold yellow]Global settings for all simulation runs.[/bold yellow]

    This command is what is used to actually run mujoco-mojo. It is used in conjuntion with the other subcommands (such as [bold cyan]`monte-carlo`[/bold cyan] or [bold cyan]`optimize`[/bold cyan]).
    """
    # Ensure ctx.obj exists even if we exit early
    ctx.ensure_object(dict)

    help_requested = any(arg in sys.argv for arg in ["-h", "--help"])
    if ctx.resilient_parsing or help_requested or generator is None:
        return

    from mujoco_mojo.utils.runner import MojoRunner

    processed_gen_args = [_smart_parse(a) for a in gen_args]
    processed_gen_kwargs = _process_kwargs(gen_kwargs)

    processed_run_args = [_smart_parse(a) for a in run_args]
    processed_run_kwargs = _process_kwargs(run_kwargs)

    # resolve code paths
    gen_func = _load_func(generator)
    run_func = _load_func(runtime) if runtime else None

    # initialize runner
    runner = MojoRunner(
        generator=gen_func,
        runtime=run_func,
        workdir=workdir,
        model_config_name=model_config_name,
        xml_name=xml_name,
        gen_args=processed_gen_args,
        gen_kwargs=processed_gen_kwargs,
        run_args=processed_run_args,
        run_kwargs=processed_run_kwargs,
    )

    # dry-run check
    gen_name, gen_path = runner.inspect_protocol(gen_func)
    run_name, run_path = runner.inspect_protocol(run_func)
    inspection_results = (
        f"[bold blue]generator[/bold blue] {gen_name} [dim]([u]{gen_path}[/u])[/dim]\n"
        f"[bold blue]runtime  [/bold blue] {run_name} [dim]([u]{run_path}[/u])[/dim]"
    )
    rprint(
        Panel(
            inspection_results,
            title="[bold white]Protocol Inspection[/bold white]",
            border_style="cyan",
        )
    )

    ctx.obj = {"runner": runner, "resume": resume}


@run_app.command(name="monte-carlo")
def run_monte_carlo(
    ctx: typer.Context,
    n_trial: NTrialType = DEFAULT_MC_N_TRIAL,
    n_proc: NProcType = DEFAULT_MC_N_PROC,
):
    """
    [bold yellow]Execute a Monte Carlo campaign.[/bold yellow]

    This command handles the directory setup, distribution salting, and parallel execution of physics trials.
    """
    from mujoco_mojo.utils.runner import MojoRunner, MonteCarloConfig

    # 1. Retrieve the shared values from the context
    runner: MojoRunner = ctx.obj["runner"]
    resume: bool = ctx.obj["resume"]

    # 2. build config
    runner.config = MonteCarloConfig(n_trial=n_trial, n_proc=n_proc)

    # 3. run
    rprint(
        f"[bold magenta]Starting {n_trial} trials[/bold magenta] (using {n_proc} workers)..."
    )
    _results, had_fails = runner.run(resume=resume)

    if had_fails:
        preamble = "[bold red]Monte Carlo finished with failures![/bold red]"
    else:
        preamble = "[bold green]Monte Carlo finished![/bold green]"
    rprint(
        f"\n{preamble} Results located at [italic underline]{runner.workdir.resolve()}[/italic underline]"
    )

    raise typer.Exit()


@run_app.command(name="optimize")
def run_optimizer():
    """[dim]Placeholder for future optimization command...[/dim]"""
    rprint("[yellow]Optimization engine coming soon![/yellow]")


if __name__ == "__main__":
    app()
