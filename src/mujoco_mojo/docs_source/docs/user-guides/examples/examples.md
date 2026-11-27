# Examples

!!! abstract

    The following are collections of models you can use to help familiarize yourself with in addition to the [example workflow](../workflow/getting-started.md) discussed previously. Examples provided show other ways Mojo can be used to enrich your analysis and design by providing a flexible way to define MJCF models.

    If you have good example models to share, please don't hesitate to reach out or [open a pull request](https://github.com/Hydrowelder/mujoco-mojo/compare){target:"_blank"} with a guide showing how you built your model!

---

## Running the Examples

Every example in these guides ships with Mojo, in the `mujoco_mojo.examples` package:

| Name                             | Model                                                                                       | Guide                                                    |
| :------------------------------- | :------------------------------------------------------------------------------------------ | :------------------------------------------------------- |
| `vlr`                            | A rocket that falls and lands on four spring-damped legs.                                   | [Vertically Landed Rocket](vlr/introduction.md)          |
| `berthing`                       | A seven-joint robotic arm that grabs a visiting vehicle and berths it to a station.         | [Berthing](berthing/introduction.md)                     |
| `boxes-and-springs`              | Two boxes joined by springs, with randomized inputs for a Monte Carlo study.                | [Generate Script](../workflow/generate-script.md)        |
| `boxes-and-springs-optimization` | Two boxes joined by springs, with an objective to tune them in an optimization study.       | [Optimization](../features/optimization/optimization.md) |
| `tennis-racket`                  | A racket spun about its middle axis, which flips over and over (the tennis racket theorem). | [Tennis Racket Theorem](tennis-racket/tennis-racket.md)  |

Open one in [Reloaded](../features/reloaded/reloaded.md) by its name:

``` bash linenums="0"
mujoco-mojo examples run vlr
```

The first line of Reloaded's log is the path to the example's code, which the terminal of an editor such as VS Code opens with Ctrl+click. The trials are written to `mojo-examples/<name>` in the folder you run from (`--workdir` picks another). [`mujoco-mojo examples list`](../../reference/cli.md#mujoco-mojo-examples-list) lists the examples.

The examples build their models from MuJoCo's built-in textures and Mojo's generated meshes, so they need no files beyond the package and run offline. The berthing example uses [`mink`](https://kevinzakka.github.io/mink/), which comes with the `examples` extra:

``` bash linenums="0"
pip install "mujoco-mojo[examples]"
```

Each example is a folder of its own, whose `simulation.py` has a `generate` and a `runtime` function, so every other command takes it by its import path, the same as a model of your own. For example, a Monte Carlo of ten trials of the boxes and springs:

``` bash linenums="0"
mujoco-mojo run monte-carlo \
    -g mujoco_mojo.examples.boxes_and_springs.simulation.generate \
    -r mujoco_mojo.examples.boxes_and_springs.simulation.runtime \
    -nt 10
```
