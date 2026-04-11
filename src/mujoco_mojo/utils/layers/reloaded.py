import logging
import sys
import time
from bdb import BdbQuit
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import mujoco
import typer
from numpydantic import NDArray
from rich.console import Console
from rich.panel import Panel

from mujoco_mojo.mojo_model import MojoModel
from mujoco_mojo.stochas import NamedValueDict
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.runner import MojoGenerator

from .cli import UserInterface

logger = get_logger(__name__)
console = Console()

INTENTIONAL_DELAY = 0.75


@runtime_checkable
class OnReloadCallback(Protocol):
    def __call__(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData) -> Any: ...


@runtime_checkable
class IsRunningCheck(Protocol):
    def __call__(self) -> Any: ...


def recursive_reload(module, project_root: Path, visited: set | None = None):
    """Recursively reloads modules, but only if they live inside project_root."""
    import importlib
    import sys

    if visited is None:
        visited = set()

    if module in visited:
        return
    visited.add(module)

    # skip reloading these
    BLOCKLIST = {"numpy", "scipy", "matplotlib", "PIL", "cv2", "mujoco"}

    if getattr(module, "__name__", "") in BLOCKLIST:
        return

    for name in list(module.__dict__.keys()):
        obj = module.__dict__[name]
        if hasattr(obj, "__module__"):
            child_module_name = obj.__module__
            child_module = sys.modules.get(child_module_name)

            if child_module and child_module not in visited:
                child_file = getattr(child_module, "__file__", None)

                if child_file:
                    child_path = Path(child_file).resolve()

                    # must be inside project root AND NOT inside site-packages
                    is_local = child_path.is_relative_to(project_root)
                    is_library = (
                        "site-packages" in child_path.parts
                        or "dist-packages" in child_path.parts
                    )

                    if is_local and not is_library:
                        recursive_reload(child_module, project_root, visited)

    try:
        importlib.reload(module)
    except Exception:
        # some modules (like namespace packages) can be finicky
        pass


