import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

logger = mojo.utils.get_logger(__name__)


class UserData(mojo.UserData):
    """Pass state from generate() to runtime()."""

    pass


def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    user_data = UserData()
    mojo_model.mjcf.worldbody = mojo.WorldBody()
    mojo_model.user_data = user_data
    return mojo_model


def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    _user_data = mojo_model.get_user_data(UserData)

    with runtime_manager as rm:
        while state.data.time < 1.0:
            rm.step(state)

    return mojo_model


def objective(mojo_model: mojo.MojoModel, *args, **kwargs) -> float:
    """Return a scalar score for the optimizer to minimize or maximize."""
    return 0.0
