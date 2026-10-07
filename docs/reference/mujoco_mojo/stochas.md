# mujoco\_mojo.stochas

The `mujoco_mojo.stochas` subpackage re-exports the distributions, named values, design values, and unit system from the [stochas](https://github.com/Hydrowelder/stochas) library, which handles the stochastic parameterization of MuJoCo Mojo models. The best reference is the stochas documentation:

[stochas API Reference :material-open-in-new:](https://hydrowelder.github.io/stochas/reference/stochas/){ .md-button .md-button--primary target=_blank }

All of these types are re-exported from the top-level `mujoco_mojo` namespace,
so you rarely need to import directly from `mujoco_mojo.stochas` or `stochas`.

```python
import mujoco_mojo as mojo

mass = mojo.NormalDistribution(name=mojo.DistName("link_mass"), mu=1.5, sigma=0.15)
```
