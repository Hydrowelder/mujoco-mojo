# Initializing a New Project

!!! abstract

    The `mujoco-mojo init` command scaffolds a new project in the current directory, providing ready-to-run starter files for Monte Carlo campaigns or optimization studies.

---

## Usage

```bash linenums="0"
mujoco-mojo init [--optimizer]
```

With no flags, the command generates a standard Monte Carlo project. Pass `--optimizer` to include an `objective` function stub for use with `mujoco-mojo run optimization`.

---

## Generated Files

Running `mujoco-mojo init` produces three files in the current directory:

| File            | Purpose                                                 |
| --------------- | ------------------------------------------------------- |
| `simulation.py` | Simulation stubs: `UserData`, `generate`, and `runtime` |
| `run.sh`        | Pre-configured shell script to launch the campaign      |
| `reloaded.sh`   | Shell script to open the interactive viewer             |

Both shell scripts are made executable and resolve their paths relative to their own location, so they can be invoked from any working directory.

It also creates a `.mujoco-mojo/` folder holding the project's settings file (`settings.toml`) and a schema that gives TOML-aware editors completion for it. If you have no global settings file yet, `init` asks whether to create one with the defaults. See [Where the Project File Lives](running-jobs/running-jobs.md#where-the-project-file-lives) for how project settings are found.

### Choosing the Viewer

`reloaded.sh` does not name a viewer. Reloaded takes it from the `reloaded.ui` setting, which defaults to the right one for the machine you run it on:

| Machine                                  | Default viewer           |
| ---------------------------------------- | ------------------------ |
| A desktop session                        | `studio` (native window) |
| An SSH session, or Linux with no display | `web` (in a browser)     |

A machine reached over SSH gets the browser viewer even when X forwarding is on, because that is the better experience over a network link. Because nothing is written into the script, the same project works on your desktop and on a remote machine. To pin a viewer, set `reloaded.ui` in your settings, or add `-ui studio` or `-ui web` to the command in `reloaded.sh`.

---

## Monte Carlo (default)

```bash linenums="0"
mujoco-mojo init
```

`simulation.py` will contain stubs for `generate` and `runtime`. `run.sh` will call `mujoco-mojo run monte-carlo`.

---

## Optimization

```bash linenums="0"
mujoco-mojo init --optimizer
```

`simulation.py` will additionally contain an `objective` stub. `run.sh` will call `mujoco-mojo run optimization`.

---

## Next Steps

After running `init`, fill in your `generate` and `runtime` functions, then launch your campaign:

```bash linenums="0"
bash run.sh
```

!!! tip

    Use `reloaded.sh` during development to get rapid visual feedback on your model without running a full campaign.

    ```bash linenums="0"
    bash reloaded.sh
    ```
