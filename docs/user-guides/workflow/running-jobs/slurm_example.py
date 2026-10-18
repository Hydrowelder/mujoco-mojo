# --8<-- [start:imports]
from pathlib import Path

import mujoco_mojo as mojo
from mujoco_mojo.utils.slurm import SlurmConfig

# --8<-- [end:imports]


def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Stands in for your generator, which lives in an importable module such as `sim.py`."""
    return mojo_model


# --8<-- [start:submit]
if __name__ == "__main__":
    runner = mojo.utils.MojoRunner(
        generator=generate,
        generator_path="sim.generate",
        workdir=Path("my_job"),
        config=mojo.utils.MonteCarloConfig(n_trial=500, n_proc=1),
    )

    submission = runner.submit_slurm(
        SlurmConfig(
            partition="compute",
            cpus_per_task=4,
            mem="16G",
            time_limit="02:00:00",
            max_concurrent=50,
        )
    )
# --8<-- [end:submit]
