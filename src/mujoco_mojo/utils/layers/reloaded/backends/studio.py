import importlib
from typing import NoReturn

import mujoco

from mujoco_mojo.typing import UserInterface

__all__ = ["ViewerUnavailableError", "raise_studio_unavailable", "studio_available"]


class ViewerUnavailableError(RuntimeError):
    """The chosen viewer cannot run here. The message says why and what to use instead."""


def studio_available() -> bool:
    """Whether the installed MuJoCo includes Studio. Released builds do not yet, so this is only true for a build made from the MuJoCo source."""
    try:
        importlib.import_module("mujoco.studio._studio")
    except ImportError:
        return False
    return True


def raise_studio_unavailable(ui: UserInterface) -> NoReturn:
    """Raises `ViewerUnavailableError` for a Studio viewer, saying why it cannot start."""
    if studio_available():
        reason = (
            "MuJoCo Studio was found, but Mojo's Studio viewer is not finished yet."
        )
    else:
        reason = f"MuJoCo {mujoco.__version__} does not include MuJoCo Studio."
    raise ViewerUnavailableError(
        f"The `{ui.value}` viewer needs MuJoCo Studio. {reason} Use `-ui opengl` for now."
    )
