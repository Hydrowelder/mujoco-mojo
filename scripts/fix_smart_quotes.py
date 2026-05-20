#!/usr/bin/env python3
import subprocess
from pathlib import Path

# Folder to scan
SRC_DIR = Path("src")

# Mapping of smart quotes to regular quotes
REPLACEMENTS = {
    "\u2005": " ",  # Four-Per-Em Space
    "\u200a": " ",  # Hair Space
    "\u200b": "",  # Zero Width Space (ZWSP)
    "\u2013": "-",  # En Dash
    "\u2018": "'",  # Left Single Quotation Mark
    "\u2019": "'",  # Right Single Quotation Mark
    "\u201c": '"',  # Left Double Quotation Mark
    "\u201d": '"',  # Right Double Quotation Mark
    "\u2026": "...",  # Horizontal Ellipsis
    "\u2061": "",  # Function Application
}


def fix_file(file_path: Path) -> bool:
    """
    Fix smart quotes in a file.
    Returns True if the file was modified.
    """
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"Skipping {file_path}: {e}")
        return False

    new_text = text
    for old, new in REPLACEMENTS.items():
        new_text = new_text.replace(old, new)

    if new_text != text:
        file_path.write_text(new_text, encoding="utf-8")
        return True
    return False


def stage_file(file_path: Path):
    """Stage the file in git."""
    subprocess.run(["git", "add", str(file_path)], check=True)


SKIP_DIRS = {"node_modules", "__pycache__", ".venv", ".git"}


def main():
    for file_path in SRC_DIR.rglob("*.*"):
        if SKIP_DIRS & set(file_path.parts):
            continue
        if file_path.suffix in {".py", ".md", ".txt", ".json", ".xml"}:
            modified = fix_file(file_path)
            if modified:
                stage_file(file_path)


if __name__ == "__main__":
    main()
