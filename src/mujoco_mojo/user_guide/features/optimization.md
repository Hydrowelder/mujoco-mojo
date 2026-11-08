# Optimization

!!! abstract

    While a [Monte Carlo](../workflow/running-jobs/running-jobs.md) campaign explores the "what if" of random chance, Optimization helps answer the "what is best." Instead of drawing from static distributions, Mojo uses Optuna to intelligently navigate your design space, evolving your model parameters to minimize or maximize a specific physical outcome.

!!! note "Install Required"

    Optimization requires the `optuna`, `optuna-dashboard`, and `joblib` packages. Install with `uv add mujoco-mojo[optimize]` or `pip install mujoco-mojo[optimize]`.

---

## Design Variables vs. Distributions

In a standard Monte Carlo script, you use `mojo_model.sample_dist()` to represent uncertainty. In an optimization study, you replace these with Design Variables.

### Defining the Search Space

Mojo supports two primary types of design variables within your generate script:

- `DesignFloat`: For continuous parameters like spring stiffness, mass, or damping ratios.
- `DesignCategorical`: For discrete choices like material types (`['steel', 'aluminum']`) or solver methods.

???+ example "Example: Defining Design Variables"

    ```python
    # stiffness = mojo_model.sample_dist(mojo.NormalDistribution(...))
    stiffness = mojo_model.design_float(
        name="spring_stiffness",
        default=100.0,  # initial guess
        low=50.0,
        high=200.0
    )

    # material = mojo_model.sample_dist(mojo.CategoricalDistribution(...))
    material = mojo_model.design_categorical(
        name="structure_material",
        default="steel",
        choices=["steel", "aluminum", "play-doh"],
    )
    ```

???+ note "Note: Random Values and Overrides"

    Just because you are using design variables doesn't restrict you from defining distributions! You can very much still add "chaos" to your runs with the random values as you would for a Monte Carlo.

    If override named values are also provided, those will be used over a design value just like for stochastic values.

---

## The Objective Function Contract

The **Objective Function** is the "grade" you give to a simulation. It is a standalone function that Mojo calls after the runtime script finishes. Its job is to ingest the simulation results and return a single `#!python float`.

???+ example "Example: MojoObjective Handle"

    ```python
    def objective(
        mojo_model: mojo.MojoModel,
        telemetry: Path,
        state: mojo.MjState,
    ) -> float:
    ```

A valid objective function must accept the `MojoModel`, the `Path` to the telemetry outputs requested during runtime, and an `MjState` object.

???+ example "Example: Scoring Performance"

    ```python
    def objective(
        mojo_model: mojo.MojoModel,
        telemetry: Path,
        state: mojo.MjState,
    ) -> float:
        """
        Score the trial: Low relative angular velocity (stability) weighted against high translational kinetic energy.
        """
        handoff = mojo_model.get_user_data(Handoff)

        w1 = handoff.box1.rt_ang_vel(state)
        w2 = handoff.box2.rt_ang_vel(state)
        omega_score = float(np.linalg.norm(w1 - w2))

        ke1 = handoff.box1.rt_trans_ke(state)
        ke2 = handoff.box2.rt_trans_ke(state)
        total_ke = ke1 + ke2
        ke_score = 1 / (total_ke + 1e-6)

        # J = 10*Omega + 1*KE_inv
        return (10.0 * omega_score) + (1.0 * ke_score)

    ```

---

## Running the Optimizer

Optimization jobs are launched via the `mujoco-mojo run optimization` command (instead of `monte-carlo`). This engine orchestrates the feedback loop between your `generate` script, your `runtime` script, and your `objective` function.

### Key Command Line Arguments

| Argument                 | Shortcut | Description                                                                    |
| :----------------------- | :------- | :----------------------------------------------------------------------------- |
| `--direction`            | `-d`     | Whether to `minimize` (e.g., error) or `maximize` (e.g., efficiency).          |
| `--sampler`              | `-sm`    | The search algorithm. `tpe` is the workhorse; `cmaes` is for local refinement. |
| `--storage`              | _N/A_    | Defines if a storage database will be placed in the workdir.                   |
| `--evals-per-trial`      | _N/A_    | Runs the sim _N_ times with different seeds and averages the score.            |
| `--refine-search-factor` | _N/A_    | **Aggressive Refinement**. On resume, shrinks bounds around the current best.  |

