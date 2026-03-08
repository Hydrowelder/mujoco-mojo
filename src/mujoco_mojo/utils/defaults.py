from pathlib import Path

__all__ = [
    "DEFAULT_MC_N_PROC",
    "DEFAULT_MC_N_TRIAL",
    "DEFAULT_MODEL_CONFIG_NAME",
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

# MonteCarloConfig defaults
DEFAULT_MC_N_TRIAL = 2
DEFAULT_MC_N_PROC = 1

# run defaults
DEFAULT_RESUME = True
