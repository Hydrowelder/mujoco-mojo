---
hide:
  - navigation
#   - toc
---
<style>
  .md-typeset h1,
  .md-content__button {
    display: none;
  }
</style>

<p align="center" class="mojo-splash">
  <img src="assets/light-hero-logo.svg" alt="MuJoCo Mojo Logo">
</p>

A **complete MJCF lifecycle and trial orchestration suite** for MuJoCo, powered by **Pydantic v2**.

**MuJoCo Mojo** bridges the gap between static XML modeling and large-scale simulation research. It provides a strongly-typed bridge for building models and a robust execution engine for running them at scale.

* **Model:** Build MJCFs via **validated Python objects**—no more manual XML hacking.
* **Scale:** Execute **multi-threaded Monte Carlo trials** with built-in resume logic.
* **Monitor:** Track progress via a **zero-dependency web dashboard** and persistent logs.
* **Reproduce:** Automatic **environment snapshotting** (`requirements.txt`) for every job.

## Installation

Install `mujoco-mojo` in your project using the following:

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


## Features

### MJCF Tools
* Strongly-typed MJCF elements backed by Pydantic v2
* Early validation of MJCF structure and attribute semantics
* Pythonic composition of assets, bodies, sensors, and plugins
* Designed to mirror MuJoCo’s XML schema closely (no magic abstractions)
* Suitable for code generation, tooling, and large model pipelines
* Embedded MuJoCo object enumerations to make getting `mjOBJ` IDs simple
* Specialized handling of dependency by remapping assets to become shared allows for space efficient execution of complex models

### Job Utilities
* Single or multi-threaded trial execution
* Random draw tools for Monte Carlo or rerun with global variable override
* Detailed status files for insight on trial progress
* Resume a previously started job without rerunning previous cases
* Automatically record installed Python packages to `requirements.txt` for job recreation (works with `uv` or `pip`)
* End of run summary with metric to help perform a state of health check
* Flexible command line utilities to run jobs

    ??? example
        ```bash
        mujoco-mojo run monte-carlo \
            --generator monte_carlo_test.Experiment.generate \
            --runtime monte_carlo_test.runtime \
            --workdir ./mc_test/ \
            --no-resume \
            --gen-arg 123 \
            --gen-kwarg 'test=1234' \
            --n-trial 10 \
            --n-proc 1
        ```

* Lightweight browser-based dashboard tool for runtime monitoring with system/light/darkmode which works with or without an internet connection
* Built in Rich logging for terminal and a rotating file handler for persistent logs
