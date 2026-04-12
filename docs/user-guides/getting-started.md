# Getting Started

!!! abstract
    **MuJoCo Mojo** is a high-level Python framework designed to turn static MuJoCo simulations into robust, scalable, and stochastic experiment pipelines.

---

## Installation

Install `mujoco-mojo` using your preferred package manager. We recommend `uv` for speed and dependency management.

=== "`uv` (recommended)"

    ```bash
    uv add mujoco-mojo
    ```

=== "`pip`"

    ```bash
    pip install mujoco-mojo
    ```

!!! warning
    At the time of writing, MuJoCo supports up to Python 3.13. This package is built on modern Python requiring 3.12 or above.

---

## Core Concepts

Before writing code, it is helpful to understand the three pillars of a Mojo project:

* **The MojoModel:** This is your "Source of Truth." It contains the `mjcf` object (your model) and the `stochas` object (distributions and random variables).
    * This class relies upon `pydantic` V2 to statically type and validate entries.
* **The Generate-Runtime Pattern:** Mojo separates Generation (building the XML and sampling random values) from **Runtime** (the physics loop where forces and logic are applied).
    ```python
    def generate(
        mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
        # Add geoms, sites, and sample distributions here
        return mojo_model

    def runtime(
        mojo_model: mojo.MojoModel,
        runtime_manager: rt.RuntimeManager,
        mj_model: mujoco.MjModel,
        mj_data: mujoco.MjData,
        *args,
        **kwargs,
    ):
        # Step the physics and apply logic here
        while mj_data.time < 10.0:
            runtime_manager.step(mj_model, mj_data)
    ```
* **Request-Based Telemetry:** You don't (*have to*) manually log data. Instead, you "Request" that specific geoms, sites, or custom forces be tracked by the `ResultsManager`.

---

## The MJCF Object Model

The `mojo.mjcf` object is designed to be isomorphic to the MuJoCo XML schema.

!!! tip
    If you know how to write an XML file, you know how to use `mojo.mjcf`.

    It is recommended to reference the official [XML Reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html) for specifics on the XML schema.

* `<worldbody>` becomes `mojo.WorldBody()`.
* `<body name="box">` becomes `mojo.Body(name=mojo.BodyName("box"))`.
    * `mojo.BodyName` (and the other related names) are really strings, but are typed this way to allow for improved static analysis (e.g., if you try to use a `BodyName` where a `SiteName` is needed Pylance will warn you about the invalid type).
* Attributes like `pos` and `rgba` are strictly typed using NumPy arrays and Pydantic validation.

This design ensures that there is "no magic". You are simply building a MuJoCo model using a strongly-typed Python API instead of a fragile string-based XML file.

---

## Random Values and Distributions

Mojo treats stochasticity as a first-class citizen. Instead of using `np.random` directly, you define a **Distribution** and sample it through the `MojoModel`.

!!! tip
    For additional details on the stochastic tools provided, see the [`stochas` documentation](https://hydrowelder.github.io/stochas/)

```python
stiffness = mojo_model.sample_dist(
    mojo.TruncatedNormalDistribution(
        name=mojo.DistName("spring_stiffness"),
        nominal=100,
        mu=100,
        sigma=20,
        low=0,
    )
)
```

### Why use Mojo's sampling?

* **Reproducibility:** Every draw is anchored to a global seed.
* **Named Values:** Every random draw is saved as a `NamedValue`. This means your results database automatically knows exactly what "spring_stiffness" was used for Trial #42.
    * It also helps to ensure you do not accidentally overwrite or modify a value.
* **Global Overrides:** You can run a job and tell Mojo to ignore the distribution and force a specific `NamedValue` for testing.

!!! success
    This concludes our basic overview of the core concepts to MuJoCo Mojo. The next guide will cover how to get started with assembling your first model with the [generate script](generate-script.md).
