"""
Writes the command line reference of `mujoco-mojo` to `docs/reference/cli.md`.

The page is read off the Typer app itself, so every command, argument and option is on it with the type, default and help the command line gives, and it cannot drift from the code. It is a docs page like the others, in the Reference section: the docs site shows it, `scripts/gen_user_guide.py` bundles it into the package with the user guides, and SensAI answers questions about the commands from it.

Typer bundles its own copy of click (`typer._click`), so a `click.Group`, `click.Option` or `click.Argument` check on one of its commands is never true. This reads them by what they have instead: a command with `commands` is a group, and a parameter says what it is in `param_type_name`.

Usage:
    python scripts/gen_cli_reference.py           # rewrite the page
    python scripts/gen_cli_reference.py --check   # exit 1 if the page is out of date, changing nothing

The pre-commit hook `gen-cli-reference` runs it when the command line changes, and a test fails if the page is stale.
"""

from __future__ import annotations

import enum
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import typer
from rich.text import Text
from typer.main import get_command

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "docs" / "reference" / "cli.md"

_TYPE_NAMES = {
    "str": "text",
    "text": "text",
    "int": "integer",
    "integer": "integer",
    "int range": "integer",
    "integer range": "integer",
    "float": "number",
    "float range": "number",
    "path": "path",
    "boolean": "boolean",
}

_HEADER = (
    "<!-- Written by scripts/gen_cli_reference.py from the command line itself. "
    "Do not edit it by hand: change the command and run the script. -->"
)


def markdown_text(markup: str) -> str:
    """
    A help text as markdown, with its Rich markup taken out the way `--help` takes it out.

    The command line uses `[bold cyan]` for commands and code, which become backticks, and `[bold]` for emphasis; any other tag is dropped and its text kept. Lines of one paragraph are joined, as the terminal wraps them to its own width.
    """
    text = re.sub(r"\[bold cyan\](.*?)\[/bold cyan\]", r"`\1`", markup, flags=re.DOTALL)
    text = re.sub(r"\[bold\](.*?)\[/bold\]", r"**\1**", text, flags=re.DOTALL)
    plain = Text.from_markup(text).plain
    paragraphs = [" ".join(part.split()) for part in plain.split("\n\n")]
    return "\n\n".join(p for p in paragraphs if p)


def _cell(text: str) -> str:
    """Text for a table cell: one line, with the pipes escaped."""
    return markdown_text(text).replace("\n\n", " ").replace("|", "\\|")


def _is_group(command: Any) -> bool:
    return hasattr(command, "commands")


def _visible_params(command: Any, kind: str) -> list[Any]:
    return [
        p
        for p in command.params
        if p.param_type_name == kind and not getattr(p, "hidden", False)
    ]


def walk(command: Any, path: list[str]) -> Iterator[tuple[list[str], Any]]:
    """Each command under `command`, with its path, in the order they are defined. Hidden ones are left out."""
    yield path, command
    for name, sub in getattr(command, "commands", {}).items():
        if not getattr(sub, "hidden", False):
            yield from walk(sub, [*path, name])


def _range_text(kind: Any) -> str:
    low, high = getattr(kind, "min", None), getattr(kind, "max", None)
    if low is not None and high is not None:
        return f"between {low} and {high}"
    if low is not None:
        return f"at least {low}"
    if high is not None:
        return f"at most {high}"
    return ""


def type_text(param: Any) -> str:
    """What a parameter takes: its type, the choices it is limited to or the range it is in, and whether it can be repeated."""
    kind = param.type
    if getattr(param, "count", False):
        return "count"
    if getattr(param, "is_flag", False):
        return "flag"
    choices = getattr(kind, "choices", None)
    if choices:
        text = "one of " + ", ".join(f"`{c}`" for c in choices)
    else:
        name = str(kind.name)
        text = _TYPE_NAMES.get(name, name)
        if name.endswith("range") and (limit := _range_text(kind)):
            text += f", {limit}"
    return f"{text}, repeatable" if getattr(param, "multiple", False) else text


def default_text(param: Any) -> str:
    """What a parameter is when it is left out: `required`, `none`, or its default value as the command line writes it."""
    if param.required:
        return "required"
    default = param.default
    if getattr(param, "count", False):
        return f"`{default or 0}`"
    if getattr(param, "is_flag", False):
        both = getattr(param, "secondary_opts", None)
        if both:
            return f"`{param.opts[0] if default else both[0]}`"
        return "on" if default else "off"
    if default is None or default in ([], ()):
        return "none"
    if isinstance(default, enum.Enum):
        default = default.value
    elif isinstance(default, list | tuple):
        default = ", ".join(str(item) for item in default)
    return f"`{default}`"


