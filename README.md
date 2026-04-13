<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/dark-hero-logo.svg">
    <img alt="MuJoCo Mojo" src="docs/assets/light-hero-logo.svg" style="height: 10.0em">
  </picture>
</p>

<p align="center">
  <a href="https://pypi.org/project/mujoco-mojo/" class="badge-link" style="text-decoration:none;">
    <img src="https://img.shields.io/pypi/v/mujoco-mojo.svg?cacheSeconds=300" alt="PyPI version">
  </a>
  <a href="https://pypi.org/project/mujoco-mojo/" class="badge-link" style="text-decoration:none;">
    <img src="https://img.shields.io/pypi/pyversions/mujoco-mojo.svg?cacheSeconds=86400" alt="Python versions">
  </a>
  <a href="https://github.com/Hydrowelder/mujoco-mojo/actions/workflows/release.yml" class="badge-link" style="text-decoration:none;">
    <img src="https://github.com/Hydrowelder/mujoco-mojo/actions/workflows/release.yml/badge.svg?branch=master" alt="Tests & Release Status">
  </a>
  <a href="https://docs.pydantic.dev/latest/" class="badge-link" style="text-decoration:none;">
    <img src="https://img.shields.io/badge/Pydantic-v2-FF43A1?logo=pydantic&logoColor=white" alt="Pydantic v2">
  </a>
  <a href="https://opensource.org/licenses/Apache-2.0" class="badge-link" style="text-decoration:none;">
    <img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License">
  </a>
  <a href="https://hydrowelder.github.io/mujoco-mojo/" class="badge-link" style="text-decoration:none;">
    <img src="https://img.shields.io/badge/docs-GitHub_Pages-blue.svg" alt="Documentation">
  </a>
  <a href="https://github.com/Hydrowelder/mujoco-mojo/discussions" class="badge-link" style="text-decoration:none;">
    <img src="https://img.shields.io/badge/discussions-GitHub-blue?logo=github&logoColor=white" alt="GitHub Discussions">
  </a>
  <a href="https://pypistats.org/packages/mujoco-mojo" class="badge-link" style="text-decoration:none;">
    <img src="https://img.shields.io/pypi/dm/mujoco-mojo.svg?cacheSeconds=86400" alt="Downloads">
  </a>
</p>

---

A **complete MJCF lifecycle and trial orchestration suite** for MuJoCo, powered by **Pydantic v2**.

**MuJoCo Mojo** bridges the gap between static XML modeling and large-scale simulation research. It provides a strongly-typed bridge for building models and a robust execution engine for running them at scale.

* **Model:** Build MJCFs via **validated Python objects** allowing for programatic generation.
* **Scale:** Execute **multi-threaded Monte Carlo trials** with built-in resume logic.
* **Monitor:** Track progress via a **zero-dependency web dashboard** and persistent logs.
* **Assess:** Quickly view **interactive results** of a trial in context of others.
* **Reproduce:** Automatic **environment snapshotting** (`requirements.txt`) for every job.

## Installation
Install using `uv` (recommended):

```bash
uv add mujoco-mojo
```

or with `pip`:

```bash
pip install mujoco-mojo
```

> [!WARNING]
> At the time of writing, MuJoCo supports up to Python 3.13

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

> [!TIP]
> ```bash
> mujoco-mojo run monte-carlo \
>     --generator monte_carlo_test.Experiment.generate \
>     --runtime monte_carlo_test.runtime \
>     --n-trial 10 \
>     --n-proc 4
> ```

* Support for running jobs with SLURM for distributed compute
* Built in Rich logging for terminal and a rotating file handler for persistent logs

### Dojo Dashboard

A zero-dependency, offline-first web suite for monitoring and analyzing your simulation jobs in real-time.

#### Monitor: Real-Time Oversight

* **Live Progress Tracking:** Dynamic progress bars and color-coded status cards provide a high-level view of your Monte Carlo runs.
* **Success/Failure Analytics:** Automatic categorization of trials with built-in data integrity checks to identify "empty" vs. "failed" runs.
* **Sensory Feedback:** Optional audio cues and visual celebrations let you know exactly when a multi-hour job hits 100%.
* **Deep-Linked Navigation:** Jump straight from the monitor to any individual trial in the viewer with one click.

#### Mosaic: Advanced Telemetry Analysis

* **High-Fidelity Plotting:** Hardware-accelerated visualization using Plotly.js for seamless zooming and panning through millions of data points.
* **Dynamic Versus Mode:** Overlay current telemetry against previous trials using an intuitive range-selection slider for instant regression testing.
* **Regex-Powered Filtering:** Navigate high-dimensional datasets using a "folder-style" signal selector with suffix and regex support.
* **State Persistence & Sharing:** Every view is captured in a shareable, compressed URL by pasting a link to share your exact configuration.
* **Pro-Grade Tooling:** Built-in JSON configuration editor, drag-and-drop config restoration, and multi-format exports (SVG, PNG, CSV).
* **Keyboard-First Design:** Full hotkey support for warping between trials and managing views without leaving the home row.

### Reloaded

A rapid prototyping loop that allows you to modify physics logic and model architecture on the fly without ever closing the visualizer.

* **Module Hot-Reloading:** Recursively reloads local Python modules and MJCF logic, allowing code changes to propagate instantly to the active simulation.
* **Unified Visualizer Bridge:** Synchronized visualization of custom force and torque vectors across native OpenGL, Viser web interfaces, and video recordings.
* **Interactive Prototyping:** A developer-centric command loop to toggle playback speeds, repeat last commands, or trigger "generation-only" mode for rapid MJCF debugging.
* **Asset Persistence:** Automatically dumps current MJCF snapshots and model configurations to a workspace directory for post-hoc analysis or version tracking.

> [!TIP]
> ```bash
> mujoco-mojo reloaded \
>     --generator monte_carlo_test.Experiment.generate \
>     --runtime monte_carlo_test.runtime \
> ```

---

> [!NOTE]
> **MuJoCo Mojo** is an independently developed open-source toolbox. It is **not** affiliated with, sponsored by, or endorsed by **Google DeepMind** or the official **MuJoCo** development team.
> MuJoCo® is a registered trademark of Google LLC. All MJCF schemas and MuJoCo-related terminology used within this project are for compatibility and documentation purposes only.
