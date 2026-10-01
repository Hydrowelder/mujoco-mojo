from pathlib import Path
from typing import Final

from mujoco_mojo.typing import Sampler

__all__ = [
    "DEFAULT_MC_N_TRIAL",
    "DEFAULT_MODEL_CONFIG_NAME",
    "DEFAULT_N_PROC",
    "DEFAULT_OP_N_TRIAL",
    "DEFAULT_OP_SAMPLER",
    "DEFAULT_OP_STORAGE",
    "DEFAULT_OP_STUDY_NAME",
    "DEFAULT_OP_TIMEOUT",
    "DEFAULT_RESUME",
    "DEFAULT_RUNTIME",
    "DEFAULT_SEED",
    "DEFAULT_XML_NAME",
    "NAMED_VALUES_FNAME",
    "STOCHAS_DIR_NAME",
    "STOCHAS_DISTS_FNAME",
    "TIME_COLUMN_NAME",
]

TIME_COLUMN_NAME: Final = "time"
"""Name of the time column in signal outputs."""

# MojoRunner defaults
DEFAULT_RUNTIME: Final = None
DEFAULT_WORKDIR: Final = Path("./mojo-models")
DEFAULT_MODEL_CONFIG_NAME: Final = None
DEFAULT_XML_NAME: Final = "model.xml"
NAMED_VALUES_FNAME: Final = "named_values.json"
STOCHAS_DIR_NAME: Final = "stochas"
STOCHAS_DISTS_FNAME: Final = "dists.json"
DEFAULT_SEED: Final = None
DEFAULT_N_PROC: Final = 1

# MonteCarloConfig defaults
DEFAULT_MC_N_TRIAL: Final = 2

# OptimizeConfig defaults
DEFAULT_OP_N_TRIAL: Final = 100
DEFAULT_OP_STUDY_NAME: Final = "mojo-study"
DEFAULT_OP_TIMEOUT: Final = None
DEFAULT_OP_STORAGE: Final = None
DEFAULT_OP_SAMPLER: Final = Sampler.TPE
DEFAULT_OP_EVALS_PER_TRIAL: Final = 1
DEFAULT_OP_REFINE_SEARCH_FACTOR: Final = None
DEFAULT_OP_PRUNE_FAILED_TRIALS: Final = True

# run defaults
DEFAULT_RESUME: Final = True
