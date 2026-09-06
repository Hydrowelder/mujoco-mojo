# Defining a Ground Surface

!!! abstract

    The rocket needs some ground to collide with, we will be defining a custom class which will contain the key elements needed to configure the ground.

---

## Class Definition

The `Ground` class is (thankfully) pretty straightforward. We define three things:

- **Grid Texture**: A checkerboard texture used on the ground plane. It's technically not needed, but helpful to give things a sense of scale.
- **Material**: To apply a texture to a geometry (like our ground plane) we apply it via a material. This gives options for other photorealistic rendering textures, but we'll stick with the simple built in one for now.
- **Geometry**: A `GeomPlane` (a special built in geometry type) is used to make a contact surface for the rocket. It can be positioned in whatever orientation is needed. We apply our previous contact groups to it to make sure the correct collision pairs are being used (define this body as `GROUND` with valid collisions with the rocket's `TUBE` or `GEAR`).
  - For a more complex model, you could even use a heightmap to simulate an uneven surface!

```python
--8<-- "docs/user-guides/vlr-example/vlr_example.py:ground"
```

---

!!! success

    We have defined a ground plane, its contact behavior, and applied it to our `mojo_model`! We are now ready to begin building the rocket and landing gear assembly.
