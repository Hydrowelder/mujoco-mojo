# mujoco\_mojo.mjcf

The `mujoco_mojo.mjcf` subpackage provides the complete Python object model
for the MuJoCo XML schema.  It mirrors the official XML structure closely, so
the best reference is the upstream documentation:

[MuJoCo XML Reference :material-open-in-new:](https://mujoco.readthedocs.io/en/stable/XMLreference.html){ .md-button .md-button--primary target=_blank }

All `mjcf` types are re-exported from the top-level `mujoco_mojo` namespace,
so you rarely need to import directly from `mujoco_mojo.mjcf`.

```python
import mujoco_mojo as mojo

body = mojo.Body(name=mojo.BodyName("my_body"))
```
