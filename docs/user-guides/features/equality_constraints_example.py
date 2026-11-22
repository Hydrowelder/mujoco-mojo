"""A ball caught on a hook and then let go, for the Equality Constraints guide. Run this file to remake the guide's video."""

import tempfile
from pathlib import Path

# --8<-- [start:example]
import numpy as np

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt


class Scene(mojo.UserData):
    """The weld and the two sites it joins, so the runtime can find them."""

    weld: mojo.EqualityWeldSite
    ball_site: mojo.SiteSphere
    hook_site: mojo.SiteSphere


# --8<-- [start:model]
def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """A ball above a fixed hook, and a weld that can catch the ball on the hook."""
    worldbody = mojo_model.mjcf.worldbody = mojo.WorldBody()

    hook_site = mojo.SiteSphere(
        name=mojo.SiteName("hook"),
        size=0.03,
        rgba=mojo.utils.Color.GREEN_500.rgba,
        pose=mojo.PoseQuat(pos=np.array((0, 0, 1))),
    )
    worldbody.sites.append(hook_site)

    ball_site = mojo.SiteSphere(name=mojo.SiteName("ball_site"), size=0.02)
    worldbody.bodies.append(
        mojo.Body(
            name=mojo.BodyName("ball"),
            pose=mojo.PoseQuat(pos=np.array((0, 0, 1.5))),
            geoms=[
                mojo.GeomSphere(size=0.1, mass=1, rgba=mojo.utils.Color.RED_500.rgba)
            ],
            sites=[ball_site],
            freejoints=[mojo.FreeJoint()],
        )
    )

    # --8<-- [start:weld]
    assert ball_site.name
    assert hook_site.name
    weld = mojo.EqualityWeldSite(
        name=mojo.EqualityName("catch"),
        site1=ball_site.name,
        site2=hook_site.name,
        # off, so the ball falls freely until the runtime switches it on
        active=False,
    )
    mojo_model.mjcf.equalities.append(mojo.Equality(welds=[weld]))
    # --8<-- [end:weld]

    mojo_model.user_data = Scene(weld=weld, ball_site=ball_site, hook_site=hook_site)
    return mojo_model


# --8<-- [end:model]


def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    with runtime_manager as rm:
        scene = mojo_model.get_user_data(Scene)

        def gap(state: mojo.MjState) -> float:
            return float(
                np.linalg.norm(
                    scene.ball_site.rt_pos(state) - scene.hook_site.rt_pos(state)
                )
            )

        # --8<-- [start:switch]
        # on only once the ball is close, so the weld has almost nothing to pull in
        while gap(state) > 0.05:
            rm.step(state)
        scene.weld.enable(state)

        caught_at = state.data.time
        while state.data.time < caught_at + 0.5:
            rm.step(state)
        held = scene.weld.is_active(state)
        scene.weld.disable(state)
        # --8<-- [end:switch]

        released_at = state.data.time
        while state.data.time < released_at + 0.3:
            rm.step(state)

        print(held, gap(state))

    return mojo_model


# --8<-- [end:example]


def record_clip(path: Path) -> None:
    """Films the example from the side at half speed, with a label that says whether the weld is on, and saves it to `path`."""

    def generate_with_camera(
        mojo_model: mojo.MojoModel, *args, **kwargs
    ) -> mojo.MojoModel:
        mojo_model = generate(mojo_model, *args, **kwargs)
        assert mojo_model.mjcf.worldbody

        # look_at leaves the picture turned a quarter turn, so the roll turns it back upright
        mojo_model.mjcf.worldbody.cameras.append(
            mojo.Camera(
                name=mojo.CameraName("side"),
                fovy=40,
                pose=mojo.PoseQuat.look_at(
                    target=np.array((0, 0, 1)),
                    eye=np.array((0, -3, 1)),
                    roll=-90,
                ),
            )
        )
        return mojo_model

    def runtime_with_video(
        mojo_model: mojo.MojoModel,
        runtime_manager: rt.RuntimeManager,
        state: mojo.MjState,
        *args,
        **kwargs,
    ) -> mojo.MojoModel:
        scene = mojo_model.get_user_data(Scene)

        def label(state: mojo.MjState) -> rt.LabelConfig:
            weld = "on" if scene.weld.is_active(state) else "off"
            return {
                "text": f"t = {state.data.time:.2f} s   weld {weld}",
                "background_color": mojo.utils.Color.SLATE_900.with_alpha(0.7),
            }

        # registered here because the example's runtime opens the `with` block itself
        rt.VideoRecorder(
            path=path,
            camera_name=mojo.CameraName("side"),
            frame_rate=60,
            playback_speed=0.5,
            frame_label=label,
        ).setup(state).register_to_rm(runtime_manager)
        return runtime(mojo_model, runtime_manager, state, *args, **kwargs)

    with tempfile.TemporaryDirectory() as workdir:
        mojo.utils.MojoRunner(
            generator=generate_with_camera,
            runtime=runtime_with_video,
            workdir=Path(workdir) / "run",
            config=mojo.utils.MonteCarloConfig(n_trial=1, n_proc=1, resume=False),
        ).run()


if __name__ == "__main__":
    record_clip(Path(__file__).with_name("equality-constraints.mp4"))
