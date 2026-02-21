from __future__ import annotations

from mujoco_mojo.mjcf.xml_model import XMLModel

__all__ = ["SpatialPulley"]


class SpatialPulley(XMLModel):
    """This element starts a new branch in the tendon path. The branches are not required to be connected spatially. Similar to the transmissions described in the Actuation model section of the Computation chapter, the quantity that affects the simulation is the tendon length and its gradient with respect to the joint positions. If a spatial tendon has multiple branches, the length of each branch is divided by the divisor attribute of the pulley element that started the branch, and added up to obtain the overall tendon length. This is why the spatial relations among branches are not relevant to the simulation. The tendon.xml example above illustrated the use of pulleys."""

    tag = "pulley"

    attributes = ("divisor",)

    divisor: float
    """The length of the tendon branch started by the pulley element is divided by the value specified here. For a physical pulley that splits a single branch into two parallel branches, the common branch would have divisor value of 1 and the two branches following the pulley would have divisor values of 2. If one of them is further split by another pulley, each new branch would have divisor value of 4 and so on. Note that in MJCF each branch starts with a pulley, thus a single physical pulley is modeled with two MJCF pulleys. If no pulley elements are included in the tendon path, the first and only branch has divisor value of 1."""
