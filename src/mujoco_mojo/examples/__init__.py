"""
The examples that ship with mujoco-mojo, which `mujoco-mojo examples run <name>` opens in Reloaded.

Each example is a folder of its own, whose `simulation.py` has the `generate` and `runtime` functions, so it also runs like a model of your own, by its import path: `mujoco-mojo reloaded -g mujoco_mojo.examples.vlr.simulation.generate -r mujoco_mojo.examples.vlr.simulation.runtime`. The guides in the docs walk through their code.

An example builds its model from MuJoCo's built-in textures and Mojo's generated meshes, so it needs no file beyond the package and runs offline. This module only names them and imports none of them, since `berthing` needs the `examples` extra.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

__all__ = ["EXAMPLES", "Example", "ExampleName"]


class ExampleName(StrEnum):
    """The examples, by the name `mujoco-mojo examples run` takes."""

    VLR = "vlr"
    BERTHING = "berthing"
    BOXES_AND_SPRINGS = "boxes-and-springs"
    BOXES_AND_SPRINGS_OPTIMIZATION = "boxes-and-springs-optimization"
    TENNIS_RACKET = "tennis-racket"


class Example(BaseModel):
    """An example: the module that holds its `generate` and `runtime` functions, and what it models."""

    model_config = ConfigDict(frozen=True)

    module: str
    """Import path of the module with the `generate` and `runtime` functions."""

    summary: str
    """What the example models, in a sentence, which `mujoco-mojo examples list` shows."""

    @property
    def generator(self) -> str:
        """Import path of the `generate` function."""
        return f"{self.module}.generate"

    @property
    def runtime(self) -> str:
        """Import path of the `runtime` function."""
        return f"{self.module}.runtime"


EXAMPLES: dict[ExampleName, Example] = {
    ExampleName.VLR: Example(
        module="mujoco_mojo.examples.vlr.simulation",
        summary="A rocket that falls and lands on four spring-damped legs.",
    ),
    ExampleName.BERTHING: Example(
        module="mujoco_mojo.examples.berthing.simulation",
        summary="A seven-joint robotic arm that grabs a visiting vehicle and berths it to a station. Needs the examples extra.",
    ),
    ExampleName.BOXES_AND_SPRINGS: Example(
        module="mujoco_mojo.examples.boxes_and_springs.simulation",
        summary="Two boxes joined by springs, with randomized inputs for a Monte Carlo study.",
    ),
    ExampleName.BOXES_AND_SPRINGS_OPTIMIZATION: Example(
        module="mujoco_mojo.examples.boxes_and_springs_optimization.simulation",
        summary="Two boxes joined by springs, with an objective to tune them in an optimization study.",
    ),
    ExampleName.TENNIS_RACKET: Example(
        module="mujoco_mojo.examples.tennis_racket.simulation",
        summary="A racket spun about its middle axis, which flips over and over (the tennis racket theorem).",
    ),
}
"""Every example, by name."""
