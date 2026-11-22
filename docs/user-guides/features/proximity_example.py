"""Two cylinders and the distance between them, for the Proximity guide."""

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

    # a builtin mesh, which MuJoCo generates when it compiles the model: 0.2 m across and 1 m long
    mesh = mojo.MeshCylinder(
        name=mojo.MeshName("cylinder"),
        count=(9, 9, 9),
        spacing=np.array((0.025, 0.025, 0.125)),
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
                pose=mojo.PoseQuat(pos=np.array((1, 0, 0))),
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
            volume_1=cylinders.probe, volume_2=cylinders.target, dist_max=2.0
        ).register_to_rm()
        proximity.request(channels=["dist", "fromto"])
        # --8<-- [end:pair]

        # set the initial velocity (qvel) of a free-joint body so the probe drifts toward the target at 0.5 m/s
        cylinders.probe_body.set_initial_velocity(
            state, linear_velocity=np.array((0.5, 0, 0))
        )
        while state.data.time < 1.0:
            rm.step(state)

        # --8<-- [start:read]
        distance, probe_point, target_point, algorithm = proximity.get_proximity(state)
        # --8<-- [end:read]
        print(distance, probe_point, target_point, algorithm.name)

    return mojo_model
