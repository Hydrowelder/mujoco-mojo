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

| Argument           | Description                                                               |
|:-------------------|:--------------------------------------------------------------------------|
| `--help`           | Describes all available arguments. Used on its own.                       |
| `--generator`      | **(Required)** Import path to your `MojoGenerate` function.               |
| `--runtime`        | Optional import path to your `MojoRuntime` function.                      |
| `--user-interface` | Choose your viewer: `opengl` (native), `viser`, or `mjviser` (web-based). |
| `--seed`           | Set the global seed for stochastic draws.                                 |
| `--port`           | Port for the web-based viewers (default: `8080`).                         |

---

## Interactive Controls

Once Reloaded is running, your terminal becomes an interactive command center. You can trigger reloads and control simulation speed without restarting the process.

| Command              | Action                                                                                       |
|:---------------------|:---------------------------------------------------------------------------------------------|
| `ENTER`              | Repeat the last command (perfect for rapid iteration).                                       |
| `gen`                | Trigger **Generate Only** mode. Useful for MJCF debugging.                                   |
| `1.0` (or any float) | Trigger **Runtime** mode at the specified playback speed (only if a `runtime` was provided). |
| `exit`               | Safely close the server and visualizer.                                                      |

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
3. Enter a speed like `1.0` (Real-time) or `0.5` (Slow-motion).
4. Watch the physics play out. If it’s not right, tweak the code and hit `ENTER` to watch it again with the updated logic.

---

!!! success
    Use the **Viser** UI (`--ui viser`, available in the `mujoco-mojo[reloaded]` dependency group) if you want to develop on one machine and view the simulation on another (such as on an SSH connection, phone, or tablet) via your local network. Reloaded will automatically display the local and mobile URLs in your terminal.
