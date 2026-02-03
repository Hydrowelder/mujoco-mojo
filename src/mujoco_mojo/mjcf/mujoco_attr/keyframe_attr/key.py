from mujoco_mojo.base import XMLModel
from mujoco_mojo.typing import KeyName, VecN


class Key(XMLModel):
    """This element sets the data for one of the keyframes. They are set in the order in which they appear here. If the number of elements specified in the given vectors is less than the size of the corresponding mjData array, missing entries will be set to their values in the default configuration."""

    tag = "key"

    attributes = ("name", "time", "qpos", "qvel", "act", "mpos", "mquat", "ctrl")

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
