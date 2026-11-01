# Mojo Reloaded

!!! abstract

    **Mojo Reloaded** is the definitive rapid prototyping tool for MuJoCo Mojo. It allows you to modify your model architecture and physics logic on the fly without ever closing your visualizer. By tightening the feedback loop between code changes and visual results, Reloaded transforms the development process from "Compile and Wait" to "Save and See."

---

## Getting Started

To launch a development session, use the `reloaded` command from the CLI. You must provide the module path to your generator function.

```bash linenums="0"
mujoco-mojo reloaded --generator my_sim.Experiment.generate
```

### Command Interface

The `reloaded` command is highly flexible, allowing you to specify different viewers, initial seeds, and even pass custom arguments to your scripts.

| Argument           | Shortcut | Description                                                                                                                                                                                                                                        |
| :----------------- | :------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--help`           |          | Describes all available arguments. Used on its own.                                                                                                                                                                                                |
| `--generator`      | `-g`     | Import path to your `generate` function.                                                                                                                                                                                                           |
| `--config`         | `-c`     | Path to a saved `model_config.json`. Mutually exclusive with `--generator`.                                                                                                                                                                        |
| `--runtime`        | `-r`     | Optional import path to your `runtime` function.                                                                                                                                                                                                   |
| `--workdir`        | `-w`     | Workspace directory for output files (default: `mojo-models`).                                                                                                                                                                                     |
| `--user-interface` | `-ui`    | Choose your viewer: `opengl` (the classic MuJoCo window), `studio` (MuJoCo Studio in a native window), or `web` (MuJoCo Studio in a browser). Defaults to `studio`, or `web` over SSH or with no display (the `reloaded.ui` setting).              |
| `--trial-num`      | `-tn`    | Load the random state for a specific trial number (default: `0`).                                                                                                                                                                                  |
| `--seed`           | `-s`     | Set the global seed for stochastic draws.                                                                                                                                                                                                          |
| `--overrides`      | `-o`     | Path to a NamedValue overrides JSON file. Fixes specific distribution draws.                                                                                                                                                                       |
| `--arg`            | `-a`     | Positional argument forwarded to the generator and the runtime. Repeatable.                                                                                                                                                                        |
| `--kwarg`          | `-k`     | Keyword argument (`key=value`) forwarded to the generator and the runtime, each receiving only the keywords it accepts. Repeatable.                                                                                                                |
| `--port`           | `-p`     | Port for the web viewer. Reads from your settings (`mujoco-mojo settings show`) if you've set one, `8000` out of the box; if that port's already in use (e.g. `mujoco-mojo dojo` is already running), the next free one is selected automatically. |

---

## The Terminal UI

Once Reloaded is running, your terminal becomes a command center with a status bar and a row of control buttons at the top, a log of everything that happens in the middle, and a command line at the bottom. You can trigger reloads and control simulation speed without restarting the process.

### Commands

Type a command and press `ENTER`. Press `TAB` to complete the one you are typing (`explain hel` becomes `explain help`), and use the up and down arrows to step through earlier commands.

| Command                             | Action                                                                                                                                                             |
| :---------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ENTER`                             | Repeat the last command (perfect for rapid iteration). On a paused run it steps once instead.                                                                      |
| `gen`, `g`, `generate`              | Trigger **Generate Only** mode. Useful for MJCF debugging.                                                                                                         |
| `run`, `r`, `runtime`               | Generate and run the `runtime` (only if a `runtime` was provided). Give a speed, as in `run 0.5`, to set it first. On a paused run it carries on.                  |
| `run until time 2.5`                | Run, then pause by itself once the simulation time reaches that reading. It starts a run if none is going, and carries a paused one on.                            |
| `run until step 500`                | The same, but pausing once the run has taken that many steps since it began.                                                                                       |
| `pause`, `p`                        | Hold the run in progress where it is.                                                                                                                              |
| `step`, `step 5`                    | Advance a run by one step, or by that many. A run that is going is paused first.                                                                                   |
| `speed 0.5`, `speed 0`, `speed inf` | Set the playback speed for the next run, or for the one in progress: 1 is real time, `0` steps by hand, and `inf` runs as fast as it can. It does not start a run. |
| `seed 42`                           | Set the seed. `seed none` clears it.                                                                                                                               |
| `trial 3`                           | Set the trial number.                                                                                                                                              |
| `watch`, `w`                        | Turn reloading on or off when your `*.py` files change.                                                                                                            |
| `record`, `rec`                     | Turn telemetry and video recording on or off.                                                                                                                      |
| `dojo`                              | Print the command that opens the Dojo for this session.                                                                                                            |
| `explain seed 42`                   | Say what a command would do without running it. Ending a command with `?` does the same.                                                                           |
| `stop`, `halt`, `abort`             | Abort the run in progress.                                                                                                                                         |
| `help`, `h`, `?`                    | Show every command and key.                                                                                                                                        |
| `quit`                              | Close the viewer and Reloaded. It is the only word that does, so `stop` is the one that ends a run.                                                                |

A one-line hint beside the command line describes what the command you are typing would do. Click the `?` to hide or show it.

Anything your code logs with Python's `logging` ends with the file and line that logged it, such as `src/my_sim/robot.py:42`, flush with the right edge of the log. A long message wraps, and the location goes on its last row, or on a row of its own if there is no room beside the end of the message. The path is relative to the folder you launched from when the file is inside it. Click the location to copy it with the full path, so it works from any folder, then paste it into your editor's quick open to jump straight there (`Ctrl+P` in VS Code). Messages from Reloaded itself and anything printed with `print` have no location.

### Controlling a Run

While a run is going you can `pause` it, `step` it, carry it on with `run`, and change its speed with `speed 0.5`. A paused run is carried on by `run 2` at that speed. `stop` still aborts it, paused or not.

