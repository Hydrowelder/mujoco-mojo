import datetime
import re
import sys
from pathlib import Path

from mujoco_mojo.utils.changelog import parse_changelog


def main() -> int:
    changelog_path = Path("CHANGELOG.md")
    if not changelog_path.exists():
        print("ERROR: CHANGELOG.md file not found!", file=sys.stderr)
        return 1

    # Get today's local date in YYYY-MM-DD format
    today_str = datetime.date.today().isoformat()

    pushed_tags: list[str] = []

    # Git passes pushed refs via stdin in the format:
    # <local ref> <local sha> <remote ref> <remote sha>
    for line in sys.stdin.read().splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) < 3:
            continue

        local_ref = parts[0]

        # Extract the version string ONLY if a tag ref is currently being pushed (e.g. refs/tags/v2.6.8 or refs/tags/2.6.8)
        tag_match = re.match(r"^refs/tags/v?([0-9]+\.[0-9]+\.[0-9]+)", local_ref)
        if tag_match:
            pushed_tags.append(tag_match.group(1))

    # If no version tag is being pushed in this command (e.g. normal branch push), pass cleanly
    if not pushed_tags:
        return 0

    entries_by_version = {
        entry.version: entry for entry in parse_changelog(changelog_path.read_text())
    }
    errors = []

    for version in pushed_tags:
        # matched via parse_changelog's structured entries, not a string
        # search - expected_header is only for the error messages below
        expected_header = f"## Version {version} ({today_str})"
        entry = entries_by_version.get(version)

        if entry is None:
            errors.append(
                f"ERROR: Pushed tag 'v{version}' does not have a matching heading in CHANGELOG.md!\n"
                f"  Expected exact format: {expected_header}"
            )
        elif entry.date is None:
            errors.append(
                f"ERROR: CHANGELOG.md heading for tag 'v{version}' has a malformed date!\n"
                f"  Expected exact format: {expected_header}"
            )
        elif entry.date != today_str:
            errors.append(
                f"ERROR: Date mismatch for tag 'v{version}' in CHANGELOG.md!\n"
                f"  Found date:   {entry.date}\n"
                f"  Today's date: {today_str}\n"
                f"  Expected exact format: {expected_header}"
            )

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
