# MuJoCo Mojo

A **Pythonic MJCF generation and validation toolkit** for MuJoCo, built on **Pydantic v2**.

MuJoCo Mojo lets you construct MJCF models using **typed Python objects** instead of handwritten XML, with:

* Static typing
* Runtime validation
* Programmatic composition of complex models

## Features

### MJCF Tools
* Strongly-typed MJCF elements backed by Pydantic v2
* Early validation of MJCF structure and attribute semantics
* Pythonic composition of assets, bodies, sensors, and plugins
* Designed to mirror MuJoCo’s XML schema closely (no magic abstractions)
* Suitable for code generation, tooling, and large model pipelines

### Job Utilities
* Single or multi-threaded trial execution
* Random draw tools for Monte Carlo or rerun with global variable override
* Detailed status files for insight on trial progress
* Resume a previously started job without rerunning previous cases
* Automatically record installed Python packages to `requirements.txt` for job recreation (works with `uv` or `pip`)
* End of run summary with metric to help perform a state of health check
* *SOON*: dashboard tool for runtime monitoring

## Installation
=== "`uv` (recommended)"

    ```bash
    uv add mujoco-mojo
    ```

=== "`pip`"

    ```
    pip install mujoco-mojo
    ```

!!! warning
    At the time of writing, MuJoCo supports up to Python 3.13
