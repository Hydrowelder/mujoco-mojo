from mujoco_mojo.base import MojoBaseModel

__all__ = ["Var"]


class Var(MojoBaseModel):
    """Defines a reference to a variable. This is intended for use with variables used as random inputs for Monte Carlo analysis."""

    ref: str
