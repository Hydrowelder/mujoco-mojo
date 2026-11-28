from typing import ClassVar, Self

import mujoco
import numpy as np
from pydantic import Field, model_validator

from mujoco_mojo.mj_state import MjState
from mujoco_mojo.mjcf.mujoco_attr.keyframe_attr.key_state import AnyKeyState, KeyVector
from mujoco_mojo.mjcf.xml_model import XMLModel
from mujoco_mojo.typing import KeyName, VecN
from mujoco_mojo.utils.log import get_logger
from mujoco_mojo.utils.utils import is_empty_list

logger = get_logger(__name__)

_DATA_FIELDS: dict[KeyVector, str] = {
    "qpos": "qpos",
    "qvel": "qvel",
    "act": "act",
    "ctrl": "ctrl",
    "mpos": "mocap_pos",
    "mquat": "mocap_quat",
}
"""Each key vector's field in `MjData`, in the order MuJoCo lists them."""


class Key(XMLModel):
    """
    This element sets the data for one of the keyframes. They are set in the order in which they appear here. If the number of elements specified in the given vectors is less than the size of the corresponding mjData array, missing entries will be set to their values in the default configuration.

    Rather than writing the vectors by hand, which means knowing where each joint, actuator, or mocap body sits in them, list what to set in `states` and Mojo works the vectors out from the compiled model.

    ???+ example "Example Usage of Key States"

        ```python
        mojo.Key(
            name=mojo.KeyName("kicked"),
            initial=True,
            states=[
                mojo.JointState(joint=elbow.name, qpos=-0.6, qvel=5.0),
                mojo.FreeBodyState(body=racket.name, angular_velocity=np.array((0.1, 4.0, 0))),
                mojo.ActuatorState(actuator=motor.name, ctrl=1.0),
            ],
        )
        ```
    """

    tag = "key"

    attributes = (
        "name",
        "time",
        "qpos",
        "qvel",
        "act",
        "mpos",
        "mquat",
        "ctrl",
        "plastic",
    )

    # neither is an MJCF attribute: `states` is written as the vectors it gives once the model is compiled, and `initial` is read by `Mujoco.prep_for_sim`
    non_xml_fields = ("states", "initial")

    _mjt_obj: ClassVar[mujoco.mjtObj | None] = mujoco.mjtObj.mjOBJ_KEY

    name: KeyName | None = None
    """Name of this keyframe."""

    time: float = 0
    """Simulation time, copied into mjData.time when the simulation state is set to this keyframe."""

    qpos: VecN | None = None
    """Vector of joint positions, copied into mjData.qpos when the simulation state is set to this keyframe."""

    qvel: VecN | None = None
    """Vector of joint velocities, copied into mjData.qvel when the simulation state is set to this keyframe."""

    act: VecN | None = None
    """Vector of actuator activations, copied into mjData.act when the simulation state is set to this keyframe."""

    ctrl: VecN | None = None
    """Vector of controls, copied into mjData.ctrl when the simulation state is set to this keyframe."""

    mpos: VecN | None = None
    """Vector of mocap body positions, copied into mjData.mocap_pos when the simulation state is set to this keyframe."""

    mquat: VecN | None = None
    """Vector of mocap body quaternions, copied into mjData.mocap_quat when the simulation state is set to this keyframe."""

    plastic: VecN | None = None
    """Vector of plastic states, copied into mjData.plastic when the simulation state is set to this keyframe."""

    states: list[AnyKeyState] = Field(
        default_factory=list,
        exclude_if=is_empty_list,
    )
    """
    What this key sets, by reference: the position and velocity of joints and free bodies, the control and activation of actuators, and the pose of mocap bodies. Everything not listed keeps the model's default.

    When the model is written or compiled, these are turned into the `qpos`, `qvel`, `act`, `ctrl`, `mpos`, and `mquat` vectors, so a key with states cannot also set those vectors directly. The XML holds the vectors, so reading it back gives a key with vectors and no states.
    """

    initial: bool = False
    """Whether the simulation starts from this key. `Mujoco.prep_for_sim`, which the runner and Reloaded use to start a simulation, loads it after compiling. At most one key in a model can be initial."""

    @model_validator(mode="after")
    def check_states(self) -> Self:
        """Refuses a key that sets vectors both through `states` and directly, and a key with states or `initial` but no name, since Mojo finds it in the compiled model by name."""
        if self.states:
            direct = [v for v in _DATA_FIELDS if getattr(self, v) is not None]
            if direct:
                msg = f"Key '{self.name}' sets {', '.join(direct)} directly and also has states. Set them through states only."
                logger.error(msg)
                raise ValueError(msg)

        if (self.states or self.initial) and self.name is None:
            msg = "A key with states or initial=True needs a name."
            logger.error(msg)
            raise ValueError(msg)

        return self

    def resolve(self, model: mujoco.MjModel) -> dict[KeyVector, np.ndarray]:
        """
        Lays this key's `states` out as MuJoCo's state vectors for `model`.

        Each vector starts at the model's default (`qpos0` for positions, zero for velocities, controls, and activations, and the defined pose for mocap bodies) and only the entries of the objects in `states` change. Only the vectors some state fills in are returned, and an empty one (`act` in a model with no activation) is left out.

        Raises:
            ValueError: If two states set the same object, or a state names an object the model does not have or gives it the wrong number of values.

        """
        targets = [s.target for s in self.states]
        if repeated := sorted({t for t in targets if targets.count(t) > 1}):
            msg = f"Key '{self.name}' sets {', '.join(repeated)} more than once."
            logger.error(msg)
            raise ValueError(msg)

        state = MjState(model, mujoco.MjData(model))
        for key_state in self.states:
            key_state.write(state)

        written = {v for s in self.states for v in s.writes}
        vectors: dict[KeyVector, np.ndarray] = {}
        for vector, data_field in _DATA_FIELDS.items():
            if vector not in written:
                continue
            values = np.asarray(getattr(state.data, data_field)).ravel().copy()
            if values.size:
                vectors[vector] = values
        return vectors
