"""
Writes the MJCF model of each docs example that links to MuJoCo Live, to `docs/assets/models/<name>/model.xml`.

Each file is what the example's `generate` function builds, written the way the runner writes a trial's `model.xml`: one sample (seed 0, trial 0), before any runtime behavior. The docs link to it as `https://live.mujoco.org/?model=github:Hydrowelder/mujoco-mojo/master/docs/assets/models/<name>/model.xml`, which MuJoCo Live reads straight from GitHub, so the file has to stand on its own: a model with file assets (a mesh, an image texture) is refused until its assets are bundled beside it.

Usage:
    python scripts/gen_docs_models.py           # rewrite the models
    python scripts/gen_docs_models.py --check   # exit 1 if a model is out of date, changing nothing

The pre-commit hook `gen-docs-models` runs it before a push when the library or an example changes (a push stops if it rewrote a file, so commit the new model and push again), and a test fails if a committed model is stale.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import mujoco_mojo as mojo

ROOT = Path(__file__).parents[1]
OUTPUT_DIR = ROOT / "docs" / "assets" / "models"

SEED = 0
TRIAL_NUM = 0

# the docs examples with a model to open in MuJoCo Live: each one's folder name under `docs/assets/models`, and the example script whose `generate` builds it
EXAMPLES: dict[str, Path] = {
    "vlr": ROOT / "docs" / "user-guides" / "examples" / "vlr" / "vlr_example.py",
}


def output_path(name: str) -> Path:
    """Where the model of the example `name` is committed."""
    return OUTPUT_DIR / name / "model.xml"


def load_example(name: str) -> ModuleType:
    """Imports the example script, which sits outside any package. It is registered under its own name first because pydantic looks a class's module up there to resolve its annotations."""
    module_name = f"docs_example_{name}"
    spec = importlib.util.spec_from_file_location(module_name, EXAMPLES[name])
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load the example script {EXAMPLES[name]}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def render(name: str) -> str:
    """The XML of the example `name`, built the way the runner builds a trial's model."""
    generate: Callable[[mojo.MojoModel], mojo.MojoModel] = load_example(name).generate
    mojo_model = mojo.MojoModel().with_seed(seed=SEED).with_trial_num(TRIAL_NUM)
    mojo_model = generate(mojo_model)
    with tempfile.TemporaryDirectory() as tmp:
        bundled = mojo_model.mjcf.bundle_assets(
            target_dir=Path(tmp) / "assets", rel_to_xml=Path("assets")
        )
        if bundled:
            raise ValueError(
                f"The `{name}` model uses file assets, which MuJoCo Live cannot reach from a single linked XML file. Bundle them beside the model first."
            )
        return mojo_model.mjcf.write_xml(Path(tmp) / "model.xml")


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale = False
    for name in EXAMPLES:
        path = output_path(name)
        text = render(name)
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if text == current:
            continue
        if check:
            print(f"{path.relative_to(ROOT)} is out of date")
            stale = True
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {path.relative_to(ROOT)}")
    if stale:
        print("Run: python scripts/gen_docs_models.py")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
