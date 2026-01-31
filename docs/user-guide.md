Guide is coming soon...

!!! warning "Default Values"
    Some attributes in this package make use of default values. Wherever possible, the default values match what is stated in the [XML Reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html#xml-reference){:target="_blank"}. The `to_xml` method found in all `XMLModel` (which is most objects in `mujoco_mojo.mjcf`) has an argument (`exclude_defaults`) which will omit serializing fields set as default.

    If you have a specific use case which is dependent on a value you leave as default, it is highly recommended that you pin that value as opposed to use the default. MuJoCo may change their defaults, and this package may fall behind. In that case, you would be using a "default" which is no longer the default.
