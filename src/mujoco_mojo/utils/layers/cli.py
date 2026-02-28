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
run_app = typer.Typer(help="Execution subcommands for trials.")
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
    """Helper to dynamically import user logic."""
    # Ensure current directory is in path for local simulation files
    if "." not in sys.path:
        sys.path.insert(0, ".")

    try:
        module_path, func_name = path.rsplit(".", 1)
        mod = importlib.import_module(module_path)
        return getattr(mod, func_name)
    except Exception as e:
        rprint(f"[bold red]Error:[/bold red] Could not load '{path}': {e}")
        raise typer.Exit(code=1)


@run_app.callback()
def run_globals(
    ctx: typer.Context,
    generator: GeneratorType = None,
    runtime: RuntimeType = DEFAULT_RUNTIME,
    workdir: WorkdirType = DEFAULT_WORKDIR,
    model_config_name: ModelConfigNameType = DEFAULT_MODEL_CONFIG_NAME,
    xml_name: XMLNameType = DEFAULT_XML_NAME,
    resume: ResumeType = DEFAULT_RESUME,
):
    """
    [bold yellow]Global settings for all simulation runs.[/bold yellow]
    """
    # Ensure ctx.obj exists even if we exit early
    ctx.ensure_object(dict)

    help_requested = any(arg in sys.argv for arg in ["-h", "--help"])
    if ctx.resilient_parsing or help_requested or generator is None:
        return

    from mujoco_mojo.utils.runner import MojoRunner

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
    )

    # dry-run check
    inspection_results = (
        f"[bold blue]Generator:[/bold blue] {runner.inspect_protocol(gen_func)}\n"
        f"[bold blue]Runtime:  [/bold blue] {runner.inspect_protocol(run_func)}"
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
    [bold green]Execute a Monte Carlo campaign.[/bold green]

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
    _results = runner.run(resume=resume)
    rprint(
        f"\n[bold green]Monte Carlo finished![/bold green] Results located at [italic underline]{runner.workdir.resolve()}[/italic underline]"
    )

    raise typer.Exit()


@run_app.command(name="optimize")
def run_optimizer():
    """[dim]Placeholder for future optimization command...[/dim]"""
    rprint("[yellow]Optimization engine coming soon![/yellow]")


if __name__ == "__main__":
    app()
