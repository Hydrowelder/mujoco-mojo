from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import Field

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

logger = mojo.utils.get_logger(__name__)

FIXED_CAMERA_NAME = mojo.CameraName("static")
BOX_CAMERA_NAME = mojo.CameraName("box_camera")
TRACKING_CAMERA_NAME = mojo.CameraName("tracker_cam")


def perform_mock_draws(mojo_model: mojo.MojoModel) -> None:
    """
    Draws one sample from every distribution type stochas supports.

    These draws don't feed into the model or the simulation in any way; this just exists to exercise every distribution type (with categories/units set) during a Monte Carlo run for testing.
    """
    assert mojo_model.us
    us = mojo_model.us
    mojo_model.sample_dist(
        mojo.NormalDistribution(
            name=mojo.DistName("mock_normal"),
            nominal=0.0,
            mu=0,
            sigma=1.0,
            category="link_props",
            unit=us.kg,
        )
    )
    mojo_model.sample_dist(
        mojo.UniformDistribution(
            name=mojo.DistName("mock_uniform"),
            nominal=1.0,
            low=0,
            high=2.0,
            category="contact",
            unit=us.m,
        )
    )
    mojo_model.sample_dist(
        mojo.DiscreteUniformDistribution(
            name=mojo.DistName("mock_discrete_uniform"),
            nominal=2,
            low=0,
            high=5,
            category="counts",
            # unit=None: integer counts are dimensionless; no UnitDescriptor exists for "count"
        )
    )
    mojo_model.sample_dist(
        mojo.CategoricalDistribution[str](
            name=mojo.DistName("mock_categorical"),
            choices={
                "O+": 0.36,
                "O-": 0.14,
                "A+": 0.28,
                "A-": 0.08,
                "B+": 0.08,
                "B-": 0.03,
                "AB+": 0.02,
                "AB-": 0.01,
            },
            nominal="O+",
            category="material",
            unit=us.dimensionless,  # non-numeric outputs (strings) cannot be scaled by a UnitDescriptor
        )
    )
    mojo_model.sample_dist(
        mojo.PermutationDistribution[str](
            name=mojo.DistName("mock_permutation"),
            nominal=["A", "B", "C"],
            items=["A", "B", "C"],
            category="ordering",
            unit=us.dimensionless,  # non-numeric outputs (lists) cannot be scaled by a UnitDescriptor
        ),
        size=3,
    )
    mojo_model.sample_dist(
        mojo.TriangularDistribution(
            name=mojo.DistName("mock_triangular"),
            nominal=0.5,
            low=0,
            high=1,
            mode=0.5,
            category="geometry",
            unit=us.m,
        )
    )
    mojo_model.sample_dist(
        mojo.TruncatedNormalDistribution(
            name=mojo.DistName("mock_truncated_normal"),
            nominal=0.0,
            mu=0,
            sigma=1,
            low=-1.0,
            category="sensor_noise",
            unit=us["m/s"],
        )
    )
    mojo_model.sample_dist(
        mojo.LogNormalDistribution(
            name=mojo.DistName("mock_log_normal"),
            nominal=1.0,
            s=0.5,
            scale=1,
            category="material",
            unit=us.pascal,
        )
    )
    mojo_model.sample_dist(
        mojo.PoissonDistribution(
            name=mojo.DistName("mock_poisson"),
            nominal=4,
            lam=4.0,
            category="counts",
            unit=us.dimensionless,  # Poisson outputs are event counts (dimensionless integers)
        )
    )
    mojo_model.sample_dist(
        mojo.ExponentialDistribution(
            name=mojo.DistName("mock_exponential"),
            nominal=1.0,
            lam=1.0,
            category="reliability",
            unit=us.second,  # exponential samples are waiting times (seconds), not the rate
        )
    )
    mojo_model.sample_dist(
        mojo.RayleighDistribution(
            name=mojo.DistName("mock_rayleigh"),
            nominal=1.0,
            scale=1.0,
            category="vibration",
            unit=us.m / us.s,
        )
    )
    mojo_model.sample_dist(
        mojo.BernoulliDistribution(
            name=mojo.DistName("mock_bernoulli"),
            nominal=True,
            p=0.5,
            category="flags",
            unit=us.dimensionless,  # boolean outcomes (0/1) are dimensionless
        ),
        size=4,
    )
    mojo_model.sample_dist(
        mojo.GammaDistribution(
            name=mojo.DistName("mock_gamma"),
            nominal=2.0,
            alpha=2.0,
            beta=1.0,
            category="actuation",
            unit=us.newton,
        )
    )
    mojo_model.sample_dist(
        mojo.BetaDistribution(
            name=mojo.DistName("mock_beta"),
            nominal=0.5,
            alpha=2.0,
            beta=2.0,
            category="friction",
            unit=us.dimensionless,  # Beta outputs are probabilities/ratios in [0, 1] (dimensionless)
        ),
        size=5,
    )
    mojo_model.sample_dist(
        mojo.WeibullDistribution(
            name=mojo.DistName("mock_weibull"),
            nominal=1.0,
            shape=1.5,
            scale=1.0,
            category="fatigue",
            unit=us.second,  # Weibull samples are time-to-failure values
        )
    )
    mojo_model.sample_dist(
        mojo.BinomialDistribution(
            name=mojo.DistName("mock_binomial"),
            nominal=10,
            n=20,
            p=0.5,
            category="counts",
            unit=us.dimensionless,  #  binomial outputs are success counts (dimensionless integers)
        )
    )
    mojo_model.sample_dist(
        mojo.NegativeBinomialDistribution(
            name=mojo.DistName("mock_negative_binomial"),
            nominal=3,
            r=3,
            p=0.5,
            category="counts",
            unit=us.dimensionless,  # negative binomial outputs are failure counts (dimensionless integers)
        )
    )
    mojo_model.sample_dist(
        mojo.GeometricDistribution(
            name=mojo.DistName("mock_geometric"),
            nominal=2,
            p=0.5,
            category="counts",
            unit=us.dimensionless,  #  geometric outputs are trial counts (dimensionless integers)
        )
    )
    mojo_model.sample_dist(
        mojo.LogisticDistribution(
            name=mojo.DistName("mock_logistic"),
            nominal=0.0,
            mu=0.0,
            beta=1.0,
            category="control",
            unit=us.volt,
        )
    )
    mojo_model.sample_dist(
        mojo.ParetoDistribution(
            name=mojo.DistName("mock_pareto"),
            nominal=1.0,
            alpha=2.5,
            beta=1.0,
            category="economics",
            unit=us.dimensionless,  # Pareto outputs are dimensionless scale ratios
        )
    )
    mojo_model.sample_dist(
        mojo.StudentTDistribution(
            name=mojo.DistName("mock_student_t"),
            nominal=0.0,
            nu=5.0,
            category="sensor_noise",
            unit=us.dimensionless,  # Student-t outputs are dimensionless standardized scores
        )
    )
    mojo_model.sample_dist(
        mojo.HypergeometricDistribution(
            name=mojo.DistName("mock_hypergeometric"),
            nominal=8,
            N=50,
            M=20,
            K=20,
            category="counts",
            unit=us.dimensionless,  #  hypergeometric outputs are draw counts (dimensionless integers)
        )
    )
    mojo_model.sample_dist(
        mojo.BetaBinomialDistribution(
            name=mojo.DistName("mock_beta_binomial"),
            nominal=10,
            n=20,
            alpha=5.0,
            beta=5.0,
            category="counts",
            unit=us.dimensionless,  #  beta-binomial outputs are success counts (dimensionless integers)
        )
    )
    mojo_model.sample_dist(
        mojo.CauchyDistribution(
            name=mojo.DistName("mock_cauchy"),
            nominal=0.0,
            theta=0.0,
            sigma=1.0,
            category="sensor_noise",
            unit=us.radian,
        )
    )
    mojo_model.sample_dist(
        mojo.ChiSquaredDistribution(
            name=mojo.DistName("mock_chi_squared"),
            nominal=4.0,
            p=4,
            category="statistics",
            unit=us.dimensionless,  #  chi-squared outputs are dimensionless test statistics
        )
    )
    x = float(
        mojo_model.sample_dist(
            mojo.LaplaceDistribution(
                name=mojo.DistName("mock_laplace"),
                nominal=10.0,
                mu=10.0,
                sigma=5.0,
                category="sensor_noise",
                unit=us.cm,
            )
        ).squeeze()
    )
    logger.info(f"Laplace sampled to {x} {us.length} (from {x / us.cm} cm)")

    mojo_model.sample_dist(
        mojo.FDistribution(
            name=mojo.DistName("mock_f"),
            nominal=1.25,
            nu1=5.0,
            nu2=10.0,
            category="statistics",
            unit=us.dimensionless,  #  F-distribution outputs are dimensionless variance ratios
        )
    )


