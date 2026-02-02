# MuJoCo Mojo

Pythonic MJCF generation and validation toolkit built on Pydantic v2. It is built for Python 3.13 and above.

## Features

- Typed MJCF models
- Compile-time XML validation
- NumPy vector support
- Automatic XML serialization
- MuJoCo compatible schema

## Quick Example

```python
import mujoco_mojo.mjcf as mjcf

mat = mjcf.Material(name="steel")
print(mat.to_xml())
```