def is_dark_mode() -> bool:
    """Determine if the system is in dark mode using only the standard library."""
    import platform
    import subprocess

    system = platform.system()

    try:
        if system == "Windows":
            import winreg

            # Look at the 'Personalize' key for AppsUseLightTheme
            path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:  # pyright: ignore[reportAttributeAccessIssue]
                # 0 = Dark, 1 = Light
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")  # pyright: ignore[reportAttributeAccessIssue]
                return value == 0

        elif system == "Darwin":  # macOS
            # 'defaults read -g AppleInterfaceStyle' returns 'Dark' or errors out if Light
            cmd = ["defaults", "read", "-g", "AppleInterfaceStyle"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return "Dark" in result.stdout

        elif system == "Linux":
            # Check GNOME/GTK settings (most common)
            cmd = ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return "dark" in result.stdout.lower()

    except Exception:
        # Fallback to Light Mode if anything fails (e.g. old Windows versions)
        return False

    return False


@dataclass
class MojoReloaded:
    generator: str
    workdir: Path
    ui: UserInterface
    overrides_path: Path | None
    trial_num: int
    seed: int | None
    model_config_name: str
    xml_name: str
    gen_args: list[Any]
    gen_kwargs: dict[str, Any]
    host: str
    port: int

    def generate_construct(self) -> tuple[mujoco.MjModel, mujoco.MjData]:
        """Helper to run a generation."""
        from .cli import _load_func

        project_root = Path.cwd()
        gen_func: MojoGenerator = _load_func(self.generator)
        module_name = gen_func.__module__

        if module_name in sys.modules:
            try:
                recursive_reload(sys.modules[module_name], project_root)
                gen_func = _load_func(self.generator)
            except Exception as e:
                # If there's a syntax error in their change, we'll catch it here
                logger.error(f"Reload failed: {e}")
                raise e

        global_overrides = NamedValueDict[NDArray]()
        if self.overrides_path and self.overrides_path.exists():
            logger.info(
                f"Retrieving global NamedValue overrides from `{self.overrides_path}`"
            )
            global_overrides = NamedValueDict[NDArray].model_validate_json(
                self.overrides_path.read_text()
            )

            if len(global_overrides) == 0:
                logger.warning(
                    "Global NamedValue overrides had no entries. Continuing anyway."
                )
            else:
                logger.info(
                    f"Global NamedValue overrides had {len(global_overrides)} entries."
                )

        mojo_model = (
            MojoModel()
            .with_overrides(overrides=global_overrides)
            .with_seed(seed=self.seed)
            .with_trial_num(self.trial_num)
        )
        mojo_model = gen_func(
            mojo_model,
            global_overrides,
            *self.gen_args,
            **self.gen_kwargs,
        )
        mojo_model.dump_to_path(self.workdir / self.model_config_name)
        mj_model, mj_data = mojo_model.mjcf.prep_for_sim(
            save_path=self.workdir / self.xml_name
        )
        mujoco.mj_forward(mj_model, mj_data)
        return mj_model, mj_data

    def run(self):
        self.workdir = self.workdir.resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        (self.workdir / ".gitignore").write_text("*")

        try:
            with console.status(
                "[bold magenta]Performing initial generation...[/bold magenta]"
            ):
                mj_model, mj_data = self.generate_construct()
                time.sleep(INTENTIONAL_DELAY)
        except Exception as e:
            console.print(f"[bold red]Initial Generation Failed:[/bold red] {e}")
            raise typer.Exit(1)

        match self.ui:
            case UserInterface.OPENGL:
                self.run_opengl(mj_model, mj_data)
            case UserInterface.MJVISER | UserInterface.VISER:
                self.run_viser(mj_model, mj_data)
            case _:
                console.print(f"Invalid viewer option selected {self.ui}")
        console.print("\n[bold yellow]Exiting MuJoCo Mojo Reloaded[/bold yellow]")

    def _interactive_loop(
        self, on_reload_callback: OnReloadCallback, is_running_check: IsRunningCheck
    ):
        console.print(
            Panel(
                "[bold green]MuJoCo Mojo Reloaded is Live![/bold green]\n\n"
                "1. Edit your generator code.\n"
                "2. Press [bold yellow]ENTER[/bold yellow] here to push changes.\n"
                "3. Type [bold red]'exit'[/bold red] to close.",
                title="Mojo Reloaded",
                border_style="cyan",
            )
        )
        while is_running_check():
            try:
                cmd = (
                    console.input(
                        "[bold green]Awaiting reload command[/bold green]:[white] Press [bold yellow]ENTER[/bold yellow] to reload > [/white]"
                    )
                    .strip()
                    .lower()
                )
                if cmd in ["exit", "quit", "q"]:
                    break
            except (BdbQuit, KeyboardInterrupt):
                break

            try:
                with console.status("[bold]Regenerating...[/bold]"):
                    new_mj_model, new_mj_data = self.generate_construct()
                    on_reload_callback(mj_model=new_mj_model, mj_data=new_mj_data)
                    time.sleep(INTENTIONAL_DELAY)
                console.print("[bold green]Model Reloaded.[/bold green]")

            except Exception as e:
                console.print(
                    f"[bold red]Reload Failed:[/bold red]\n[white]{e}[/white]"
                )

    def run_opengl(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        import mujoco.viewer

        with mujoco.viewer.launch_passive(mj_model, mj_data) as viewer:

            def reload_handler(m: mujoco.MjModel, d: mujoco.MjData):
                sim = viewer._get_sim()
                if sim:
                    sim.load(m, d, str(self.workdir / self.xml_name))
                    viewer.sync()

            reload_handler(mj_model, mj_data)

            self._interactive_loop(
                lambda mj_model, mj_data: reload_handler(mj_model, mj_data),
                is_running_check=viewer.is_running,
            )

    def run_viser(self, mj_model: mujoco.MjModel, mj_data: mujoco.MjData):
        try:
            import viser
            from mjviser import ViserMujocoScene
        except ImportError:
            console.print(
                "The [bold]mjviser[/bold] UI option requires you to install [bold]mjviser[/bold] separately."
            )
            raise typer.Exit(1)
        import contextlib
        import io

        from mujoco_mojo.utils.color import Color
        from mujoco_mojo.utils.utils import get_local_ip

        for name in ["websockets"]:
            _l = logging.getLogger(name)
            _l.setLevel(logging.WARNING)
            _l.propagate = False

        def _print_connection_panel():
            local_ip = get_local_ip()

            connection_info = (
                f"Local: [bold cyan u]http://127.0.0.1:{self.port}[/bold cyan u]"
            )

            if self.host == "0.0.0.0":
                connection_info += f"\nMobile: [bold cyan u]http://{local_ip}:{self.port}[/bold cyan u]"
            else:
                connection_info += "\n\n[dim]Tip: To view on other devices, run with[/dim] [yellow]--host 0.0.0.0[/yellow]"

            console.print(
                Panel(
                    f"""{connection_info}\n\n[yellow]Press CTRL+C to stop[/yellow]""",
                    border_style="yellow",
                    title="Connection Info.",
                )
            )

        with contextlib.redirect_stdout(io.StringIO()):
            server = viser.ViserServer(
                host=self.host,
                port=self.port,
                label="MuJoCo Mojo Reloaded",
                verbose=False,
            )
        server.configure_theme(  # pyright: ignore[reportAttributeAccessIssue]
            dark_mode=is_dark_mode(),
            show_logo=False,
            brand_color=tuple(int(x) for x in (Color.CYAN_500.rgb * 255).round()),
        )

        server.scene.reset()
        scene = ViserMujocoScene(server=server, mj_model=mj_model, num_envs=1)
        scene.create_visualization_gui()
        scene.create_scene_gui()

        def update_scene(m: mujoco.MjModel, d: mujoco.MjData):
            scene = ViserMujocoScene(server=server, mj_model=m, num_envs=1)
            scene.update_from_mjdata(d)
            return scene

        update_scene(mj_model, mj_data)

        _print_connection_panel()

        self._interactive_loop(
            lambda mj_model, mj_data: update_scene(mj_model, mj_data), lambda: True
        )
        server.stop()