```bash linenums="0"
# Launch a 400-trial study with 10 parallel workers
mujoco-mojo run optimization \
    -g sim.generate \
    -r sim.runtime \
    --objective sim.objective \
    --n-trial 400 \
    --n-proc 10 \
    --seed 42 \
    --storage \
    --direction minimize
```

---

## Advanced Workflows: Zooming and Robustness

### Stochastic Robustness (`--evals-per-trial`)

In MuJoCo, a "lucky" seed can sometimes produce a great score that isn't actually robust. By setting `--evals-per-trial 5`, Mojo runs every trial 5 times with different joint noise and returns the mean score. This ensures the optimizer finds stable designs, not just lucky ones.

### Adaptive Refinement (`--refine-search-factor`)

Once you find a promising "neighborhood," you can resume the job with `--refine-search-factor 0.2 --resume`. This physically shrinks the search bounds by 80% around your current best trial, allowing the solver to find the absolute peak with high precision.

---

## Post-Processing

One difference you may notice with `mujoco-mojo dojo` is the new **Morph** tab not present for Monte-Carlo jobs. This new tab allows you to view the history of your optimization using [`optuna-dashboard`](https://github.com/optuna/optuna-dashboard).

Morph reads the study's storage database, which an optimization job writes to its workdir by default. Running with `--no-storage` turns it off.

---

!!! success

    The **Optimization** toolkit transforms MuJoCo Mojo from a diagnostic simulator into an automated engineering design tool. By replacing manual parameter sweeps with a closed-loop search, you can efficiently navigate high-dimensional design spaces where physical intuition often hits a ceiling.

    Whether you are filtering out physics noise with **multi-evaluation trials** or "zooming in" on a performance sweet spot with **adaptive refinement**, the Morph toolkit ensures that your final design is backed by rigorous convergence, not just a lucky seed.

??? example "Example: Full Optimization Script"

    ```python
    from pathlib import Path
    from typing import Literal

    import numpy as np
    from pydantic import Field

    import mujoco_mojo as mojo
    import mujoco_mojo.runtime as rt

    logger = mojo.utils.get_logger(__name__)


    class Handoff(mojo.UserData):
        """
        User-defined interconnect between the generator and runtime function. Encapsulates MJCF elements for seamless reference in the physics loop.
        """

        box1: mojo.Body
        box2: mojo.Body
        box1_rot: mojo.AnySite
        springs: dict[
            Literal["pz", "mz"],
            tuple[mojo.AnySite, mojo.AnySite, float, float, float],
        ] = Field(default_factory=dict)

        def define_spring(
            self,
            loc: Literal["pz", "mz"],
            box1: mojo.Body,
            box2: mojo.Body,
            mojo_model: mojo.MojoModel,
        ) -> None:
            mult = 1 if loc == "pz" else -1

            # Add attachment sites to the bodies
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

            # OPTIMIZATION: Define design variables for the search space
            stiffness = mojo_model.sample_design(
                mojo.DesignFloat(
                    name=mojo.ValueName(f"{loc}_stiffness"),
                    stored_value=100.0,  # this will act as the default value for trial 0
                    low=50.0,
                    high=200.0,
                )
            )

            stroke = mojo_model.sample_design(
                mojo.DesignFloat(
                    name=mojo.ValueName(f"{loc}_stroke"),
                    stored_value=(nom := 1.0),
                    low=nom * 0.8,
                    high=nom * 1.2,
                )
            )

            preload = mojo_model.sample_design(
                mojo.DesignFloat(
                    name=mojo.ValueName(f"{loc}_preload"),
                    stored_value=(nom := 1000.0 if loc == "pz" else 750.0),
                    low=nom * 0.8,
                    high=nom * 1.2,
                )
            )

            self.springs.update({loc: (base, tip, stiffness, stroke, preload)})

        def add_spring_force(self, loc: Literal["pz", "mz"]) -> None:
            base, tip, stiffness, stroke, preload = self.springs[loc]

            spring_force = rt.PointToPointForce.stroke_compression_spring(
                name=f"{loc}_spring",
                action_site=base,
                xtion_site=tip,
                stiffness=stiffness,
                max_stroke=stroke,
                preload=preload,
            ).register_to_rm()

            # Request high-fidelity telemetry for these components
            base.request()
            tip.request()
            spring_force.request()


    def generate(mojo_model: mojo.MojoModel, *args, **kwargs) -> mojo.MojoModel:
        """Assembles the world and identifies optimization design variables."""
        mojo_model.mjcf.assets = [
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
            ),
        ]

        # Environment Setup
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
            mojo.Option(timestep=0.001, gravity=np.asarray((0, 0, 0)))
        ]

        # Body Definition
        mojo_model.mjcf.worldbody.bodies.extend(
            [
                box1 := mojo.Body(
                    name=mojo.BodyName("box1"),
                    pose=mojo.PoseQuat(pos=np.asarray([-0.5, 0, 0])),
                    freejoints=[mojo.FreeJoint()],
                    geoms=[
                        mojo.GeomBox(
                            name=mojo.GeomName("g1"),
                            size=np.asarray([0.5, 0.5, 0.5]),
                            rgba=mojo.utils.Color.ROSE_500.with_alpha(0.5),
                        )
                    ],
                ),
                box2 := mojo.Body(
                    name=mojo.BodyName("box2"),
                    pose=mojo.PoseQuat(pos=np.asarray([0.5, 0, 0])),
                    freejoints=[mojo.FreeJoint()],
                    geoms=[
                        mojo.GeomBox(
                            name=mojo.GeomName("g2"),
                            size=np.asarray([0.5, 0.5, 0.5]),
                            rgba=mojo.utils.Color.CYAN_500.with_alpha(0.5),
                        )
                    ],
                ),
            ]
        )

        box1.sites.append(
            box1_rot_site := mojo.SiteSphere(
                name=mojo.SiteName("box1_rot_site"),
                size=0.2,
                pose=mojo.PoseEuler(euler=np.asarray((45, 45, 45))),
                rgba=mojo.utils.Color.FUCHSIA_500.rgba,
            )
        )

        # Handoff
        handoff = Handoff(box1=box1, box2=box2, box1_rot=box1_rot_site)
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
        """Executes the physics loop and flushes telemetry."""
        with runtime_manager as rm:
            handoff = mojo_model.get_user_data(Handoff)
            assert mojo_model.mjcf.worldbody

            # Apply forces defined during generation
            handoff.add_spring_force("pz")
            handoff.add_spring_force("mz")

            if rm.signal_manager:
                for b in mojo_model.mjcf.worldbody.walk_bodies():
                    b.request()
                handoff.box1_rot.request()

            while state.data.time < 2.0:
                rm.step(state)

        return mojo_model


    def objective(
        mojo_model: mojo.MojoModel,
        telemetry: Path,
        state: mojo.MjState,
    ) -> float:
        """
        Score the trial: Low relative angular velocity (stability) weighted against high translational kinetic energy.
        """
        handoff = mojo_model.get_user_data(Handoff)

        w1 = handoff.box1.rt_ang_vel(state)
        w2 = handoff.box2.rt_ang_vel(state)
        omega_score = float(np.linalg.norm(w1 - w2))

        ke1 = handoff.box1.rt_trans_ke(state)
        ke2 = handoff.box2.rt_trans_ke(state)
        total_ke = ke1 + ke2
        ke_score = 1 / (total_ke + 1e-6)

        # J = 10*Omega + 1*KE_inv
        return (10.0 * omega_score) + (1.0 * ke_score)



    # --- Entry Point ---
    if __name__ == "__main__":
        workdir = Path("./optimization_study").resolve()
        runner = mojo.utils.MojoRunner(
            generator=generate,
            runtime=runtime,
            objective=objective,
            workdir=workdir,
            config=mojo.utils.OptimizerConfig(
                n_trial=200,
                n_proc=4,
                direction=mojo.Direction.MINIMIZE,
                sampler=mojo.Sampler.TPE,
                storage=f"sqlite:///{workdir / 'study.db'}",
                resume=True,
            ),
            seed=42,
        )

        logger.info("Starting Optimization Study...")
        runner.run()
    ```
