# Optimization

!!! abstract

    While a [Monte Carlo](../workflow/running-jobs/running-jobs.md) campaign explores the "what if" of random chance, Optimization helps answer the "what is best." Instead of drawing from static distributions, Mojo uses Optuna to intelligently navigate your design space, evolving your model parameters to minimize or maximize a specific physical outcome.

!!! note "Install Required"

    Optimization requires the `optuna`, `optuna-dashboard`, and `joblib` packages. Install with `uv add mujoco-mojo[optimize]` or `pip install mujoco-mojo[optimize]`.

---

## Design Variables vs. Distributions

In a standard Monte Carlo script, you use `mojo_model.sample_dist()` to represent uncertainty. In an optimization study, you replace these with Design Variables.

### Defining the Search Space

Mojo supports two primary types of design variables within your generate script:

- `DesignFloat`: For continuous parameters like spring stiffness, mass, or damping ratios.
- `DesignCategorical`: For discrete choices like material types (`['steel', 'aluminum']`) or solver methods.

???+ example "Example: Defining Design Variables"

    ```python
    # stiffness = mojo_model.sample_dist(mojo.NormalDistribution(...))
    stiffness = mojo_model.design_float(
        name="spring_stiffness",
        default=100.0,  # initial guess
        low=50.0,
        high=200.0
    )

    # material = mojo_model.sample_dist(mojo.CategoricalDistribution(...))
    material = mojo_model.design_categorical(
        name="structure_material",
        default="steel",
        choices=["steel", "aluminum", "play-doh"],
    )
    ```

???+ note "Note: Random Values and Overrides"

    Just because you are using design variables doesn't restrict you from defining distributions! You can very much still add "chaos" to your runs with the random values as you would for a Monte Carlo.

    If override named values are also provided, those will be used over a design value just like for stochastic values.

---

## The Objective Function Contract

The **Objective Function** is the "grade" you give to a simulation. It is a standalone function that Mojo calls after the runtime script finishes. Its job is to ingest the simulation results and return a single `#!python float`.

???+ example "Example: MojoObjective Handle"

    ```python
    --8<-- "docs/user-guides/features/optimization_example.py:score-handle"
    ```

A valid objective function must accept the `MojoModel`, the `Path` to the telemetry outputs requested during runtime, and an `MjState` object.

???+ example "Example: Scoring Performance"

    ```python
    --8<-- "docs/user-guides/features/optimization_example.py:score"
    ```

---

## Running the Optimizer

Optimization jobs are launched via the `mujoco-mojo run optimize` command (instead of `monte-carlo`). This engine orchestrates the feedback loop between your `generate` script, your `runtime` script, and your `objective` function.

### Key Command Line Arguments

| Argument                 | Shortcut | Description                                                                    |
|:-------------------------|:---------|:-------------------------------------------------------------------------------|
| `--direction`            | `-d`     | Whether to `minimize` (e.g., error) or `maximize` (e.g., efficiency).          |
| `--sampler`              | `-sm`    | The search algorithm. `tpe` is the workhorse; `cmaes` is for local refinement. |
| `--storage`              | `-st`    | Defines if a storage database will be placed in the workdir.                   |
| `--evals-per-trial`      | `-ept`   | Runs the sim *N* times with different seeds and averages the score.            |
| `--refine-search-factor` | `-rsf`   | **Aggressive Refinement**. On resume, shrinks bounds around the current best.  |

```bash linenums="0"
# Launch a 400-trial study with 10 parallel workers
mujoco-mojo run optimiztion \
    -g sim.generate \
    -r sim.runtime \
    --objective sim.objective \
    --n-trial 400 \
    --n-proc 10 \
    --seed 42 \
    --storage \
    --direction minimize
```

---

## Advanced Workflows: Zooming and Robustness

### Stochastic Robustness (`--evals-per-trial`)

In MuJoCo, a "lucky" seed can sometimes produce a great score that isn't actually robust. By setting `--evals-per-trial 5`, Mojo runs every trial 5 times with different joint noise and returns the mean score. This ensures the optimizer finds stable designs, not just lucky ones.

### Adaptive Refinement (`--refine-search-factor`)

Once you find a promising "neighborhood," you can resume the job with `--refine-search-factor 0.2 --resume`. This physically shrinks the search bounds by 80% around your current best trial, allowing the solver to find the absolute peak with high precision.

---

## Post-Processing

One difference you may notice with `mujoco-mojo dojo` is the new **Morph** tab not present for Monte-Carlo jobs. This new tab allows you to view the history of your optimization using [`optuna-dashboard`](https://github.com/optuna/optuna-dashboard).

To use this you must provide a storage database argument for you optimization job configuration.

---

!!! success

    The **Optimization** toolkit transforms MuJoCo Mojo from a diagnostic simulator into an automated engineering design tool. By replacing manual parameter sweeps with a closed-loop search, you can efficiently navigate high-dimensional design spaces where physical intuition often hits a ceiling.

    Whether you are filtering out physics noise with **multi-evaluation trials** or "zooming in" on a performance sweet spot with **adaptive refinement**, the Morph toolkit ensures that your final design is backed by rigorous convergence, not just a lucky seed.

??? example "Example: Full Optimization Script"
    ```python
    --8<-- "docs/user-guides/features/optimization_example.py"
    ```
