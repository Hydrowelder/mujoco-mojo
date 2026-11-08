# Command Line Reference

Every `mujoco-mojo` command with its arguments and options. Add `--help` to any command to see the same in your terminal.

| Command | What it does |
| :--- | :--- |
| [`mujoco-mojo init`](#mujoco-mojo-init) | Initialize a new empty mujoco-mojo project. |
| [`mujoco-mojo reloaded`](#mujoco-mojo-reloaded) | Run a development session in a terminal UI, with the model shown in a MuJoCo viewer. |
| [`mujoco-mojo dojo`](#mujoco-mojo-dojo) | Launch the Mojo Dojo to monitor the progress of a running job. |
| [`mujoco-mojo run`](#mujoco-mojo-run) | Execution commands for various Mojo generators and solvers (Monte Carlo, optimization, etc.). |
| [`mujoco-mojo settings`](#mujoco-mojo-settings) | Manage global mujoco-mojo settings at `~/.mujoco-mojo/settings.toml`. |
| [`mujoco-mojo docs`](#mujoco-mojo-docs) | Find the user guides that ship with this version of mujoco-mojo. |

## Global options

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--version` | flag | off | Show version and exit. |
| `--install-completion` | flag | off | Install completion for the current shell. |
| `--show-completion` | flag | off | Show completion for the current shell, to copy it or customize the installation. |

## `mujoco-mojo init`

Initialize a new empty mujoco-mojo project.

Writes these to the current directory: a `simulation.py` scaffold, the `run.sh` and `reloaded.sh` scripts, a project settings file, and an `AGENTS.md` that points coding agents at the user guides (an existing `AGENTS.md` is left alone). The scaffold contains stub implementations of **generate**, **runtime**, and **UserData**. Pass `--optimizer` to also include an **objective** stub.

```bash
mujoco-mojo init [OPTIONS]
```

**Options**

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--optimizer`, `-op` / `--no-optimizer`, `-nop` | flag | `--no-optimizer` | Include an `objective` function stub for use with **mujoco-mojo run optimization**. |

## `mujoco-mojo reloaded`

Run a development session in a terminal UI, with the model shown in a MuJoCo viewer.

Regenerates and reloads the MJCF model on command, or whenever your source files change, for rapid prototyping.

```bash
mujoco-mojo reloaded [OPTIONS]
```

**Options**

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--generator`, `-g` | text | none | Path to generator (e.g. 'sim.gen') |
| `--runtime`, `-r` | text | none | Runtime path to use to run dynamics (e.g. 'sim.run') |
| `--workdir`, `-w` | path | `mojo-models` | Workspace directory. The job will be executed out of this directory. It will be made if it does not already exist. |
| `--user-interface`, `-ui` | one of `opengl`, `studio`, `web` | `web` | Which viewer to show the model in. **opengl** is the classic MuJoCo window: it needs a display (X11 forwarding over SSH) but is ideal for local development. **studio** is a native MuJoCo Studio window and **web** is MuJoCo Studio in a browser, which works over SSH and without a display. |
| `--gfx` | one of `default`, `opengl`, `opengl_software`, `vulkan`, `vulkan_software` | `default` | How the native MuJoCo Studio window is drawn (Studio's own --gfx option): **default**, **opengl**, **opengl_software**, **vulkan**, **vulkan_software** where the display only has software OpenGL, such as a remote desktop, and the default fails to draw. Ignored by the **web** and **opengl** viewers. |
| `--overrides`, `-o` | path | none | File which contains NamedValue overrides to use in all trials. |
| `--trial-num`, `-tn` | integer | `0` | Specific trial number to run (-tn 5) |
| `--seed`, `-s` | integer | none | Seed to use for the job. |
| `--config`, `-c` | path | none | File which contains a model config definition. Mutually exclusive with the generator option. |
| `--model-config-name`, `-mcn` | text | none | Name for model dump file (e.g. 'model_config.json') |
| `--xml-name`, `-xml` | text | `model.xml` | Name for XML file (e.g. 'model.xml') |
| `--watch` / `--no-watch` | flag | `--watch` | Automatically reload when *.py source files change. |
| `--record` / `--no-record` | flag | `--no-record` | Record telemetry to a per-trial 'telemetry.parquet' (so the run can be inspected with mujoco-mojo dojo) and capture frames for any registered video recorders. Off by default since interactive sessions can run indefinitely. |
| `--arg`, `-a` | text, repeatable | none | Positional arg passed to the `generator`, the runtime, and the objective. Repeat for multiple values (e.g., --arg high_friction --arg 1.5). Values are smart-parsed (e.g., '1.5' becomes a float and 'false' a bool). All of those functions get the same values, so each must accept them. |
| `--kwarg`, `-k` | text, repeatable | none | Keyword arg (key=value) passed to the `generator`, the runtime, and the objective. Each function receives only the keywords it accepts, and a keyword that none of them accept is an error. Example: --kwarg mode='fast' --kwarg complexity=10. Strings with special characters should be single-quoted inside the double quotes. |
| `--port`, `-p` | integer | `8000` | Port number to use to serve the process. Auto-selects the next free port at or after this one if it's already taken. |
| `--verbose`, `-v` | count | `0` | Increase verbosity (can be repeated, e.g., -vv for DEBUG). |
| `--quiet`, `-q` | count | `0` | Decrease verbosity (can be repeated, e.g., -qq for ERROR). |

## `mujoco-mojo dojo`

Launch the Mojo Dojo to monitor the progress of a running job.

This command reads status files in the workdir to give live updates.

```bash
mujoco-mojo dojo [OPTIONS] WORKDIR
```

**Arguments**

| Argument | Type | Description |
| :--- | :--- | :--- |
| `WORKDIR` | path | Workspace directory to build the Dojo process for. This should be the same argument as what is used for other mujoco-mojo run commands. |

**Options**

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--host`, `-h` | text | `127.0.0.1` | What host IP should be used to serve the process. |
| `--port`, `-p` | integer | `8000` | Port number to use to serve the process. Auto-selects the next free port at or after this one if it's already taken. |
| `--n-proc`, `-np` | integer | `1` | Parallel processes to use in executing tasks (such as running Monte Carlo or status file proccessing for the Dojo process). Be a good citizen. It is easy to abuse this command. Only use what resouces you absolutely need. |
| `--password`, `-pw` | text | none | Enable Basic Auth protection |
| `--verbose`, `-v` | count | `0` | Increase verbosity (can be repeated, e.g., -vv for DEBUG). |
| `--quiet`, `-q` | count | `0` | Decrease verbosity (can be repeated, e.g., -qq for ERROR). |

## `mujoco-mojo run`

Execution commands for various Mojo generators and solvers (Monte Carlo, optimization, etc.).

```bash
mujoco-mojo run [OPTIONS] COMMAND [ARGS]...
```

**Commands**

| Command | What it does |
| :--- | :--- |
| [`mujoco-mojo run monte-carlo`](#mujoco-mojo-run-monte-carlo) | Execute a Monte Carlo campaign. |
| [`mujoco-mojo run single`](#mujoco-mojo-run-single) | Execute a single trial. |
| [`mujoco-mojo run watch-workdir`](#mujoco-mojo-run-watch-workdir) | Keep a job's status current until it finishes. |
| [`mujoco-mojo run optimization`](#mujoco-mojo-run-optimization) | Execute an automated Design Optimization study. |

### `mujoco-mojo run monte-carlo`

Execute a Monte Carlo campaign.

This command handles the directory setup, distribution salting, and parallel execution of physics trials.

```bash
mujoco-mojo run monte-carlo [OPTIONS]
```

**Options**

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--generator`, `-g` | text | required | Path to generator (e.g. 'sim.gen') |
| `--runtime`, `-r` | text | none | Runtime path to use to run dynamics (e.g. 'sim.run') |
| `--workdir`, `-w` | path | `mojo-models` | Workspace directory. The job will be executed out of this directory. It will be made if it does not already exist. |
| `--n-trial`, `-nt` | integer | `2` | Number of trials to be performed in the job. |
| `--n-proc`, `-np` | integer | `1` | Parallel processes to use in executing tasks (such as running Monte Carlo or status file proccessing for the Dojo process). Be a good citizen. It is easy to abuse this command. Only use what resouces you absolutely need. |
| `--resume` / `--no-resume` | flag | `--resume` | Resume from previous state on disk |
| `--seed`, `-s` | integer | none | Seed to use for the job. |
| `--clean-workdir` / `--no-clean-workdir` | flag | `--no-clean-workdir` | Delete the workdir before running (mutually exclusive with --resume) |
| `--model-config-name`, `-mcn` | text | none | Name for model dump file (e.g. 'model_config.json') |
| `--xml-name`, `-xml` | text | `model.xml` | Name for XML file (e.g. 'model.xml') |
| `--execution-mode`, `-em` | one of `local`, `slurm` | `local` | The strategy used to execute trials. |
| `--overrides`, `-o` | path | none | File which contains NamedValue overrides to use in all trials. |
| `--trial-num`, `-tn` | integer, repeatable | none | Specific trial numbers to run (-tn 5 -tn 42) |
| `--arg`, `-a` | text, repeatable | none | Positional arg passed to the `generator`, the runtime, and the objective. Repeat for multiple values (e.g., --arg high_friction --arg 1.5). Values are smart-parsed (e.g., '1.5' becomes a float and 'false' a bool). All of those functions get the same values, so each must accept them. |
| `--kwarg`, `-k` | text, repeatable | none | Keyword arg (key=value) passed to the `generator`, the runtime, and the objective. Each function receives only the keywords it accepts, and a keyword that none of them accept is an error. Example: --kwarg mode='fast' --kwarg complexity=10. Strings with special characters should be single-quoted inside the double quotes. |
| `--verbose`, `-v` | count | `0` | Increase verbosity (can be repeated, e.g., -vv for DEBUG). |
| `--quiet`, `-q` | count | `0` | Decrease verbosity (can be repeated, e.g., -qq for ERROR). |

### `mujoco-mojo run single`

Execute a single trial.

This command handles the directory setup, distribution salting, and execution of exactly one physics trial (trial 0, the nominal run, unless `--trial-num` targets a different one).

```bash
mujoco-mojo run single [OPTIONS]
```

**Options**

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--generator`, `-g` | text | required | Path to generator (e.g. 'sim.gen') |
| `--runtime`, `-r` | text | none | Runtime path to use to run dynamics (e.g. 'sim.run') |
| `--workdir`, `-w` | path | `mojo-models` | Workspace directory. The job will be executed out of this directory. It will be made if it does not already exist. |
| `--n-proc`, `-np` | integer | `1` | Parallel processes to use in executing tasks (such as running Monte Carlo or status file proccessing for the Dojo process). Be a good citizen. It is easy to abuse this command. Only use what resouces you absolutely need. |
| `--resume` / `--no-resume` | flag | `--resume` | Resume from previous state on disk |
| `--seed`, `-s` | integer | none | Seed to use for the job. |
| `--clean-workdir` / `--no-clean-workdir` | flag | `--no-clean-workdir` | Delete the workdir before running (mutually exclusive with --resume) |
| `--model-config-name`, `-mcn` | text | none | Name for model dump file (e.g. 'model_config.json') |
| `--xml-name`, `-xml` | text | `model.xml` | Name for XML file (e.g. 'model.xml') |
| `--execution-mode`, `-em` | one of `local`, `slurm` | `local` | The strategy used to execute trials. |
| `--overrides`, `-o` | path | none | File which contains NamedValue overrides to use in all trials. |
| `--trial-num`, `-tn` | integer | `0` | Specific trial number to run (-tn 5) |
| `--padding` | integer, at least 1 | none | Zero-padding width of the trial folder name (--padding 3 gives trial_007). Defaults to no padding for a single trial. SLURM workers pass the width of the whole job so their folders match. |
| `--arg`, `-a` | text, repeatable | none | Positional arg passed to the `generator`, the runtime, and the objective. Repeat for multiple values (e.g., --arg high_friction --arg 1.5). Values are smart-parsed (e.g., '1.5' becomes a float and 'false' a bool). All of those functions get the same values, so each must accept them. |
| `--kwarg`, `-k` | text, repeatable | none | Keyword arg (key=value) passed to the `generator`, the runtime, and the objective. Each function receives only the keywords it accepts, and a keyword that none of them accept is an error. Example: --kwarg mode='fast' --kwarg complexity=10. Strings with special characters should be single-quoted inside the double quotes. |
| `--verbose`, `-v` | count | `0` | Increase verbosity (can be repeated, e.g., -vv for DEBUG). |
| `--quiet`, `-q` | count | `0` | Decrease verbosity (can be repeated, e.g., -qq for ERROR). |

### `mujoco-mojo run watch-workdir`

Keep a job's status current until it finishes.

For jobs whose trials are run by other processes, such as the tasks of a SLURM job. They only write their own trial's status, so **job_status.json** (elapsed time, trial durations) and the runtime report would otherwise stay as they were at submission. This checks the trials every few seconds and updates both, and exits by itself once every trial is done. Safe to stop with Ctrl+C and start again; the job is not affected.

```bash
mujoco-mojo run watch-workdir [OPTIONS]
```

**Options**

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--workdir`, `-w` | path | `mojo-models` | Workspace directory. The job will be executed out of this directory. It will be made if it does not already exist. |
| `--interval`, `-i` | number, at least 1.0 | `10.0` | Seconds between checks. |
| `--n-proc`, `-np` | integer | `1` | Parallel processes to use in executing tasks (such as running Monte Carlo or status file proccessing for the Dojo process). Be a good citizen. It is easy to abuse this command. Only use what resouces you absolutely need. |
| `--verbose`, `-v` | count | `0` | Increase verbosity (can be repeated, e.g., -vv for DEBUG). |
| `--quiet`, `-q` | count | `0` | Decrease verbosity (can be repeated, e.g., -qq for ERROR). |

### `mujoco-mojo run optimization`

Execute an automated Design Optimization study.

This command uses Optuna to intelligently navigate the search space defined by `model.design_float` and `model.design_categorical` calls within your generator.

```bash
mujoco-mojo run optimization [OPTIONS]
```

**Options**

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--generator`, `-g` | text | required | Path to generator (e.g. 'sim.gen') |
| `--objective`, `-ob` | text | required | Objective function path to score the model (e.g. 'sim.score') |
| `--runtime`, `-r` | text | none | Runtime path to use to run dynamics (e.g. 'sim.run') |
| `--workdir`, `-w` | path | `mojo-models` | Workspace directory. The job will be executed out of this directory. It will be made if it does not already exist. |
| `--n-trial`, `-nt` | integer | `100` | Number of trials to be performed in the job. |
| `--n-proc`, `-np` | integer | `1` | Parallel processes to use in executing tasks (such as running Monte Carlo or status file proccessing for the Dojo process). Be a good citizen. It is easy to abuse this command. Only use what resouces you absolutely need. |
| `--timeout`, `-to` | number | none | Stop searching for new design parameters after N seconds have elapsed. |
| `--study-name`, `-sn` | text | `mojo-study` | Unique identifier for the Optuna study. Useful for resuming or tracking in a database. |
| `--direction`, `-d` | one of `minimize`, `maximize` | `minimize` | The optimization goal. |
| `--sampler`, `-sm` | one of `tpe`, `cmaes`, `random`, `nsgaii`, `nsgaiii`, `qmc`, `gp`, `brute` | `tpe` | The search algorithm to use (e.g., 'tpe' for Bayesian, 'cmaes', or 'random'). |
| `--storage` / `--no-storage` | flag | `--storage` | Whether or not to use database storage. Required for multi-process optimization. |
| `--resume` / `--no-resume` | flag | `--resume` | Resume from previous state on disk |
| `--seed`, `-s` | integer | none | Seed to use for the job. |
| `--evals-per-trial` | integer | `1` | Number of evaluations (different seeds) per trial to average. |
| `--refine-search-factor` | number | none | Shrink search bounds by this factor on resume (0.1 = aggressive). |
| `--prune-failed-trials` / `--no-prune-failed-trials` | flag | `--prune-failed-trials` | Immediately stop trials that hit physics instabilities. |
| `--clean-workdir` / `--no-clean-workdir` | flag | `--no-clean-workdir` | Delete the workdir before running (mutually exclusive with --resume) |
| `--model-config-name`, `-mcn` | text | none | Name for model dump file (e.g. 'model_config.json') |
| `--xml-name`, `-xml` | text | `model.xml` | Name for XML file (e.g. 'model.xml') |
| `--overrides`, `-o` | path | none | File which contains NamedValue overrides to use in all trials. |
| `--arg`, `-a` | text, repeatable | none | Positional arg passed to the `generator`, the runtime, and the objective. Repeat for multiple values (e.g., --arg high_friction --arg 1.5). Values are smart-parsed (e.g., '1.5' becomes a float and 'false' a bool). All of those functions get the same values, so each must accept them. |
| `--kwarg`, `-k` | text, repeatable | none | Keyword arg (key=value) passed to the `generator`, the runtime, and the objective. Each function receives only the keywords it accepts, and a keyword that none of them accept is an error. Example: --kwarg mode='fast' --kwarg complexity=10. Strings with special characters should be single-quoted inside the double quotes. |
| `--verbose`, `-v` | count | `0` | Increase verbosity (can be repeated, e.g., -vv for DEBUG). |
| `--quiet`, `-q` | count | `0` | Decrease verbosity (can be repeated, e.g., -qq for ERROR). |

## `mujoco-mojo settings`

Manage global mujoco-mojo settings at `~/.mujoco-mojo/settings.toml`.

```bash
mujoco-mojo settings [OPTIONS] COMMAND [ARGS]...
```

**Commands**

| Command | What it does |
| :--- | :--- |
| [`mujoco-mojo settings init`](#mujoco-mojo-settings-init) | Initialize a settings file with defaults. |
| [`mujoco-mojo settings show`](#mujoco-mojo-settings-show) | Display settings. |
| [`mujoco-mojo settings set`](#mujoco-mojo-settings-set) | Update a setting. |
| [`mujoco-mojo settings reset`](#mujoco-mojo-settings-reset) | Reset settings back to their defaults. |

### `mujoco-mojo settings init`

Initialize a settings file with defaults.

Writes `~/.mujoco-mojo/settings.toml` (or, with **--project**, `./.mujoco-mojo/settings.toml`) plus a **settings.schema.json** and **.taplo.toml** colocated in the same directory, for TOML editor intellisense. Safe to re-run any time to refresh the schema, e.g. after upgrading mujoco-mojo. A project file is meant to hold only the specific keys that differ from the global settings (e.g. per-project SLURM extras or force-scaling), not a full copy - and gets its own self-contained schema, independent of the global one, so intellisense keeps working even when only the project directory is visible to your editor (e.g. opened over SSH/SSHFS without the home directory mounted).

```bash
mujoco-mojo settings init [OPTIONS]
```

**Options**

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--force`, `-f` | flag | off | Overwrite an existing settings file (will not overwrite existing settings). |
| `--project`, `-p` | flag | off | Initialize the project-local settings file (./.mujoco-mojo/settings.toml, in the current directory) instead of the global one. |

### `mujoco-mojo settings show`

Display settings.

By default, resolves values from all sources in priority order (environment variables, project settings file, global settings file, then defaults) and shows the resulting effective settings, with the API key masked. Pass **--scope project** or **--scope global** to instead show the raw, unmerged contents of just that one file (also masked).

```bash
mujoco-mojo settings show [OPTIONS]
```

**Options**

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--scope`, `-s` | one of `effective`, `project`, `global` | `effective` | Which settings to display. |

### `mujoco-mojo settings set`

Update a setting.

Example: `mujoco-mojo settings set dojo.sensai.enabled true`

Add **--project** to write only the changed key into this project's local override file, leaving everything else there untouched.

```bash
mujoco-mojo settings set [OPTIONS] KEY VALUE
```

**Arguments**

| Argument | Type | Description |
| :--- | :--- | :--- |
| `KEY` | text | Dotted key path (e.g. `dojo.sensai.enabled`) |
| `VALUE` | text | Value to assign. Integers, floats, and **True**/**False** are auto-parsed. |

**Options**

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--project`, `-p` | flag | off | Write to the project-local settings file (the nearest .mujoco-mojo/settings.toml in this or a parent directory, else a new one in ./.mujoco-mojo/) instead of the global one. |

### `mujoco-mojo settings reset`

Reset settings back to their defaults.

Without **--project**: overwrites every value in `~/.mujoco-mojo/settings.toml` with its default (comments you've added by hand are kept). With **--project**: deletes the project-local override file entirely, since it's meant to hold only a small, deliberate diff, not a full copy of every setting.

```bash
mujoco-mojo settings reset [OPTIONS]
```

**Options**

| Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--project`, `-p` | flag | off | Delete the project-local settings file (the nearest .mujoco-mojo/settings.toml in this or a parent directory) instead of resetting the global one. |

## `mujoco-mojo docs`

Find the user guides that ship with this version of mujoco-mojo.

```bash
mujoco-mojo docs [OPTIONS] COMMAND [ARGS]...
```

**Commands**

| Command | What it does |
| :--- | :--- |
| [`mujoco-mojo docs path`](#mujoco-mojo-docs-path) | Print the folder that holds the user guides. |

### `mujoco-mojo docs path`

Print the folder that holds the user guides.

The guides are plain markdown written from the documentation site, so they match the installed version and need no network. Only the path is printed, for scripts and coding assistants to use.

```bash
mujoco-mojo docs path [OPTIONS]
```
