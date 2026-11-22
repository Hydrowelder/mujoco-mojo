"""A fixed camera that follows the visitor."""

from __future__ import annotations

from typing import Self

import numpy as np

import mujoco_mojo as mojo

US = mojo.UnitSystem.si()


# --8<-- [start:inputs]
class OverviewInput(mojo.UserData):
    """Where the overview camera is and how wide it sees."""

    POSITION: tuple[float, float, float] = (2.0 * US.m, -16.0 * US.m, 7.0 * US.m)
    """Where the camera is in the world, as X, Y and Z."""

    FOVY: float = 30
    """Vertical field of view, in degrees."""


OVERVIEW = OverviewInput()
# --8<-- [end:inputs]


# --8<-- [start:overview]
class Overview(mojo.UserData):
    """A camera fixed in the world that turns to keep the visitor's center of mass in view."""

    camera: mojo.Camera
    """The camera. Its `name` is what a video recorder needs."""

    @classmethod
    def new(cls, mojo_model: mojo.MojoModel, target: mojo.Body) -> Self:
        """Makes the camera and puts it in the world, aimed at `target`."""
        assert mojo_model.mjcf.worldbody  # for type hinting
        assert target.name

        # in this mode MuJoCo works out the orientation, so only the position is given
        camera = mojo.Camera(
            name=mojo.CameraName("overview"),
            mode=mojo.TrackingMode.TARGETBODYCOM,
            target=target.name,
            fovy=OVERVIEW.FOVY,
            pose=mojo.PoseQuat(pos=np.array(OVERVIEW.POSITION)),
        )
        mojo_model.mjcf.worldbody.cameras.append(camera)

        return cls(camera=camera)


# --8<-- [end:overview]
