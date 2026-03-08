# MuJoCo Mojo

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/dark-logo.png">
    <img alt="MuJoCo Mojo" src="docs/assets/light-logo.png" width="320">
  </picture>
</p>

A **Pythonic MJCF generation and validation toolkit** for MuJoCo, built on **Pydantic v2**.

MuJoCo Mojo lets you construct MJCF models using **typed Python objects** instead of handwritten XML, with:

* Static typing
* Runtime validation
* Programmatic composition of complex models

> [Documentation](https://hydrowelder.github.io/mujoco-mojo/)

## Installation
Install using `uv` (recommended):

```bash
uv add mujoco-mojo
```

or with `pip`:

```
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
* Flexible commandline utilities to run jobs

> [!TIP]
> ```bash
> mujoco-mojo run monte-carlo \
>     --generator monte_carlo_test.Experiment.generate \
>     --runtime monte_carlo_test.runtime \
>     --workdir ./mc_test/ \
>     --no-resume \
>     --gen-arg 123 \
>     --gen-kwarg 'test=1234' \
>     --n-trial 10 \
>     --n-proc 1
> ```

* Lightweight browser-based dashboard tool for runtime monitoring with system/light/darkmode which works with or without an internet connection
* Built in Rich logging for terminal and a rotating file handler for persistant logs
