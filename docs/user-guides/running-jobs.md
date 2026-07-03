# Running Jobs

!!! abstract
    The **Job Runner** is the engine that transforms your local scripts into production-scale data. Whether you need to run a single "golden" simulation for a video or ten thousand Monte Carlo trials across a compute cluster, `mujoco-mojo run` orchestrates the entire lifecycle. This includes environment snapshotting, multi-processing, and automatic resume logic.

    While jobs can be launched via the Python `MojoRunner` class, it is highly recommended to use the full-featured CLI for better process management and integration with tools like SLURM.

---

## Scaling from 1 to 10,000

Mojo uses a single, unified command structure for all job types. By adjusting a few flags, you can switch from a single "golden" run to a massive stochastic experiment.

### Running a Single Trial

Use `mujoco-mojo run single` when you want to execute exactly one trial. It accepts the same arguments as `run monte-carlo` and is the recommended command when running a baseline or re-running an individual trial for inspection.

```bash linenums="0"
# Run trial 0 (nominal values)
mujoco-mojo run single -g sim.generate -r sim.runtime --seed 123

# Re-run a specific trial from a previous campaign
mujoco-mojo run single -g sim.generate -r sim.runtime --seed 123 --trial-num 42
```

???+ note "Note: Nominal Run"
    Trial number `0` uses each distribution's `nominal_value` (if one was provided). This gives you a deterministic baseline that reflects design intent rather than a stochastic draw.

You can also target specific trials within a full `run monte-carlo` campaign by passing `--trial-num` one or more times. This is useful for re-running failed trials without re-running the entire job.

```bash linenums="0"
# Re-run only trials 12 and 42
mujoco-mojo run monte-carlo -g sim.generate -r sim.runtime --seed 123 --trial-num 12 --trial-num 42
```

### Running a Monte Carlo

For large-scale jobs, increase the trial count and specify the number of parallel processors to use.

```bash linenums="0"
mujoco-mojo run monte-carlo \
    --generator sim.generate \
    --runtime sim.runtime \
    --seed 123 \
    --n-trial 100 \
    --n-proc 8
```

---

## Core Command Arguments

The `monte-carlo` command is the workhorse of the `mujoco-mojo run` CLI.

| Argument      | Shortcut | Description                                                                         |
|:--------------|:---------|:------------------------------------------------------------------------------------|
| `--help`      | *N/A*    | Describes all available arguments. Used on its own.                                 |
| `--generator` | `-g`     | **(Required)** Path to your `generate` function (e.g., `sim.generate`).             |
| `--runtime`   | `-r`     | Path to your `runtime` function.                                                    |
| `--seed`      | `-s`     | Sets the campaign entropy for the whole Monte Carlo for reproducible results.       |
| `--n-trial`   | `-nt`    | Total number of unique trials to perform.                                           |
| `--n-proc`    | `-np`    | Parallel processes to use.                                                          |
| `--trial-num` | `-tn`    | Run specific trial IDs (e.g., `-tn 5 -tn 10`). Mutually exclusive with `--n-trial`. |
| `--workdir`   | `-w`     | Workspace directory for logs, snapshots, and the results database.                  |

---

## Workspace Management

Mojo is built for professional simulations where reliability is key. The runner manages the state of your `workdir` to prevent data loss.

- `--resume`: This is the default. Mojo will search the trial status files to in your workdir and only execute trials that are missing or incomplete. Jobs with a failed or success status will be ignored.
- `--clean-workdir` (`-cw`): Wipes the directory before starting. Use this when you've fundamentally changed your MJCF structure and want a fresh start.

???+ tip "Tip: T-Minus 10, 9, 8, ..."
    When using `--clean-workdir`, if the directory already exists, a short countdown is provided before wiping in case you have any second thoughts!

---

## Passing Arguments to Scripts

Mojo can pass positional or keyword arguments directly to your Python functions from the CLI.

- **Generator Args:** `--gen-arg` (`-ga`) and `--gen-kwarg` (`-gk`)
- **Runtime Args:** `--run-arg` (`-ra`) and `--run-kwarg` (`-rk`)

```bash linenums="0"
# Example: Passing a string keyword and a float to the generator function
mujoco-mojo run monte-carlo \
    -g sim.gen \
    --gen-kwarg mode='fast' \
    --gen-arg 1.5
```

???+ info "Info: Smart Parsing"
    Mojo automatically converts strings like `'1.5'` into a `#!python float`, `'True'` into a `#!python bool`, or `'[1, 2, 3]'` into a `#!python list`. If you need to pass a string with special characters, wrap it in single quotes inside the double quotes (e.g., `--gen-kwarg name="'complex-site'"`).

---

## Global Overrides

If you need to "fix" a random variable for an entire job (e.g., forcing a spring stiffness to a specific value regardless of the distribution), use the `--overrides` (`-o`) flag to pass a JSON file of `NamedValue` overrides.

---

## Execution Mode

Mojo supports different strategies for executing your trials using the `--execution-mode` argument. This allows you to scale from a local workstation to a high-performance compute cluster seamlessly.

### Local Mode (`local`)

This is the default execution strategy. Mojo uses the number of processes specified by `--n-proc` to parallelize trials on your current machine. Each worker process is independent, ensuring that a crash in one trial does not cascade to the others.

???+ warning "Warning: Resource Allocation"
    It is easy to over-allocate resources on a local machine. Be a good citizen if you are working on a shared server, only use the number of processes you need.

### SLURM Mode (`slurm`)

For large-scale analysis on high-performance compute clusters, Mojo provides an **Interactive Orchestrator** for SLURM. This mode takes the guesswork out of writing submission scripts and managing environment variables.

When you launch a job with `--execution-mode slurm`, Mojo starts an orchestration wizard instead of running physics immediately.

#### How Orchestration Works

- **Trial Identification:** Mojo scans your workdir and identifies exactly which trials are pending (fully supporting resume logic).
- **Resource Discovery:** It autodetects your cluster's partitions, CPU limits, memory limits, and maximum array sizes.
- **Interactive Setup:** You are prompted for job details (Job Name, Partition, Time Limit) with intelligent defaults and safety warnings if your requests exceed node limits.
- **Automatic Scripting:** Mojo generates a `.sh` sbatch script in your workdir, handles `PYTHONPATH` inclusions, and persists global overrides so workers have the correct context.

#### The SLURM Worker

Behind the scenes, Mojo utilizes **SLURM Job Arrays**. Each array task corresponds to a single trial. The orchestrator generates a command for the compute nodes that forces the worker into `local` mode with a single process, using the `$SLURM_ARRAY_TASK_ID` to pick the correct trial.

???+ tip "Tip: Manual Submissions"
    The generated script is saved to your workdir as `mujoco_mojo_submit.sh`. If you prefer to submit manually or need to make custom tweaks to the `#SBATCH` headers, you can simply run `sbatch mujoco_mojo_submit.sh` at any time.

---

## State of Health Reporting

When running in [local mode](#local-mode-local), Mojo will create a file in your workdir which reports the status of the job and settings used to run it. This file is updated during the run for basic reporting.

???+ example "Example: Runtime Report"
    To see an example of a runtime report, see the next guide or go to [this page](MOJO_RUNTIME_REPORT.md){:target=_blank}.

For more advanced reporting, see the guide on the [Dojo Dashboard](dojo.md).

---

!!! success
    Your job is now running! To keep an eye on your telemetry while the trials are still processing, move on to the [Dojo Dashboard](dojo.md) guide to learn about real-time monitoring and rapid data analysis.
