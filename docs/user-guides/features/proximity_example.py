"""Two cylinders and the distance between them, for the Proximity guide. Run this file to remake the guide's video."""

import tempfile
from pathlib import Path

# --8<-- [start:example]
import numpy as np

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt


class Cylinders(mojo.UserData):
    """The two cylinders, so the runtime can find them."""

    target: mojo.GeomMesh
    probe: mojo.GeomMesh
    probe_body: mojo.Body


# --8<-- [start:model]
def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """A cylinder fixed in place, and an identical one free to drift toward it."""
    mojo_model.mjcf.worldbody = mojo.WorldBody()

    # a builtin mesh, which MuJoCo generates when it compiles the model: 0.2 m across and 0.4 m long
    mesh = mojo.MeshCylinder(
        name=mojo.MeshName("cylinder"),
        count=(9, 9, 9),
        spacing=np.array((0.025, 0.025, 0.05)),
    )
    mojo_model.mjcf.assets.append(mojo.Asset(meshes=[mesh]))
    assert mesh.name

    target = mojo.GeomMesh(name=mojo.GeomName("target"), mesh=mesh.name, mass=1)
    probe = mojo.GeomMesh(name=mojo.GeomName("probe"), mesh=mesh.name, mass=1)
    probe_body = mojo.Body(
        name=mojo.BodyName("probe"),
        geoms=[probe],
        freejoints=[mojo.FreeJoint()],
    )
    mojo_model.mjcf.worldbody.bodies.extend(
        [
            mojo.Body(
                name=mojo.BodyName("target"),
                pose=mojo.PoseQuat(pos=np.array((1.5, 0, 0))),
                geoms=[target],
            ),
            probe_body,
        ]
    )
    mojo_model.user_data = Cylinders(target=target, probe=probe, probe_body=probe_body)

    mojo_model.mjcf.options.append(
        mojo.Option(gravity=np.array((0, 0, 0)))  # nothing pulls the probe off its line
    )
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
        cylinders = mojo_model.get_user_data(Cylinders)

        # --8<-- [start:pair]
        proximity = mojo.utils.Proximity(
            volume_1=cylinders.probe, volume_2=cylinders.target, dist_max=0.4
        ).register_to_rm()
        proximity.request(channels=["dist", "fromto", "prox_type"])
        # --8<-- [end:pair]

        # set the initial velocity (qvel) of a free-joint body: the probe drifts toward the target at 0.8 m/s and spins, so the nearest points move around the surfaces
        cylinders.probe_body.set_initial_velocity(
            state,
            linear_velocity=np.array((0.8, 0, 0)),
            angular_velocity=np.array((0, 10, 0)),
        )
        while state.data.time < 1.4:
            rm.step(state)

        # --8<-- [start:read]
        distance, probe_point, target_point, algorithm = proximity.get_proximity(state)
        # --8<-- [end:read]

        # --8<-- [start:stop]
        proximity.active = False
        # --8<-- [end:stop]
        print(distance, probe_point, target_point, algorithm.name)

    return mojo_model


# --8<-- [end:example]


def record_clip(path: Path) -> None:
    """Films the example from the side at half speed, with the proximity line and a distance label, and saves it to `path`."""

    def generate_with_camera(
        mojo_model: mojo.MojoModel, *args, **kwargs
    ) -> mojo.MojoModel:
        mojo_model = generate(mojo_model, *args, **kwargs)
        assert mojo_model.mjcf.worldbody

        # from a little above, so the cylinders' top faces and the line between them show
        mojo_model.mjcf.worldbody.cameras.append(
            mojo.Camera(
                name=mojo.CameraName("side"),
                fovy=30,
                pose=mojo.PoseQuat.look_at(
                    target=np.array((0.75, 0, 0)),
                    eye=np.array((0.75, -2.8, 1.5)),
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
        runtime_manager.set_playback_speed(0)
        with runtime_manager as rm:
            cylinders = mojo_model.get_user_data(Cylinders)
            proximity = mojo.utils.Proximity(
                volume_1=cylinders.probe, volume_2=cylinders.target, dist_max=0.4
            ).register_to_rm()

            def label(state: mojo.MjState) -> rt.LabelConfig:
                distance, _, _, algorithm = proximity.get_proximity(state)
                return {
                    "text": f"distance = {distance:.2f} m   {algorithm.name}",
                    "background_color": mojo.utils.Color.SLATE_900.with_alpha(0.7),
                }

            # frames are taken in simulation time, so half the playback speed is slow motion
            rt.VideoRecorder(
                path=path,
                camera_name=mojo.CameraName("side"),
                frame_rate=60,
                playback_speed=0.5,
                show_proximities=True,
                frame_label=label,
            ).setup(state).register_to_rm()

            cylinders.probe_body.set_initial_velocity(
                state,
                linear_velocity=np.array((0.8, 0, 0)),
                angular_velocity=np.array((0, 10, 0)),
            )
            while state.data.time < 1.4:
                rm.step(state)
        return mojo_model

    with tempfile.TemporaryDirectory() as workdir:
        mojo.utils.MojoRunner(
            generator=generate_with_camera,
            runtime=runtime_with_video,
            workdir=Path(workdir) / "run",
            config=mojo.utils.MonteCarloConfig(n_trial=1, n_proc=1, resume=False),
        ).run()


if __name__ == "__main__":
    record_clip(Path(__file__).with_name("proximity.mp4"))
