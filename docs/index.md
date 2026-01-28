# MuJoCo Mojo

Pythonic MJCF generation and validation toolkit built on Pydantic v2.

## Features

- Typed MJCF models
- Compile-time XML validation
- NumPy vector support
- Automatic XML serialization
- MuJoCo compatible schema

## Quick Example

```python
from mujoco_mojo import Material

mat = Material(name="steel")
print(mat.to_xml())
```