class Handoff(mojo.UserData):
    """
    This class exists to serve as a user defined interconnect between the generator and runtime function.

    It is here to allow encapsulation for defining MJCF elements, while retaining the simple ability to later use those definitions in the runtime.
    """

    box1_rot: mojo.AnySite
    springs: dict[
        Literal["pz", "mz"],
        tuple[mojo.AnySite, mojo.AnySite, mojo.NamedValue, mojo.NamedValue],
    ] = Field(default_factory=dict)
    box1_bunny: mojo.GeomMesh
    box2_bunny: mojo.GeomMesh

    def define_spring(
        self,
        loc: Literal["pz", "mz"],
        box1: mojo.Body,
        box2: mojo.Body,
        mojo_model: mojo.MojoModel,
    ):
        mult = 1 if loc == "pz" else -1

        box1.sites.append(
            base := mojo.SiteSphere(
                name=mojo.SiteName(f"{loc}_spring_base_site"),
                size=0.1,
                pose=mojo.PoseQuat(pos=np.asarray([0.4, 0, mult * 0.5])),
                rgba=mojo.utils.Color.RED_500.rgba,
            )
        )
        box2.sites.append(
            tip := mojo.SiteSphere(
                name=mojo.SiteName(f"{loc}_spring_tip_site"),
                size=0.1,
                pose=mojo.PoseQuat(pos=np.asarray([-0.4, 0, mult * 0.5])),
                rgba=mojo.utils.Color.BLUE_500.rgba,
            )
        )

        # perform random draws
        stiffness = mojo_model.sample_dist(
            mojo.TruncatedNormalDistribution(
                name=mojo.DistName(f"{loc}_stiffness"),
                nominal=100,
                mu=100,
                sigma=20,
                low=0,
            )
        ).squeeze()
        stroke = mojo_model.sample_dist(
            mojo.TruncatedNormalDistribution(
                name=mojo.DistName(f"{loc}_stroke"),
                nominal=(nom := 1),
                mu=nom,
                sigma=nom * 0.1,
                low=nom * 0.8,
                high=nom * 1.2,
            )
        ).squeeze()

        self.springs.update({loc: (base, tip, stiffness, stroke)})

    def add_spring_force(self, loc: Literal["pz", "mz"]):
        base, tip, stiffness, stroke = self.springs[loc]

        spring_force = rt.PointToPointForce.stroke_compression_spring(
            name=f"{loc}_spring",
            action_site=base,  # red box
            xtion_site=tip,  # blue box
            stiffness=float(stiffness),
            max_stroke=float(stroke),
            preload=1000 if loc == "pz" else 750,
        ).register_to_rm()

        base.request()
        tip.request()
        spring_force.request()