Speed `0` is manual stepping: the run waits at every step and each press of `ENTER` (or `step`) lets one through, which is handy for watching a few steps closely. `run` alone does not let it go, because the speed is still 0. Give it a speed, as in `run 1`, or `speed inf` to run as fast as the machine can. Whenever a run is paused, `stop` ends it.

To have a run pause by itself, give `run` a target: `run until time 2.5` pauses when the simulation time reaches 2.5, and `run until step 500` pauses when the run has taken 500 steps. Both are readings since the run began, not distances from now, and they use whatever time unit your model does. You can put a speed first (`run 0.5 until step 500`), set a target on a run that is already going or paused, and a target that has already been passed is refused. The log says where the run stopped, such as `reached step 500 (time 1, step 500)`, and `run` carries on from there. A target applies to one run only. The status bar shows `PAUSED` while a run is held.

Pausing holds the run inside `rm.step(...)`, the call your runtime already makes each step, so it works for any runtime that steps through the `RuntimeManager`. That is also how forces, recording, and the force arrows reach the viewer. A runtime that calls `mujoco.mj_step` on its own can be stopped but not paused.

### Keys and Clicks

| Key   | Action                                       |
| :---- | :------------------------------------------- |
| `F2`  | Generate only.                               |
| `F3`  | Generate and run, or carry a paused run on.  |
| `F12` | Pause the run, or resume it if it is paused. |
| `F4`  | Turn watching on or off.                     |
| `F7`  | Turn recording on or off.                    |
| `F8`  | Show or hide the hint.                       |
| `F9`  | Show help.                                   |
| `Esc` | Stop the run in progress.                    |
| `F10` | Quit.                                        |

The buttons under the status bar (Gen, Run, Pause, Step, and Stop) do the same as the keys. Each has an icon and shows its key beside the label. A button that does not apply right now is dimmed, so Stop only lights up during a run and Run lights up again when a run is paused. You can also click a value in the status bar. Clicking the seed, trial, or speed lets you type a new one (`ENTER` applies it and `Esc` cancels), and clicking watch or record switches it on or off.

Closing the viewer window also closes Reloaded.

### Changing the Keys

The keys come from the `reloaded.keys` settings, a list for each action. The first key in a list is the one the footer shows, and the others work too.

```toml linenums="0"
[reloaded.keys]
generate = ["f5", "ctrl+g"]
help = ["f9"]
```

You can also set one from the command line:

```bash linenums="0"
mujoco-mojo settings set reloaded.keys.generate "f5, ctrl+g"
```

The actions are `generate`, `run`, `pause`, `step`, `watch`, `record`, `explain`, `help`, `stop`, and `quit`. `pause` is `F12` and `step` has no key by default, because no function key is left that an editor terminal passes on, so give it one if you want it. Use lowercase [Textual key names](https://textual.textualize.io/guide/input/#keys) such as `f2`, `ctrl+g`, or `escape`. A key can only do one thing, and a list can be empty to leave an action without a key. Typing `quit` always closes Reloaded.

!!! tip

    A terminal inside an editor hands some keys to the editor before Reloaded sees them. The terminal in VS Code keeps `F1`, `F5`, `F6`, `F10`, `F11`, `Ctrl+P`, and `Ctrl+Q` for itself, which is why the defaults lean on other function keys.

---

## Loading a Saved Model Config

As an alternative to calling a generator function, Reloaded can load a previously saved `model_config.json` directly using `--config`. This is useful when you want to inspect the exact model that was used in a specific trial without running any Python generation logic.

```bash linenums="0"
mujoco-mojo reloaded --config ./results/trial_0042/model_config.json
```

This mode is mutually exclusive with `--generator`.

---

## Inspecting a Specific Trial

When iterating on a stochastic simulation, it is often necessary to reproduce the exact random state of a particular trial. Pass `--trial-num` to seed the session with that trial's distribution draws.

```bash linenums="0"
# Open trial 42 in the viewer, using the same seed and random draws as the original campaign
mujoco-mojo reloaded -g sim.generate -r sim.runtime --seed 123 --trial-num 42
```

Combined with `--overrides`, you can also lock specific named values to fixed quantities while keeping everything else stochastic, which helps isolate the effect of individual parameters.

---

## Workflow

### MJCF Prototyping

When you are first building your model, you likely don't care about the physics behavior yet, you just want to see if your bodies are aligned and your textures are loading.

1. Launch with only a generator: `mujoco-mojo reloaded --generator my_mod.generate`.
2. Modify your `generate` function (e.g., change a body's `pos`).
3. Enter `gen` in the terminal.
4. The model regenerates, the module hot-reloads, and the viewer snaps to the new state instantly.

### Physics Prototyping

Once the world looks right, it's time to test your forces. By providing a `--runtime`, you can move from static snapshots to dynamic testing.

1. Launch with both: `mujoco-mojo reloaded --generator my_mod.gen --runtime my_mod.run`.
2. Modify your physics logic (e.g., increase a spring's stiffness).
3. Enter `run 1.0` (Real-time) or `run 0.5` (Slow-motion).
4. Watch the physics play out. If it’s not right, tweak the code and hit `ENTER` to watch it again with the updated logic.

---

!!! success

    Use the **web** UI (`-ui web`) if you want to develop on a machine with no display, such as over an SSH connection. Forward the viewer's port to your own machine (for example `ssh -L 8000:localhost:8000 user@host`) and open `http://localhost:8000` in your browser.

!!! warning

    The MuJoCo Studio web viewer listens on every network interface of the machine it runs on and has no password. Only use it on a network you trust, or keep the port closed to others and reach it through an SSH tunnel.
