#!/usr/bin/env python3
import re
import subprocess
from pathlib import Path

# Folder to scan
SRC_DIR = Path.cwd() / "docs" / "user-guides"
EX_DIR = Path.cwd() / "examples"

MAP = {
    SRC_DIR / "monte_carlo_example.py": EX_DIR / "boxes_and_springs_monte_carlo.py",
    SRC_DIR / "optimization_example.py": EX_DIR / "boxes_and_springs_optimization.py",
}

CONFIG_PATH = Path.cwd() / "pyproject.toml"


def clean_and_copy_file(source: Path, dest: Path) -> None:
    """
    Fix smart quotes in a file.
    Returns True if the file was modified.
    """
    try:
        text = source.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"Skipping {source}: {e}")
        return

    pattern = r"^\s*# --8<--.*$\n?"
    cleaned_text = re.sub(pattern, "", text, flags=re.MULTILINE)

    dest.write_text(cleaned_text, encoding="utf-8")

    try:
        # Check if config exists, otherwise ruff might fail on missing file
        ruff_args = ["ruff", "format", str(dest)]
        if CONFIG_PATH.exists():
            ruff_args.extend(["--config", str(CONFIG_PATH)])

        subprocess.run(ruff_args, check=True, capture_output=True)

        # Do the same for check --fix
        check_args = ["ruff", "check", "--fix", str(dest)]
        if CONFIG_PATH.exists():
            check_args.extend(["--config", str(CONFIG_PATH)])

        subprocess.run(check_args, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"Ruff error on {dest.name}: {e.stderr.decode()}")


def stage_file(file_path: Path):
    """Stage the file in git."""
    subprocess.run(["git", "add", str(file_path)], check=True)


def main():
    for source, dest in MAP.items():
        clean_and_copy_file(source, dest)
        stage_file(dest)


if __name__ == "__main__":
    main()
