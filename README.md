# MuJoCo Mojo

A **Pythonic MJCF generation and validation toolkit** for MuJoCo, built on **Pydantic v2**.

MuJoCo Mojo lets you construct MJCF models using **typed Python objects** instead of handwritten XML, with:

* Static typing
* Runtime validation
* Programmatic composition of complex models

> [Documentation](https://hydrowelder.github.io/mujoco-mojo/)

## Features

* Strongly-typed MJCF elements backed by Pydantic v2
* Early validation of MJCF structure and attribute semantics
* Pythonic composition of assets, bodies, sensors, and plugins
* Designed to mirror MuJoCo’s XML schema closely (no magic abstractions)
* Suitable for code generation, tooling, and large model pipelines

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
