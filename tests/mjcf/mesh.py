from pathlib import Path

import numpy as np

import mujoco_mojo as mojo

logger = mojo.utils.get_logger(__name__)


def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Generates two boxes at varying distances."""
    mojo_model.mjcf.assets = [
        mojo.Asset(
            meshes=[
                frustum_mesh := mojo.Mesh.new_frustum(
                    radius_bottom=3,
                    radius_top=1,
                    height=2,
                    sections=10,
                    name=mojo.MeshName("frustum_mesh"),
                ),
                hollow_frustum_mesh := mojo.Mesh.new_frustum(
                    radius_bottom=1,
                    radius_top=2,
                    height=2,
                    wall_thickness=0.1,
                    sections=20,
                    engine="manifold",
                    name=mojo.MeshName("hollow_frustum_mesh"),
                ),
            ],
        ),
    ]
    assert frustum_mesh.name and hollow_frustum_mesh.name

    mojo_model.mjcf.worldbody = mojo.WorldBody()

    # create two boxes with sites for the springs
    mojo_model.mjcf.worldbody.bodies.extend(
        [
            mojo.Body(
                name=mojo.BodyName("body1"),
                geoms=[
                    mojo.GeomMesh(
                        name=mojo.GeomName("frustum"),
                        mesh=frustum_mesh.name,
                        rgba=mojo.utils.Color.ROSE_500.with_alpha(0.5),
                    ),
                ],
            ),
            mojo.Body(
                name=mojo.BodyName("body2"),
                freejoints=[mojo.FreeJoint()],
                geoms=[
                    mojo.GeomMesh(
                        name=mojo.GeomName("hollow_frustum"),
                        mesh=hollow_frustum_mesh.name,
                        rgba=mojo.utils.Color.CYAN_500.with_alpha(0.5),
                        pose=mojo.PoseQuat(pos=np.array([4.5, 0, 2])),
                    ),
                ],
            ),
        ]
    )

    return mojo_model


def profile():
    import cProfile
    import pstats

    mojo.utils.setup_logger()

    workdir = Path(__file__).parent / "mc_bumper_test_2"
    # Run the Monte Carlo
    runner = mojo.utils.MojoRunner(
        generator=generate,
        workdir=workdir,
        config=mojo.utils.MonteCarloConfig(n_trial=1, n_proc=1, resume=False),
    )

    profiler = cProfile.Profile()
    profiler.enable()
    had_fails = runner.run(clean_workdir=True, cleanup_delay=-1)
    profiler.disable()

    stats = pstats.Stats(profiler).sort_stats("cumulative")
    stats.dump_stats(save_as := "baseline.prof")
    stats.print_callees(30, "apply_load")

    print(f"To view results run:\n\tsnakeviz {save_as}")
    print(f"Finished with {had_fails=}")


if __name__ == "__main__":
    # main()
    profile()