def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
    """Generates two boxes at varying distances."""
    # Download this skybox from here: https://www.david-gable.com/work/photography/Space/Star-Skybox/p1/
    skybox_folder = (mojo.DepPath() / "textures" / "stars").resolve()
    MESHES_DIR = mojo.DepPath(__file__).parent.parent / "meshes"

    logger.debug(f"This is a log for {mojo_model.trial_num}")
    logger.info(f"This is a log for {mojo_model.trial_num}")
    logger.warning(f"This is a log for {mojo_model.trial_num}")
    logger.error(f"This is a log for {mojo_model.trial_num}")
    logger.critical(f"This is a log for {mojo_model.trial_num}")

    # mock draws across every stochas distribution type, unused by the sim itself
    mojo_model.with_unit_system(mojo.UnitSystem.si())
    perform_mock_draws(mojo_model)
    # configure simulation
    mojo_model.mjcf.assets = [
        # add a checkerboard
        mojo.Asset(
            textures=[
                grid_tex := mojo.TextureBuiltIn(
                    name=mojo.TextureName("grid_tex"),
                    type=mojo.TextureType.D2,
                    builtin=mojo.TextureBuiltInType.CHECKER,
                    width=512,
                    height=512,
                    rgb1=mojo.utils.Color.SLATE_600.rgb,
                    rgb2=mojo.utils.Color.SLATE_800.rgb,
                )
            ],
            materials=[
                grid_mat := mojo.Material(
                    name=mojo.MaterialName("grid_mat"),
                    texture=grid_tex.name,
                    texrepeat=np.asarray((1, 1)),
                )
            ],
            meshes=[
                bunny_mesh := mojo.Mesh(
                    name=mojo.MeshName("bunny_mesh"),
                    file=MESHES_DIR / "bunny2.stl",
                    scale=np.ones(3) * 2,
                ),
            ],
        ),
    ]
    assert bunny_mesh.name

    # add a skybox
    if mojo_model.is_nominal:
        mojo_model.mjcf.assets.append(
            mojo.Asset(
                textures=[
                    mojo.Texture(
                        name=mojo.TextureName("skybox_texture_colors"),
                        type=mojo.TextureType.SKYBOX,
                        fileback=skybox_folder / "nz.png",
                        filedown=skybox_folder / "ny.png",
                        filefront=skybox_folder / "pz.png",
                        fileleft=skybox_folder / "nx.png",
                        fileright=skybox_folder / "px.png",
                        fileup=skybox_folder / "py.png",
                    )
                ]
            ),
        )

    mojo_model.mjcf.worldbody = mojo.WorldBody(
        geoms=[]
        if mojo_model.is_nominal
        else [
            mojo.GeomPlane(
                name=mojo.GeomName("floor"),
                size=np.asarray([0, 0, 0.1]),
                pose=mojo.PoseQuat(pos=np.asarray((0, 0, -5))),
                material=grid_mat.name,
                contype=0,
                conaffinity=0,
            ),
        ]
    )
    mojo_model.mjcf.options = [
        mojo.Option(
            timestep=0.001,
            gravity=np.asarray((0, 0, 0)),
        )
    ]
    mojo_model.mjcf.visuals = [
        mojo.Visual(
            map=mojo.VisualMap(force=4),
            scale=mojo.VisualScale(forcewidth=0.1),
        )
    ]

    # create two boxes with sites for the springs
    mojo_model.mjcf.worldbody.bodies.extend(
        [  # Box 1
            box1 := mojo.Body(
                name=mojo.BodyName("box1"),
                pose=mojo.PoseQuat(pos=np.asarray([-0.5, 0, 0])),
                freejoints=[mojo.FreeJoint()],
                geoms=[
                    mojo.GeomBox(
                        name=mojo.GeomName("g1"),
                        size=np.asarray([0.5, 0.5, 0.5]),
                        rgba=mojo.utils.Color.ROSE_500.with_alpha(0.5),
                        contype=0,
                        conaffinity=0,
                    ),
                    box1_bunny := mojo.GeomMesh(
                        name=mojo.GeomName("box1_bunny"),
                        mesh=bunny_mesh.name,
                        pose=mojo.PoseEuler(
                            euler=np.array((90, 0, 0)), pos=np.array((0, 0, 0.5))
                        ),
                        rgba=mojo.utils.Color.AMBER_500.rgba,
                    ),
                ],
                cameras=[
                    mojo.Camera(
                        name=BOX_CAMERA_NAME,
                        pose=mojo.PoseEuler(
                            pos=np.asarray((0.4, 0, 0)),
                            euler=np.asarray(
                                (90, -90, 0),
                            ),
                        ),
                        fovy=120,
                    ),
                ],
            ),
            # Box 2
            box2 := mojo.Body(
                name=mojo.BodyName("box2"),
                pose=mojo.PoseQuat(pos=np.asarray([0.5, 0, 0])),
                freejoints=[mojo.FreeJoint()],
                geoms=[
                    mojo.GeomBox(
                        name=mojo.GeomName("g2"),
                        size=np.asarray([0.5, 0.5, 0.5]),
                        rgba=mojo.utils.Color.CYAN_500.with_alpha(0.5),
                        contype=0,
                        conaffinity=0,
                    ),
                    box2_bunny := mojo.GeomMesh(
                        name=mojo.GeomName("box2_bunny"),
                        mesh=bunny_mesh.name,
                        pose=mojo.PoseEuler(
                            euler=np.array((90, 0, 0)), pos=np.array((0, 0, 0.5))
                        ),
                        rgba=mojo.utils.Color.EMERALD_500.rgba,
                    ),
                ],
            ),
        ]
    )

    box1.sites.append(
        box1_rot_site := mojo.SiteSphere(
            name=mojo.SiteName("box1_rot_site"),
            size=0.2,
            pose=mojo.PoseEuler(
                euler=np.asarray((45, 45, 45)),
                angle=mojo.Angle.DEGREE,
                eulerseq=mojo.EulerSeq.xyz,
            ),
            rgba=mojo.utils.Color.FUCHSIA_500.rgba,
        )
    )

    mojo_model.mjcf.worldbody.cameras = [
        mojo.Camera(
            name=FIXED_CAMERA_NAME,
            pose=mojo.PoseEuler(
                pos=np.asarray((0, -10, 0)),
                euler=np.asarray((90, 0, 0)),
            ),
            fovy=30,
        ),
        mojo.Camera(
            name=TRACKING_CAMERA_NAME,
            pose=mojo.PoseQuat(
                pos=np.asarray((0, -10, 0)),
            ),
            fovy=30,
            mode=mojo.TrackingMode.TARGETBODY,
            target=box2.name,
        ),
    ]

    # add handoff data
    handoff = Handoff(
        box1_rot=box1_rot_site, box1_bunny=box1_bunny, box2_bunny=box2_bunny
    )
    mojo_model.user_data = handoff
    handoff.define_spring("pz", box1, box2, mojo_model)
    handoff.define_spring("mz", box1, box2, mojo_model)

    return mojo_model


