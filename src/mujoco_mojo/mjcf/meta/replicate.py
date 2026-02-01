"""
!!! failure "Not Implemented"
    The Replicate class is not implemented. There is no plan to implement as its functionality is duplicated by that of Python itself. Its functionality within the Mujoco class is not implemented.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
from pydantic import Field, PositiveInt

from mujoco_mojo.base import XMLModel
from mujoco_mojo.mjcf.orientation import Euler
from mujoco_mojo.typing import Vec3
from mujoco_mojo.utils import is_empty_list

raise NotImplementedError(
    "The Replicate class is not implemented. There is no plan to implement as its functionality is duplicated by that of Python itself."
)

__all__ = ["Replicate"]


class Replicate(XMLModel):
    """The replicate element duplicates the enclosed kinematic tree elements with incremental translational and rotational offsets, adding namespace suffixes to avoid name collisions. Appended suffix strings are integers in the range [0...count-1] with the minimum number of digits required to represent the total element count (i.e., if replicating 200 times, suffixes will be 000, 001, ... etc). All referencing elements are automatically replicated and namespaced appropriately. Detailed examples of models using replicate can be found in the model/replicate/ directory.

    There are some caveats concerning keyframes when using replicate. Since mjs_attach is used to self-attach multiple times the enclosed kinematic tree, if this tree contains further attach elements, keyframes will not be replicated nor namespaced by replicate, but they will be attached and namespaced once by the innermost call of mjs_attach. See the limitations discussed in attachment.

    ???+ example "Example Usage of Replicate"

        Compiling this model:
        ```xml hl_lines="3-4 6-7"
        <mujoco>
            <worldbody>
                <replicate count="2" offset="0 1 0" euler="90 0 0">
                    <replicate count="2" sep="-" offset="1 0 0" euler="0 90 0">
                        <geom name="Alice" size=".1"/>
                    </replicate>
                </replicate>
            </worldbody>

            <sensor>
                <accelerometer name="Bob" site="Alice"/>
            </sensor>
        </mujoco>
        ```

        Results in this model:
        ```xml
        <mujoco>
            <worldbody>
                <geom name="Alice-00" size="0.1"/>
                <geom name="Alice-10" size="0.1" pos="1 0 0" quat="1 0 1 0"/>
                <geom name="Alice-01" size="0.1" pos="0 1 0" quat="1 1 0 0"/>
                <geom name="Alice-11" size="0.1" pos="1 1 0" quat="0.5 0.5 0.5 0.5"/>
            </worldbody>

            <sensor>
                <accelerometer name="Bob-00" site="Alice-00"/>
                <accelerometer name="Bob-10" site="Alice-10"/>
                <accelerometer name="Bob-01" site="Alice-01"/>
                <accelerometer name="Bob-11" site="Alice-11"/>
            </sensor>
        </mujoco>
        ```
    """

    tag = "replicate"

    attributes = ("count", "childclass", "pos", "orientation")
    children = ("replicatations",)

    count: PositiveInt
    """The number of replicas. Must be positive."""

    sep: Optional[str] = None
    """The namespace separator. This optional string is prepended to the namespace suffix string. Note that for nested replicate elements, the innermost namespace suffixes are appended first."""

    pos: Vec3 = np.array((0, 0, 0))
    """Translational offset along the three coordinate axes. In general, the frame of the offset is with respect to the previous replica, except for the first one which is with respect to the replicate element's parent. If there is no rotation, these values are always in the frame of the replicate element's parent."""

    orientation: Euler = Euler()
    """Rotation angles around three coordinate axes between two subsequent replicas. The angular units and rotation sequence respect the global angle and eulerseq settings. Rotation is always with respect to the frame of the previous replica, so total rotation is cumulative."""

    replications: Sequence[Replicate] = Field(
        default_factory=list, exclude_if=is_empty_list
    )
    """Replications assigned to Replicate."""
