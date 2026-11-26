# Mojo Reloaded

!!! abstract

    **Mojo Reloaded** is the definitive rapid prototyping tool for MuJoCo Mojo. It allows you to modify your model architecture and physics logic on the fly without ever closing your visualizer. By tightening the feedback loop between code changes and visual results, Reloaded transforms the development process from "Compile and Wait" to "Save and See."

---

## Getting Started

To launch a development session, use the `reloaded` command from the CLI. You must provide the module path to your generator function.

``` bash linenums="0"
mujoco-mojo reloaded --generator my_sim.Experiment.generate
```

### Command Interface

The `reloaded` command is highly flexible, allowing you to specify different viewers, initial seeds, and even pass custom arguments to your scripts.

| Argument           | Shortcut | Description                                                                                                                                                                                                                                                                                                                                       |
| :----------------- | :------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `--help`           |          | Describes all available arguments. Used on its own.                                                                                                                                                                                                                                                                                               |
| `--generator`      | `-g`     | Import path to your `generate` function.                                                                                                                                                                                                                                                                                                          |
| `--config`         | `-c`     | Path to a saved `model_config.json`. Mutually exclusive with `--generator`.                                                                                                                                                                                                                                                                       |
| `--runtime`        | `-r`     | Optional import path to your `runtime` function.                                                                                                                                                                                                                                                                                                  |
| `--workdir`        | `-w`     | Workspace directory for output files (default: `mojo-models`).                                                                                                                                                                                                                                                                                    |
| `--user-interface` | `-ui`    | Choose your viewer: `opengl` (the classic MuJoCo window), `studio` (MuJoCo Studio in a native window), or `web` (MuJoCo Studio in a browser). Defaults to `web` where your MuJoCo build can serve it, and `opengl` where it cannot (the `reloaded.ui` setting).                                                                                   |
| `--gfx`            |          | How the native Studio window is drawn: `default`, `opengl`, `opengl_software`, `vulkan`, or `vulkan_software`. Reads from the `reloaded.gfx` setting. Ignored by `web` and `opengl`.                                                                                                                                                              |
| `--trial-num`      | `-tn`    | Load the random state for a specific trial number (default: `0`).                                                                                                                                                                                                                                                                                 |
| `--seed`           | `-s`     | Set the global seed for stochastic draws.                                                                                                                                                                                                                                                                                                         |
| `--overrides`      | `-o`     | Path to a NamedValue overrides JSON file. Fixes specific distribution draws.                                                                                                                                                                                                                                                                      |
| `--arg`            | `-a`     | Positional argument forwarded to the generator and the runtime. Repeatable.                                                                                                                                                                                                                                                                       |
| `--kwarg`          | `-k`     | Keyword argument (`key=value`) forwarded to the generator and the runtime, each receiving only the keywords it accepts. Repeatable.                                                                                                                                                                                                               |
| `--port`           | `-p`     | Port for the web viewer. Reads from your settings ([`mujoco-mojo settings show`](../../reference/cli.md#mujoco-mojo-settings-show)) if you've set one, `8000` out of the box; if that port's already in use (e.g. [`mujoco-mojo dojo`](../../reference/cli.md#mujoco-mojo-dojo) is already running), the next free one is selected automatically. |

---

## The Terminal UI

Once Reloaded is running, your terminal becomes a command center with a status bar and a row of control buttons at the top, a pane in the middle that shows the log of everything that happens or your conversation with [SensAI](#asking-sensai), and a command line at the bottom. You can trigger reloads and control simulation speed without restarting the process.

### Commands

Type a command and press ++enter++. Press ++tab++ to complete the one you are typing (`explain hel` becomes `explain help`), and use ++up++ and ++down++ to step through earlier commands. With nothing to complete, ++tab++ switches between the log and [SensAI](#asking-sensai).

| Command                             | Action                                                                                                                                                             |
| :---------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ++enter++                           | Repeat the last command (perfect for rapid iteration). On a paused run it steps once instead.                                                                      |
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
| `explain seed 42`                   | Say what a command would do without running it. This is not AI: for that, use `sensai`.                                                                            |
| `sensai how do I seed?`             | Ask [SensAI](#asking-sensai) how to use Mojo. Its answer shows in the pane, in place of the log.                                                                   |
| `sensai`, `log`                     | Show SensAI's conversation, or the log, in the pane.                                                                                                               |
| `sensai compact`                    | Summarize the conversation with SensAI so far.                                                                                                                     |
| `sensai clear`                      | Start a new conversation with SensAI.                                                                                                                              |
| `stop`, `halt`, `abort`             | Abort the run in progress.                                                                                                                                         |
| `help`, `h`, `?`                    | Show every command and key.                                                                                                                                        |
| `quit`                              | Close the viewer and Reloaded. It is the only word that does, so `stop` is the one that ends a run.                                                                |

A one-line hint beside the command line describes what the command you are typing would do. Click the `?` to hide or show it.

### Asking SensAI

With [SensAI](sensai.md) set up, type `sensai` and a question, such as `sensai how do I add a requirement?`. The pane switches from the log to SensAI, and the answer comes from the Mojo docs, usually ending with a link to the page it used (hold ++ctrl++ and click to open it in most terminals). A run can go on meanwhile.

SensAI is not a code assistant. It does not see your project, your code or the run in progress, only the docs.

- **Switching:** the pane's title reads **Log · SensAI**. Click a name, press ++tab++ with nothing to complete, or type `log` or `sensai`, to show it. An answer that comes in while the log shows puts a dot beside SensAI.
- **Asking in SensAI's pane:** the command box is titled **Ask SensAI**, so type the question without `sensai`. A line that is one of Reloaded's commands still runs, and the hint beside the command line says which it will be. Enter on an empty line does nothing there.
- **Follow-up questions:** SensAI remembers the conversation, so you can ask "and in the Dojo?". Once it fills most of the model's context window, SensAI summarizes its earlier part and goes on from the summary (see [long conversations](sensai.md#long-conversations)). `sensai compact` summarizes it now, and `sensai clear` starts over. The bottom edge of the pane shows how much of the context window the conversation takes up, and clicking **compact** there summarizes it.
- It answers one question at a time and names the model that answered.
- A sparkle at the right end of the status bar shows while SensAI is on. Hover it for a reminder that AI can make mistakes.
- With `sensai.features.docs` off, SensAI says so.
- `explain` is not AI: it only describes Reloaded's own commands.

### Locations in the Log

Anything your code logs with Python's `logging` ends with the file and line that logged it, such as `src/my_sim/robot.py:42`, flush with the right edge of the log.

- A long message wraps, and the location goes on its last row, or on a row of its own if there is no room beside the end of the message.
- The path is relative to the folder you launched from when the file is inside it.
- Click the location to copy it with the full path, so it works from any folder. Paste it into your editor's quick open to jump straight there (++ctrl+p++ in VS Code).

Messages from Reloaded itself and anything printed with `print` have no location.

### Controlling a Run

While a run is going you can `pause` it, `step` it, carry it on with `run`, and change its speed with `speed 0.5`. A paused run is carried on by `run 2` at that speed. `stop` still aborts it, paused or not.

Speed `0` is manual stepping: the run waits at every step, and each press of ++enter++ (or `step`) lets one through. It is handy for watching a few steps closely.

`run` alone does not let it go, because the speed is still 0. Give it a speed, as in `run 1`, or `speed inf` to run as fast as the machine can.

To have a run pause by itself, give `run` a target:

- `run until time 2.5` pauses when the simulation time reaches 2.5.
- `run until step 500` pauses when the run has taken 500 steps.
- `run 0.5 until step 500` puts a speed first.

A target is a reading since the run began, not a distance from now, and time uses whatever unit your model does. You can set one on a run that is already going or paused, but one that has already been passed is refused.

When the run reaches its target, the log says where it stopped, such as `reached step 500 (time 1, step 500)`, and the status bar shows `PAUSED`. `run` carries on from there. A target applies to one run only.

Pausing holds the run inside `rm.step(...)`, the call your runtime already makes each step, so it works for any runtime that steps through the [`RuntimeManager`][mujoco_mojo.runtime.runtime_manager.RuntimeManager]. That is also how forces, recording, and the force arrows reach the viewer.

A runtime that calls `mujoco.mj_step` on its own can be stopped but not paused.

### Keys and Clicks

| Key     | Action                                       |
| :------ | :------------------------------------------- |
| ++f2++  | Generate only.                               |
| ++f3++  | Generate and run, or carry a paused run on.  |
| ++f12++ | Pause the run, or resume it if it is paused. |
| ++f4++  | Turn watching on or off.                     |
| ++f7++  | Turn recording on or off.                    |
| ++f8++  | Show or hide the hint.                       |
| ++f9++  | Show help.                                   |
| ++esc++ | Stop the run in progress.                    |
| ++f10++ | Quit.                                        |

The buttons under the status bar (Gen, Run, Pause, Step, and Stop) do the same as the keys. Each has an icon and shows its key beside the label. A button that does not apply right now is dimmed, so Stop only lights up during a run and Run lights up again when a run is paused.

You can also click a value in the status bar:

- Click the seed, trial, or speed to type a new one. ++enter++ applies it and ++esc++ cancels.
- Click watch or record to switch it on or off.

Closing the viewer window also closes Reloaded.

### Copying from the Log

Drag across the log with the mouse to select text. Every line the drag touches is highlighted in full. Letting go copies those lines to the clipboard and says how many were copied, and ++ctrl+c++ copies again. This is how to pass a log on, for example when reporting a problem.

The gap that pushes a line's location to the right edge is not copied: you get the message, two spaces, and the location.

Clicking a location without dragging copies just its full path and line.

### Watching for Changes

With `watch` on, saving a `*.py` file reloads with the last command. Reloaded watches:

- the folder it was started in
- the folders of the project modules your generator and runtime import, which are the files a reload picks up. A module that is first imported later is watched from then on.

Folders that nothing imports, such as virtual environments and build trees, are left alone. That keeps the number of watches small, because your operating system has a limit that your editor shares.

If watching does stop, Reloaded says why in the log and turns `watch` off.

### If Reloaded Crashes

The Studio viewers run compiled code, and if that code crashes it takes Reloaded down with it. Reloaded then:

- puts your terminal back as it was, so you do not have to close the shell
- says where it saved the Python stack of every thread, `crash.log` in your workdir

[`mujoco-mojo reloaded`](../../reference/cli.md#mujoco-mojo-reloaded) does this by running your session in a child process and waiting for it. Two `mujoco-mojo` processes show up as a result, and it starts about a second slower.

### The Studio Viewers

With `-ui studio` or `-ui web` the model is shown in MuJoCo Studio, and Studio's own buttons control the run the same way the terminal does, so the two always agree:

| In Studio        | Same as in the terminal                                                                                                                                                           |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Pause and play   | `pause` and `run`. The terminal's status bar changes too, and so does Studio's button when you pause in the terminal.                                                             |
| Step             | `step`.                                                                                                                                                                           |
| Speed slider     | `speed`. The slider runs from 0.1% to 100% of real time, so a speed above real time, `inf`, and manual stepping all show as 100%. Moving the slider sets a speed up to real time. |
| Reset and Reload | ++enter++: runs the last command again once nothing is running. During a run they only remind you to `stop` it first.                                                             |

Your generator builds the model, so a model file dropped onto Studio is ignored, and Studio's control noise setting has no effect.

If the native window (`-ui studio`) fails to draw on a machine whose display only has software OpenGL, such as a remote desktop, run it with `--gfx opengl_software`, or set `reloaded.gfx`.

Studio opens with its Options and Inspector panels and its status bar showing. To change what shows when it opens, set the `reloaded.studio` options, one for each item in Studio's View menu. The menu still toggles them once Studio is open.

``` toml linenums="0"
[reloaded.studio]
show_console = true
show_inspector = false
```

The options are `show_info`, `show_profiler`, `show_console`, `show_options`, `show_toolbar`, `show_view_gizmo`, `show_status_bar`, and `show_inspector`. They apply to `-ui studio` and `-ui web`, not to `-ui opengl`.

With `-ui web`, the address to open is printed at the top of the log, right after the line that says Reloaded is live. Over SSH it is followed by the command that forwards the port. Reloaded takes the first free port from `--port` upward.

### Changing the Keys

The keys come from the `reloaded.keys` settings, a list for each action. The first key in a list is the one the footer shows, and the others work too.

``` toml linenums="0"
[reloaded.keys]
generate = ["f5", "ctrl+g"]
help = ["f9"]
```

You can also set one from the command line:

``` bash linenums="0"
mujoco-mojo settings set reloaded.keys.generate "f5, ctrl+g"
```

The actions are `generate`, `run`, `pause`, `step`, `watch`, `record`, `explain`, `help`, `stop`, and `quit`. Use lowercase [Textual key names](https://textual.textualize.io/guide/input/#keys) such as `f2`, `ctrl+g`, or `escape`.

- A key can only do one thing.
- A list can be empty to leave an action without a key.
- `pause` is ++f12++ and `step` has no key by default, because no function key is left that an editor terminal passes on. Give it one if you want it.
- Typing `quit` always closes Reloaded.

!!! tip

    A terminal inside an editor hands some keys to the editor before Reloaded sees them. The terminal in VS Code keeps ++f1++, ++f5++, ++f6++, ++f10++, ++f11++, ++ctrl+p++, and ++ctrl+q++ for itself, which is why the defaults lean on other function keys.

---

## Loading a Saved Model Config

As an alternative to calling a generator function, Reloaded can load a previously saved `model_config.json` directly using `--config`. This is useful when you want to inspect the exact model that was used in a specific trial without running any Python generation logic.

``` bash linenums="0"
mujoco-mojo reloaded --config ./results/trial_0042/model_config.json
```

This mode is mutually exclusive with `--generator`.

---

## Inspecting a Specific Trial

When iterating on a stochastic simulation, it is often necessary to reproduce the exact random state of a particular trial. Pass `--trial-num` to seed the session with that trial's distribution draws.

``` bash linenums="0"
# Open trial 42 in the viewer, using the same seed and random draws as the original campaign
mujoco-mojo reloaded -g sim.generate -r sim.runtime --seed 123 --trial-num 42
```

Combined with `--overrides`, you can also lock specific named values to fixed quantities while keeping everything else stochastic, which helps isolate the effect of individual parameters.

---

## Workflow

### MJCF Prototyping

When you are first building your model, you likely don't care about the physics behavior yet, you just want to see if your bodies are aligned and your textures are loading.

1. Launch with only a generator: [`mujoco-mojo reloaded --generator my_mod.generate`](../../reference/cli.md#mujoco-mojo-reloaded).
2. Modify your `generate` function (e.g., change a body's `pos`).
3. Enter `gen` in the terminal.
4. The model regenerates, the module hot-reloads, and the viewer snaps to the new state instantly.

### Physics Prototyping

Once the world looks right, it's time to test your forces. By providing a `--runtime`, you can move from static snapshots to dynamic testing.

1. Launch with both: [`mujoco-mojo reloaded --generator my_mod.gen --runtime my_mod.run`](../../reference/cli.md#mujoco-mojo-reloaded).
2. Modify your physics logic (e.g., increase a spring's stiffness).
3. Enter `run 1.0` (Real-time) or `run 0.5` (Slow-motion).
4. Watch the physics play out. If it's not right, tweak the code and hit ++enter++ to watch it again with the updated logic.

---

!!! success

    Use the **web** UI (`-ui web`) if you want to develop on a machine with no display, such as over an SSH connection. Reloaded prints the address and the command that forwards the viewer's port to your own machine (for example `ssh -L 8000:localhost:8000 user@host`) at the top of its log. Run it on your computer, then open `http://localhost:8000` in your browser.

!!! warning

    The MuJoCo Studio web viewer listens on every network interface of the machine it runs on and has no password. Only use it on a network you trust, or keep the port closed to others and reach it through an SSH tunnel.
