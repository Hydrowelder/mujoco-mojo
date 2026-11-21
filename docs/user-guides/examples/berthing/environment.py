"""The environment: a dark gradient sky and the sun."""

from __future__ import annotations

from typing import Self

import numpy as np

import mujoco_mojo as mojo


# --8<-- [start:environment]
class Environment(mojo.UserData):
    """The sky behind everything and the sun that lights it."""

    sky: mojo.TextureBuiltIn
    """The skybox texture, a gradient from `SKY_TOP` to `SKY_BOTTOM`."""

    sun: mojo.Light
    """The sun, a directional light, so its rays are parallel and its position does not matter."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel) -> Self:
        assert mojo_model.mjcf.worldbody  # for type hinting

        # a skybox is picked up by the viewer on its own, without anything referring to it by name
        sky = mojo.TextureBuiltIn(
            name=mojo.TextureName("sky"),
            type=mojo.TextureType.SKYBOX,
            builtin=mojo.TextureBuiltInType.GRADIENT,
            width=16,
            height=16,
            rgb1=mojo.utils.Color.SLATE_700.rgb,
            rgb2=mojo.utils.Color.SLATE_950.rgb,
        )
        mojo_model.mjcf.assets.append(mojo.Asset(textures=[sky]))

        sun = mojo.Light(
            name=mojo.LightName("sun"),
            type=mojo.LightType.DIRECTIONAL,
            dir=np.array((-0.4, 0.4, -0.8)),
        )
        mojo_model.mjcf.worldbody.lights.append(sun)

        return cls(sky=sky, sun=sun)


# --8<-- [end:environment]