def option_names(param: Any) -> str:
    """The names an option goes by. A flag that can be turned off shows both ways, as `--resume` / `--no-resume`."""
    names = ", ".join(f"`{name}`" for name in param.opts)
    off = getattr(param, "secondary_opts", None)
    if off:
        names += " / " + ", ".join(f"`{name}`" for name in off)
    return names


def usage_line(path: list[str], command: Any) -> str:
    """The command as it is typed: the program and sub-commands, `[OPTIONS]`, then each argument in capitals."""
    words = [" ".join(path)]
    if _is_group(command):
        return f"{words[0]} [OPTIONS] COMMAND [ARGS]..."
    words.append("[OPTIONS]")
    for arg in _visible_params(command, "argument"):
        name = str(arg.name).upper()
        words.append(name if arg.required else f"[{name}]")
    return " ".join(words)


def anchor(path: list[str]) -> str:
    """Where the heading of a command is on the page."""
    return " ".join(path).replace(" ", "-")


def _summary(command: Any) -> str:
    """The first paragraph of a command's help."""
    return markdown_text(command.help or "").split("\n\n")[0]


def _commands_table(rows: list[tuple[list[str], Any]]) -> str:
    lines = ["| Command | What it does |", "| :--- | :--- |"]
    for path, command in rows:
        link = f"[`{' '.join(path)}`](#{anchor(path)})"
        lines.append(f"| {link} | {_cell(_summary(command))} |")
    return "\n".join(lines)


def _options_table(params: list[Any]) -> str:
    lines = [
        "| Option | Type | Default | Description |",
        "| :--- | :--- | :--- | :--- |",
    ]
    lines += [
        f"| {option_names(p)} | {_cell(type_text(p))} | {default_text(p)} | {_cell(getattr(p, 'help', None) or '')} |"
        for p in params
    ]
    return "\n".join(lines)


def _arguments_table(params: list[Any]) -> str:
    lines = ["| Argument | Type | Description |", "| :--- | :--- | :--- |"]
    lines += [
        f"| `{str(p.name).upper()}` | {_cell(type_text(p))} | {_cell(getattr(p, 'help', None) or '')} |"
        for p in params
    ]
    return "\n".join(lines)


def _section(path: list[str], command: Any) -> str:
    """The page's section for one command: its heading, description, usage and tables, one heading level deeper for each sub-command it sits under."""
    level = "#" * len(path)
    blocks = [f"{level} `{' '.join(path)}`"]
    if command.help:
        blocks.append(markdown_text(command.help))
    blocks.append(f"```bash\n{usage_line(path, command)}\n```")
    arguments = _visible_params(command, "argument")
    if arguments:
        blocks.append("**Arguments**\n\n" + _arguments_table(arguments))
    options = _visible_params(command, "option")
    if options:
        blocks.append("**Options**\n\n" + _options_table(options))
    if _is_group(command):
        subs = [(p, c) for p, c in walk(command, path) if len(p) == len(path) + 1]
        blocks.append("**Commands**\n\n" + _commands_table(subs))
    return "\n\n".join(blocks)


def render(app: typer.Typer | None = None, program: str = "mujoco-mojo") -> str:
    """The text of the page for `app`, the `mujoco-mojo` command line unless another is given."""
    if app is None:
        from mujoco_mojo.utils.layers.cli import cli_app

        app = cli_app
    root = get_command(app)
    top = [(p, c) for p, c in walk(root, [program]) if len(p) == 2]
    blocks = [
        _HEADER,
        "# Command Line Reference",
        f"Every `{program}` command with its arguments and options. Add `--help` to any command to see the same in your terminal.",
        _commands_table(top),
    ]
    global_options = _visible_params(root, "option")
    if global_options:
        blocks.append("## Global options\n\n" + _options_table(global_options))
    for path, command in walk(root, [program]):
        if len(path) > 1:
            blocks.append(_section(path, command))
    return "\n\n".join(blocks) + "\n"


def stale() -> bool:
    """Whether the page is missing or differs from what the command line gives."""
    return not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != render()


def main(argv: list[str]) -> int:
    if "--check" in argv:
        if stale():
            print(f"out of date: {OUTPUT.relative_to(ROOT)}")
            print("Run: python scripts/gen_cli_reference.py")
        return 1 if stale() else 0
    if stale():
        OUTPUT.write_text(render(), encoding="utf-8", newline="\n")
        print(f"Written -> {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
