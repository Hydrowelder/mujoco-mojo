# Running Jobs

!!! abstract

    The **Job Runner** is the engine that transforms your local scripts into production-scale data. Whether you need to run a single "golden" simulation for a video or ten thousand Monte Carlo trials across a compute cluster, `mujoco-mojo run` orchestrates the entire lifecycle. This includes environment snapshotting, multi-processing, and automatic resume logic.

    While jobs can be launched via the Python `MojoRunner` class, it is highly recommended to use the full-featured CLI for better process management and integration with tools like SLURM.

---

## Scaling from 1 to 10,000

Mojo uses a single, unified command structure for all job types. By adjusting a few flags, you can switch from a single "golden" run to a massive stochastic experiment.

### Running a Single Trial

Use `mujoco-mojo run single` when you want to execute exactly one trial. It accepts a single `--trial-num` (not the list form used by `run monte-carlo`, and there's no `--n-trial` since a single run is always one trial). It's the recommended command when running a baseline, re-running an individual trial for inspection, or as the per-task command in a SLURM job array.

```bash linenums="0"
# Run trial 0 (nominal values)
mujoco-mojo run single -g sim.generate -r sim.runtime --seed 123

# Re-run a specific trial from a previous campaign
mujoco-mojo run single -g sim.generate -r sim.runtime --seed 123 --trial-num 42
```

A single trial's folder is named from its own number (`trial_42`). Use `--padding` to zero-pad the number to a fixed width so it matches the other trials of a larger job (`--padding 4` writes `trial_0042`). You rarely need it by hand, since the [SLURM worker](#the-slurm-worker) passes it for you.

```bash linenums="0"
mujoco-mojo run single -g sim.generate -r sim.runtime --trial-num 42 --padding 4
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
| :------------ | :------- | :---------------------------------------------------------------------------------- |
| `--help`      | _N/A_    | Describes all available arguments. Used on its own.                                 |
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

Mojo can pass positional or keyword arguments directly to your Python functions from the CLI. One set of values is shared by your generator, your runtime, and, for an optimization, your objective:

- **Positional:** `--arg` (`-a`), repeatable.
- **Keyword:** `--kwarg` (`-k`) in `key=value` form, repeatable.

```bash linenums="0"
# Example: pass a string keyword and a float
mujoco-mojo run monte-carlo \
    -g sim.generate \
    -r sim.runtime \
    --kwarg mode='fast' \
    --arg 1.5
```

**Positional arguments** go to every function, after the arguments Mojo passes itself (the model and the overrides for a generator; the model, runtime manager, and state for a runtime; the model, telemetry path, and state for an objective). Each function therefore needs a matching parameter or `*args`.

**Keyword arguments** are filtered per function: each one receives only the keywords its signature accepts, or all of them if it takes `**kwargs`. This lets the generator and the runtime keep their own explicit parameters:

```python
def generate(mojo_model, overrides, mode="fast"): ...
def runtime(mojo_model, runtime_manager, state, solver="Newton"): ...
```

```bash linenums="0"
# `mode` goes to generate, `solver` goes to runtime
mujoco-mojo run monte-carlo -g sim.generate -r sim.runtime --kwarg mode='fast' --kwarg solver='PGS'
```

???+ warning "Warning: Misspelled Keywords"

    A keyword that none of your functions accept is an error, so a typo such as `--kwarg modee='fast'` stops the job before anything runs instead of being dropped silently. If any one of your functions takes `**kwargs`, it accepts every keyword and this check cannot tell a typo from a real one. The scripts written by `mujoco-mojo init` use `*args, **kwargs`.

???+ info "Info: Smart Parsing"

    Mojo automatically converts strings like `'1.5'` into a `#!python float`, `true` or `false` into a `#!python bool` (in any capitalization, so `True` works too), or `'[1, 2, 3]'` into a `#!python list`. If you need to pass a string with special characters, or a string that would otherwise be converted, wrap it in single quotes inside the double quotes (e.g., `--kwarg name="'complex-site'"`, or `--kwarg flag="'false'"` for the text `false`).

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
- **Interactive Setup:** You are prompted for job details (Job Name, Partition, Time Limit) with intelligent defaults and safety warnings if your requests exceed node limits. Memory takes any SLURM size, including decimals (`256M`, `1.5G`, `125.9G`), and a bare number is MB. The limit shown beside the prompt is the smallest node in the partition, rounded down to one decimal so the default is never more than the node has. The time limit takes every format `sbatch --time` does (`minutes`, `minutes:seconds`, `hours:minutes:seconds`, `days-hours`, `days-hours:minutes`, and `days-hours:minutes:seconds`).
- **Automatic Scripting:** Mojo generates a `.sh` sbatch script in your workdir, handles `PYTHONPATH` inclusions, and persists global overrides so workers have the correct context.

#### The SLURM Worker

Behind the scenes, Mojo utilizes **SLURM Job Arrays**. Each array task corresponds to a single trial. The orchestrator generates a `mujoco-mojo run single` command for the compute nodes that forces the worker into `local` mode with a single process, using the `$SLURM_ARRAY_TASK_ID` to pick the correct trial. The command also passes your `--arg` and `--kwarg` values, and `--padding` with the width of the whole job, so every worker names its folder like the orchestrator expects (`trial_007`, not `trial_7`).

???+ tip "Tip: Manual Submissions"

    The generated script is saved to your workdir as `mujoco_mojo_submit.sh`. If you prefer to submit manually or need to make custom tweaks to the `#SBATCH` headers, you can simply run `sbatch mujoco_mojo_submit.sh` at any time.

#### Custom SLURM Settings

The wizard only asks about a handful of common fields (partition, cpus, memory, time). Real clusters often need things Mojo has no way to know about ahead of time: account numbers, QOS, mail settings, license-server environment variables, and so on. These live in the `[slurm]` table of Mojo's settings files, managed with `mujoco-mojo settings <init|show|set|reset>`, and - like every other setting - can be set globally for you, or overridden per project, with the project value winning.

**Global defaults** - things about you or your cluster that rarely change (account number, email) belong in `~/.mujoco-mojo/settings.toml`, applied automatically to every submission from any project:

```toml title="~/.mujoco-mojo/settings.toml"
[slurm]
"sbatch.account" = "proj123"
"sbatch.mail-user" = "me@cluster.edu"
MLM_LICENSE_FILE = "27000@license.internal"
```

**Per-project overrides** - a different allocation, a stricter QOS, or anything else specific to one project belongs in that project's local settings file instead:

```bash linenums="0"
mujoco-mojo settings init --project
mujoco-mojo settings set --project slurm.sbatch.account a-different-allocation
mujoco-mojo settings set --project slurm.sbatch.qos high
```

which writes to your project's `.mujoco-mojo/settings.toml`:

```toml title=".mujoco-mojo/settings.toml"
[slurm]
"sbatch.account" = "a-different-allocation"
"sbatch.qos" = "high"
```

Both layers use the same convention:

- Keys prefixed with `sbatch.` become extra `#SBATCH` lines (`"sbatch.account"` &rarr; `#SBATCH --account=proj123`).
- Every other key is exported as an environment variable before the worker command runs.
- Values must be plain strings/numbers/bools - nested tables or arrays are rejected, since this is meant to describe a flat set of settings, not a tree.

If a key appears in both layers, the project-local value wins - so the example above submits with `account=a-different-allocation` (overridden) but still keeps the global `mail-user` and `MLM_LICENSE_FILE`.

#### Where the Project File Lives

The project file is always `.mujoco-mojo/settings.toml`. The `.mujoco-mojo/` directory belongs to the project, so any other project-local file Mojo needs later will sit beside it.

Mojo finds it by checking the current directory, then each parent directory in turn, and uses the **nearest** one. Files further up are not merged in, and the global `~/.mujoco-mojo` directory is never mistaken for a project. This means you can run Mojo from anywhere inside a project, including from a script that `cd`s into its own folder first (the scripts written by `mujoco-mojo init` do), and still pick up the project's settings.

| Command                                     | Which project file it uses                                                                                                                                                     |
| :------------------------------------------ | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mujoco-mojo settings set --project ...`    | The one found by the search. If there is none, a new `./.mujoco-mojo/settings.toml` is created in the current directory.                                                       |
| `mujoco-mojo settings init --project`       | Always creates one in the current directory, even if a parent has one. The nested file takes precedence from that directory down, and the command tells you when this happens. |
| `mujoco-mojo settings show --scope project` | The one found by the search (or says that none was found and where it looked).                                                                                                 |
| `mujoco-mojo settings reset --project`      | Deletes the one found by the search, after asking.                                                                                                                             |

#### Checking What Gets Added

Before the script is written, the wizard prints which settings files it read and exactly what it will add to the submission script:

```text linenums="0"
SLURM settings
  global   /home/me/.mujoco-mojo/settings.toml  3 entries under [slurm]
  project  /home/me/sims/.mujoco-mojo/settings.toml  2 entries under [slurm]

Extra lines added to the submission script:
  #SBATCH --account=a-different-allocation  (project)
  #SBATCH --mail-user=me@cluster.edu  (global)
  #SBATCH --qos=high  (project)
  export MLM_LICENSE_FILE=<value hidden>  (global)
```

Each line is labeled with the file it came from. Environment variable values are not printed, only their names, since they are often credentials or license servers; the values are in the generated `mujoco_mojo_submit.sh`.

???+ tip "Tip: Project Settings Not Showing Up?"

    If the project file is listed as `not found`, neither the current directory nor any of its parents has a `.mujoco-mojo/settings.toml`; the line says where the search started. Run `mujoco-mojo settings show --scope project` from the same place to see which file, if any, is in effect. Keys containing a dot must be quoted in TOML (`"sbatch.account" = "proj123"`); `mujoco-mojo settings set --project slurm.sbatch.account proj123` writes them correctly for you.

---

## State of Health Reporting

When running in [local mode](#local-mode-local), Mojo will create a file in your workdir which reports the status of the job and settings used to run it. This file is updated during the run for basic reporting.

???+ example "Example: Runtime Report"

    To see an example of a runtime report, see the next guide or go to [this page](MOJO_RUNTIME_REPORT.md){:target=_blank}.

For more advanced reporting, see the guide on the [Dojo Dashboard](../../features/dojo/dojo.md).

---

!!! success

    Your job is now running! To keep an eye on your telemetry while the trials are still processing, move on to the [Dojo Dashboard](../../features/dojo/dojo.md) guide to learn about real-time monitoring and rapid data analysis.
