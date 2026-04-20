from pathlib import Path
from typing import Literal

__all__ = [
    "DEFAULT_MC_N_TRIAL",
    "DEFAULT_MODEL_CONFIG_NAME",
    "DEFAULT_N_PROC",
    "DEFAULT_OP_DIRECTION",
    "DEFAULT_OP_N_TRIAL",
    "DEFAULT_OP_SAMPLER",
    "DEFAULT_OP_STORAGE",
    "DEFAULT_OP_STUDY_NAME",
    "DEFAULT_OP_TIMEOUT",
    "DEFAULT_RESUME",
    "DEFAULT_RUNTIME",
    "DEFAULT_SEED",
    "DEFAULT_XML_NAME",
]


# MojoRunner defaults
DEFAULT_RUNTIME = None
DEFAULT_WORKDIR = Path("./mojo-models")
DEFAULT_MODEL_CONFIG_NAME = "model_config.json"
DEFAULT_XML_NAME = "model.xml"
DEFAULT_SEED = None
DEFAULT_N_PROC = 1

# MonteCarloConfig defaults
DEFAULT_MC_N_TRIAL = 2

# OptimizeConfig defaults
DEFAULT_OP_N_TRIAL = 100
DEFAULT_OP_STUDY_NAME = "mojo-study"
DEFAULT_OP_DIRECTION = "minimize"
DEFAULT_OP_TIMEOUT = None
DEFAULT_OP_STORAGE = None
DEFAULT_OP_SAMPLER = "tpe"
SamplerOptions = Literal[
    "tpe", "cmaes", "random", "nsgaii", "nsgaiii", "qmc", "gp", "brute"
]
DEFAULT_OP_EVALS_PER_TRIAL = 1
DEFAULT_OP_REFINE_SEARCH_FACTOR = None
DEFAULT_OP_PRUNE_FAILED_TRIALS = True

# run defaults
DEFAULT_RESUME = True