def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    """Executes the spring repulsion simulation."""
    # Identify our sites from the generated model
    # Note: We can find them by name in the worldbody
    assert mojo_model.mjcf.worldbody is not None

    handoff = mojo_model.get_user_data(Handoff)

    with runtime_manager as rm:
        if mojo_model.trial_num < 10:
            rt.VideoRecorder(
                path=mojo_model.trial_dir / "fixed_camera.mp4",
                camera_name=FIXED_CAMERA_NAME,
                show_loads=True,
                show_net_force=True,
                show_proximities=True,
                show_traces=True,
            ).setup(state).register_to_rm()

        rt.Tracer(target=handoff.box1_bunny, duration=1.0).register_to_rm()
        rt.Tracer(target=handoff.box2_bunny, duration=1.0).register_to_rm()

        if mojo_model.is_nominal:
            rt.VideoRecorder(
                path=mojo_model.trial_dir / "tracking_camera.webm",
                camera_name=TRACKING_CAMERA_NAME,
                show_loads=True,
                show_proximities=True,
                show_traces=True,
            ).setup(state).register_to_rm()

            rt.VideoRecorder(
                path=mojo_model.trial_dir / "box_camera.gif",
                camera_name=BOX_CAMERA_NAME,
                show_traces=True,
            ).setup(state).register_to_rm()

        # Create compression springs
        handoff.add_spring_force("pz")
        handoff.add_spring_force("mz")

        proximity = mojo.utils.Proximity(
            geom_1=handoff.box1_bunny,
            geom_2=handoff.box2_bunny,
            dist_max=3,
            algorithm=mojo.ProximityType.CONVEX_HULL,
        ).register_to_rm()

        if rm.signal_manager:
            rm.signal_manager.record_decimation = 1

            for b in mojo_model.mjcf.worldbody.walk_bodies():
                b.request()

            proximity.request(channels=["dist", "fromto", "prox_type"])

            handoff.box1_rot.request()

        # Run for 2 seconds
        while state.data.time < 2.0:
            rm.step(state)

    return mojo_model


def main():
    mojo.utils.setup_logger()

    workdir = Path(__file__).parent / "mc_bumper_test_2"
    # Run the Monte Carlo
    runner = mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
        workdir=workdir,
        config=mojo.utils.MonteCarloConfig(n_trial=1, n_proc=1),
    )

    had_fails = runner.run(clean_workdir=True, cleanup_delay=-1)

    print(f"Finished with {had_fails=}")


def profile():
    import cProfile
    import pstats

    mojo.utils.setup_logger()

    workdir = Path(__file__).parent / "mc_bumper_test_2"
    # Run the Monte Carlo
    runner = mojo.utils.MojoRunner(
        generator=generate,
        runtime=runtime,
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
