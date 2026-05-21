"""
Generate API reference pages in docs/reference/.

Run this script before building the docs site:

    python scripts/gen_ref_pages.py

The output is written to docs/reference/ and is consumed by zensical (or
mkdocs) via the ::: autodoc directives.  The directory is gitignored; this
script must be run as part of the CI pipeline before zensical build.
"""

from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS_REF = ROOT / "docs" / "reference"

# ---------------------------------------------------------------------------
# Modules to document: (dotted identifier, output path relative to DOCS_REF)
# ---------------------------------------------------------------------------
MODULES: list[tuple[str, str]] = [
    ("mujoco_mojo.mojo_model", "mujoco_mojo/mojo_model.md"),
    ("mujoco_mojo.base", "mujoco_mojo/base.md"),
    ("mujoco_mojo.visualization", "mujoco_mojo/visualization.md"),
    # typing — enums and type aliases (some not re-exported at top level)
    ("mujoco_mojo.typing", "mujoco_mojo/typing.md"),
    # stochas — distributions and named values (has items not in top-level __all__)
    ("mujoco_mojo.stochas", "mujoco_mojo/stochas.md"),
    # runtime
    ("mujoco_mojo.runtime", "mujoco_mojo/runtime/index.md"),
    ("mujoco_mojo.runtime.load", "mujoco_mojo/runtime/load.md"),
    ("mujoco_mojo.runtime.runtime_manager", "mujoco_mojo/runtime/runtime_manager.md"),
    ("mujoco_mojo.runtime.signal_manager", "mujoco_mojo/runtime/signal_manager.md"),
    ("mujoco_mojo.runtime.video_recorder", "mujoco_mojo/runtime/video_recorder.md"),
    # utils
    ("mujoco_mojo.utils", "mujoco_mojo/utils/index.md"),
    ("mujoco_mojo.utils.color", "mujoco_mojo/utils/color.md"),
    ("mujoco_mojo.utils.runner", "mujoco_mojo/utils/runner.md"),
    ("mujoco_mojo.utils.proximity", "mujoco_mojo/utils/proximity.md"),
    ("mujoco_mojo.utils.filters", "mujoco_mojo/utils/filters.md"),
    ("mujoco_mojo.utils.interp", "mujoco_mojo/utils/interp.md"),
    ("mujoco_mojo.utils.dataframe", "mujoco_mojo/utils/dataframe.md"),
]

# ---------------------------------------------------------------------------
# Hand-written stub for mujoco_mojo.mjcf (too large to autodoc)
# ---------------------------------------------------------------------------
MJCF_STUB = """\
# mujoco\\_mojo.mjcf

The `mujoco_mojo.mjcf` subpackage provides the complete Python object model
for the MuJoCo XML schema.  It mirrors the official XML structure closely, so
the best reference is the upstream documentation:

[MuJoCo XML Reference :material-open-in-new:](https://mujoco.readthedocs.io/en/stable/XMLreference.html){ .md-button .md-button--primary target=_blank }

All `mjcf` types are re-exported from the top-level `mujoco_mojo` namespace,
so you rarely need to import directly from `mujoco_mojo.mjcf`.

```python
import mujoco_mojo as mojo

body = mojo.Body(name=mojo.BodyName("my_body"))
```
"""


def main() -> None:
    DOCS_REF.mkdir(parents=True, exist_ok=True)

    for module, rel_path in MODULES:
        dest = DOCS_REF / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f"::: {module}\n", encoding="utf-8")
        print(f"  {dest.relative_to(ROOT)}")

    mjcf_page = DOCS_REF / "mujoco_mojo" / "mjcf.md"
    mjcf_page.write_text(MJCF_STUB, encoding="utf-8")
    print(f"  {mjcf_page.relative_to(ROOT)}")

    print(f"\nWrote {len(MODULES) + 1} pages to {DOCS_REF.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
