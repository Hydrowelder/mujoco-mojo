# Getting Started

!!! abstract

    **MuJoCo Mojo** is a high-level Python framework designed to turn static MuJoCo simulations into robust, scalable, and stochastic experiment pipelines.

---

## Installation

Install `mujoco-mojo` using your preferred package manager. We recommend `uv` for speed and dependency management.

=== "`uv` (recommended)"

    ```bash linenums="0"
    uv add mujoco-mojo
    ```

=== "`pip`"

    ```bash linenums="0"
    pip install mujoco-mojo
    ```

!!! tip "Optional Extras"

    Some features require extra packages: `mujoco-mojo[optimize]` for Optuna-based optimization, `mujoco-mojo[mesh-decomp]` for CoACD mesh decomposition, and `mujoco-mojo[reloaded]` for the Viser-based live viewer. Install `mujoco-mojo[all]` to get everything.

---

## Core Concepts

Before writing code, it is helpful to understand the three pillars of a Mojo project:

- **The MojoModel:** This is your "Source of Truth." It contains the `mjcf` object (your model) and the `stochas` object (distributions and random variables).
  - This class relies upon `pydantic` V2 to statically type and validate entries.
- **The Generate-Runtime Pattern:** Mojo separates Generation (building the XML and sampling random values) from **Runtime** (the physics loop where forces and logic are applied).

???+ example "Example: Generate and Runtime Functions"

    ```python
    import mujoco_mojo as mojo

    def generate(
        mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
        # Add geoms, sites, and sample distributions here
        return mojo_model

    def runtime(
        mojo_model: mojo.MojoModel,
        runtime_manager: rt.RuntimeManager,
        state: mojo.MjState,
        *args,
        **kwargs,
    ):
        # Step the physics and apply logic here
        while state.data.time < 10.0:
            runtime_manager.step(state)
    ```

- **Request-Based Telemetry:** You don't (_have to_) manually log data. Instead, you "Request" that specific geoms, sites, or custom forces be tracked by the `SignalManager`.

---

## The MJCF Object Model

The `mojo.mjcf` object is designed to be isomorphic to the MuJoCo XML schema.

???+ quote "You Can Do It!"

    If you know how to write an XML file, you know how to use `mojo.mjcf`.

    It is recommended to reference the official [XML Reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html) for specifics on the XML schema.

- `<worldbody>` becomes `mojo.WorldBody()`.
- `<body name="box">` becomes `mojo.Body(name=mojo.BodyName("box"))`.
  - `mojo.BodyName` (and the other related names) are really strings, but are typed this way to allow for improved static analysis (e.g., if you try to use a `BodyName` where a `SiteName` is needed Pylance will warn you about the invalid type).
- Attributes like `pos` and `rgba` are strictly typed using NumPy arrays and Pydantic validation.

This design ensures that there is "no magic". You are simply building a MuJoCo model using a strongly-typed Python API instead of a fragile string-based XML file.

???+ warning "Warning: Default Values"

    Some attributes in this package make use of default values. Wherever possible, the default values match what is stated in the [XML Reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html#xml-reference){:target="_blank"}.

    The `to_xml` method found in all `XMLModel` (which is most objects in `mujoco_mojo.mjcf`) has an argument (`exclude_defaults`) which will omit serializing fields set as default.

    If you have a specific use case which is dependent on a value you leave as default, it is highly recommended that you pin that value as opposed to use the default. MuJoCo may change their defaults, and this package may fall behind. In that case, you would be using a "default" which is no longer the default.

---

## Random Values and Distributions

Mojo treats stochasticity as a first-class citizen. Instead of using `np.random` directly, you define a **Distribution** and sample it through the `MojoModel`.

???+ note "Note: Extra Reading"

    For additional details on the stochastic tools provided, see the [`stochas` documentation](https://hydrowelder.github.io/stochas/)

???+ example "Example: Sampling a Distribution with `MojoModel`"

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

- **Reproducibility:** Every draw is anchored to a global seed.
- **Named Values:** Every random draw is saved as a `NamedValue`. This means your results database automatically knows exactly what "spring_stiffness" was used for Trial #42.
  - It also helps to ensure you do not accidentally overwrite or modify a value.
- **Global Overrides:** You can run a job and tell Mojo to ignore the distribution and force a specific `NamedValue` for testing.

---

## MuJoCo Syntax Highlighting

MuJoCo does not currently ship first-party Python typing stubs. To enable proper autocomplete and static type checking (Pylance/Pyright), generate local stubs using `pybind11-stubgen`.

> Thanks to the work by [@kevinzakka](https://github.com/google-deepmind/mujoco/issues/1292#issuecomment-1874138201) and [@mluogh-xdof](https://github.com/google-deepmind/mujoco/issues/1292#issuecomment-3208219200) for figuring all this out!

1. From your project root, generate stubs into a local `typings/` directory:

   ```bash linenums="0"
   pybind11-stubgen mujoco -o typings/ --numpy-array-wrap-with-annotated
   pybind11-stubgen mujoco.viewer -o typings/ --numpy-array-wrap-with-annotated
   ```

   The second command adds the stubs for `mujoco.viewer`, which the first does not cover.

2. Recent MuJoCo builds compiled with newer pybind11 versions correctly expose enums as `SupportsInt`. If you encounter Pyright enum type errors, apply the compatibility patch:

   ```bash linenums="0"
   python typings/patch_mujoco_enums.py typings/mujoco/_enums.pyi
   ```

3. Then in `pyproject.toml` (for me, VSCode already type hints correctly, but this should fix things if you use `pyright` with your pre-commit hooks):

   ```toml title="pyproject.toml"
   [tool.pyright]
   stubPath = "typings"
   venvPath = "."
   venv = ".venv"
   ```

---

!!! tip "Tip: Scaffold a New Project"

    Before diving into the generate script, run `mujoco-mojo init` in a new directory to get a working project skeleton (`simulation.py`, `run.sh`, and `reloaded.sh`) pre-wired and ready to edit.

    ```bash linenums="0"
    mujoco-mojo init
    ```

    See the [Initializing a Project](init.md) guide for details.

!!! success

    This concludes our basic overview of the core concepts to MuJoCo Mojo. The next guide will cover how to get started with assembling your first model with the [generate script](generate-script.md).
