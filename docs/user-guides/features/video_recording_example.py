"""A ball dropped onto a floor and filmed, for the Video Recording guide. Run this file to remake the guide's video."""

import shutil
import tempfile
from pathlib import Path

# --8<-- [start:example]
import numpy as np

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt


class Scene(mojo.UserData):
    """The ball and the camera that films it, so the runtime can find them."""

    ball: mojo.Body
    camera: mojo.Camera


# --8<-- [start:model]
def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """A ball above a wedge, with a camera beside its path and a spotlight overhead."""
    assert mojo_model.mjcf.worldbody is None
    worldbody = mojo_model.mjcf.worldbody = mojo.WorldBody()

    # springy contacts, so the ball bounces
    springy = np.array((0.02, 0.1))

    ball = mojo.Body(
        name=mojo.BodyName("ball"),
        pose=mojo.PoseQuat(pos=np.array((0, 0, 1.5))),
        geoms=[
            mojo.GeomSphere(
                size=0.1,
                mass=1,
                rgba=mojo.utils.Color.RED_500.rgba,
                solref=springy,
            )
        ],
        freejoints=[mojo.FreeJoint()],
    )
    worldbody.bodies.append(ball)
    worldbody.geoms.append(mojo.GeomPlane(size=np.array((0, 0, 0.1)), solref=springy))

    # tilted so the ball bounces off sideways
    wedge = mojo.GeomBox(
        size=np.array((0.4, 0.4, 0.2)),
        pose=mojo.PoseEuler(euler=np.array((0, 10, 0))),
        rgba=mojo.utils.Color.SLATE_400.rgba,
        solref=springy,
    )
    worldbody.geoms.append(wedge)

    # look_at leaves the picture turned a quarter turn, so the roll turns it back upright
    camera = mojo.Camera(
        name=mojo.CameraName("side"),
        pose=mojo.PoseQuat.look_at(
            target=np.array((0.85, 0, 0.4)),
            eye=np.array((0.85, -3.2, 0.5)),
            roll=-90,
        ),
        fovy=40,
    )
    worldbody.cameras.append(camera)

    # overhead, so the ball casts a shadow on the floor
    worldbody.lights.append(
        mojo.Light(
            name=mojo.LightName("spot"),
            type=mojo.LightType.SPOT,
            pos=mojo.Pos(np.array((1, 0, 3))),
            dir=np.array((0, 0, -1)),
            cutoff=30,
        )
    )

    # --8<-- [start:offscreen]
    # room for a recorder larger than the default 640 by 480
    mojo_model.mjcf.visuals.append(
        mojo.Visual(global_=mojo.VisualGlobal(offwidth=1280, offheight=720))
    )
    # --8<-- [end:offscreen]

    mojo_model.user_data = Scene(ball=ball, camera=camera)
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
        assert scene.camera.name

        def height(state: mojo.MjState) -> float:
            return float(scene.ball.rt_pos(state)[2])

        # --8<-- [start:functions]
        # latched, since a trigger that followed the height would skip the top of each bounce
        started = False

        def near_floor(state: mojo.MjState) -> bool:
            nonlocal started
            started = started or height(state) < 0.6
            return started

        def label(state: mojo.MjState) -> rt.LabelConfig:
            return {
                "text": f"t = {state.data.time:.2f} s   height = {height(state):.2f} m"
            }

        # --8<-- [end:functions]

        # only the first trial films, since every frame costs time
        if mojo_model.is_nominal:
            # --8<-- [start:tracer]
            rt.Tracer(
                target=scene.ball,
                duration=1.0,
                width=1,
                color=mojo.utils.Color.WHITE.rgba,
            ).register_to_rm()
            # --8<-- [end:tracer]

            # --8<-- [start:mp4]
            mp4 = (
                rt.VideoRecorder(
                    path=mojo_model.trial_dir / "ball.mp4",
                    camera_name=scene.camera.name,
                    frame_rate=60,
                    playback_speed=0.5,
                    show_traces=True,
                    recording_trigger=near_floor,
                    frame_label=label,
                )
                .setup(state)
                .register_to_rm()
            )
            # --8<-- [end:mp4]

            # --8<-- [start:webm]
            webm = (
                rt.VideoRecorder(
                    path=mojo_model.trial_dir / "ball.webm",
                    camera_name=scene.camera.name,
                    frame_rate=60,
                    playback_speed=0.5,
                    show_traces=True,
                    recording_trigger=near_floor,
                    frame_label=label,
                )
                .setup(state)
                .register_to_rm()
            )
            # --8<-- [end:webm]

            # --8<-- [start:gif]
            gif = (
                rt.VideoRecorder(
                    path=mojo_model.trial_dir / "ball.gif",
                    camera_name=scene.camera.name,
                    frame_rate=60,
                    playback_speed=0.5,
                    show_traces=True,
                    recording_trigger=near_floor,
                    frame_label=label,
                )
                .setup(state)
                .register_to_rm()
            )
            # --8<-- [end:gif]

            # only the mp4 should record, so the others come out again
            print(f"mp4 has renderer: {mp4._renderer is not None}")
            webm.unregister_from_rm()
            gif.unregister_from_rm()

        while state.data.time < 2.0:
            rm.step(state)

    return mojo_model


# --8<-- [end:example]


def record_clip(path: Path) -> None:
    """Runs the example and copies the MP4 it recorded to `path`."""
    with tempfile.TemporaryDirectory() as workdir:
        mojo.utils.MojoRunner(
            generator=generate,
            runtime=runtime,
            workdir=Path(workdir) / "run",
            config=mojo.utils.MonteCarloConfig(n_trial=1, n_proc=1, resume=False),
        ).run()
        shutil.copy(Path(workdir) / "run" / "trials" / "trial_0" / "ball.mp4", path)


if __name__ == "__main__":
    record_clip(Path(__file__).with_name("video-recording.mp4"))
