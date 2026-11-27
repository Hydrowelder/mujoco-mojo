# Dojo Dashboard

!!! abstract

    The **Dojo Dashboard** is where your data is mastered. It is a high-performance, web-based analytics suite designed from the ground up to turn raw simulation results into actionable insights.

    Far from being a simple static viewer, Dojo is a **collaborative platform**. It features a responsive design (mobile-ready), native light/dark mode support, and built-in security for sharing your progress with colleagues across a network.

---

## Getting Started

Dojo is launched via the CLI and points directly at your specified workdir. It reads the internal `job_status.json` to understand the context of your simulation.

### The CLI Command

To start the dashboard, simply provide the path to your work directory:

``` bash linenums="0"
mujoco-mojo dojo ./mojo-models
```

| Argument     | Shortcut | Default         | Description                                                                                               |
| :----------- | :------- | :-------------- | :-------------------------------------------------------------------------------------------------------- |
| `workdir`    | _N/A_    | **Required**    | The workspace directory containing the simulation results.                                                |
| `--host`     | `-h`     | `127.0.0.1`[^1] | The IP address to serve the dashboard on.                                                                 |
| `--port`     | `-p`     | `8000`[^1]      | The port number for the web server. If it's already in use, the next free port is selected automatically. |
| `--password` | `-pw`    | _None_[^1]      | Enables Basic Auth protection.                                                                            |
| `--n-proc`   | `-np`    | `1`[^1]         | Processes used for background status file processing.                                                     |

---

## The Page Frame

Every page of the Dojo shares the same frame, so you always know where you are and how the job is doing.

[^1]: Reads from your settings ([`mujoco-mojo settings show`](../../../reference/cli.md#mujoco-mojo-settings-show)) if you've set one; the value shown is the out-of-the-box default.

<figure markdown="span">
    ![Dojo toolbar](../../../assets/user-guides/light-page-frame.jpg#only-light){ width="85%" height="auto" }
    ![Dojo toolbar](../../../assets/user-guides/dark-page-frame.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The header of every page: the tool tabs, the toolbar, and the job's owner and workdir.</figcaption>
</figure>

**Toolbar:** From left to right:

| Control            | What it does                                                                                                                   |
| :----------------- | :----------------------------------------------------------------------------------------------------------------------------- |
| **Auto** / **Off** | Turns the live updates on or off. With them on, the page follows the job as trials finish.                                     |
| Speaker            | Mutes or unmutes the completion chime. The Dojo starts muted, and your browser remembers the choice.                           |
| Theme buttons      | Light theme, follow the system, or dark theme.                                                                                 |
| Bell               | The notification history, with a badge for messages you have not read.                                                         |
| Gear               | The [settings panel](#settings).                                                                                               |
| Arrows             | Fullscreen, which gives the page the whole window. ++esc++ leaves it. `dojo.default_to_fullscreen` starts every page that way. |

**Job card:** Under the toolbar, the **Owner** who started the job and the **Workdir** it ran in. Click either to copy it. The workdir copies as the path of `job_status.json`, which an editor such as VS Code can jump straight to.

**Footer:** A pill shows **Live** (green) while the Dojo is connected to its server and **Down** (red) when it is not, with how long ago the last update arrived, or **Final Data** once the job is done. Beside it, the installed version opens the [What's Changed](#whats-changed) window, and the sparkle button at the bottom right opens [SensAI](sensai.md) when it is enabled.

---

## Design Philosophy

Dojo isn't just a local tool; it is designed for the modern, distributed engineering workflow.

### Data Sharing and Collaboration

Dojo is built on a "Share First" principle. By serving the dashboard on your local network, anyone with the URL can view the live progress of a Monte Carlo run.

- **The Host Flag:** To make Dojo shareable or viewable on a mobile device, launch with `--host 0.0.0.0`. Mojo will automatically detect your local IP and provide a "Mobile URL" in the terminal.
- **Basic Auth:** If you are sharing results on a public-facing server, use the `--password` flag (or the `dojo.password` setting). This enables a login screen where users can enter any username and your specified password to keep your data private.
- **Read-only settings:** the settings panel can only be changed from the machine running the Dojo. Anyone else who opens it sees the settings but cannot edit them.

### Responsive and Universal UI

Dojo is fully responsive. Whether you are checking a 10,000-trial run from a 4K monitor in the lab or on your phone during a boring meeting, the UI adapts.

- **Light/Dark Mode:** The dashboard automatically respects your system's theme settings, ensuring that your telemetry plots and 3D mosaics look beautiful in any environment.
- **Mobile-Optimized:** Navigation and "Individual Trial" views are designed to be touch-friendly, allowing you to scrub through simulation data effortlessly.

### Offline-First Reliability

Dojo is a **zero-dependency** suite. All assets, scripts (including Plotly.js), and styles are bundled locally within the package.

- **Air-Gapped Support:** Dojo does not require an internet connection or external CDNs to function. This guarantees that your visualization tools will work perfectly on isolated compute clusters or in secure lab environments.
- **Low Latency:** Because all resources are served locally, the interface remains snappy and responsive regardless of your network's external bandwidth.

---

## Tools Overview

Dojo is split into environments depending on your current needs:

### Monitor

**Real-Time Oversight.** Designed for use while a job is actively running.

- **Live Tracking:** Dynamic progress bars and color-coded status cards.
- **Success/Failure/Error Analytics:** Every trial is a success, a requirement failure or an error, with a timeline of how the job progressed.
- **Deep-Linking:** One-click navigation from a status card directly to the trial's telemetry.

### Mosaic

**Advanced Telemetry Analysis.** Designed for deep-dives and regression testing.

- **Hardware-Accelerated:** Smooth interaction with millions of data points via Plotly.js.
- **Dynamic Versus Mode:** Overlay current telemetry against previous trials for instant regression testing.
- **State Persistence:** Share your exact view configuration (zoom, filters, selected signals) via a single compressed URL.
- **Trial Details:** The trial's animation, where its random draws fell in their [distributions](trial-details.md#distributions), its [requirements](trial-details.md#trial-execution) and its [logs](trial-details.md#logs), below the plot.
- **[Signal Lab](signal-lab.md):** Build new signals from the ones you recorded, after the run, with a graph of filters.

### Morph

**Optimization History.** Appears only for [optimization](../optimization/optimization.md) jobs. [Morph](morph.md) embeds Optuna Dashboard so you can study how the search converged.

### SensAI

**An Assistant for the Dashboard.** Ask about your job, change your plot, or find out how to do something in Mojo, in plain language, in the [SensAI chat](sensai.md). [SensAI](../sensai/sensai.md) is optional and needs a language model of your choice.

---

## Settings

The gear in the toolbar opens the settings panel, an editor for your global settings file (`~/.mujoco-mojo/settings.toml`). It reads the same settings as [`mujoco-mojo settings`](../../../reference/cli.md#mujoco-mojo-settings), so a change made here applies to the command line too.

<figure markdown="span">
    ![Settings panel](../../../assets/user-guides/light-settings-panel.jpg#only-light){ width="85%" height="auto" }
    ![Settings panel](../../../assets/user-guides/dark-settings-panel.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The settings panel, opened with the gear in the toolbar, with its sections on the left and the description of the field under the mouse at the bottom.</figcaption>
</figure>

- **Sections and search:** the left side lists a section for each group of settings (general, visualization, Dojo, Reloaded, SensAI, run and SLURM). The search box filters every section by the name and the description of a setting.
- **Hints:** hover over or edit a field and the bar at the bottom of the panel describes it, including the values it accepts.
- **Widgets that fit the setting:** a switch for a yes/no setting, a list for a choice, a masked box for a password or a key, a color field that accepts a name or a hex value, and an editable list for entries such as the SensAI models.
- **Reset:** every field that differs from its default has a small button to put it back. **Restore Defaults** at the top resets them all.
- **Save:** changes are only written when you press **Save**, and **Cancel** discards them. A field with an invalid value is highlighted and blocks saving until you fix it.

!!! note "Project settings"

    A project can have its own `.mujoco-mojo/settings.toml`, which takes priority over the global file. The panel edits the global file. Write to the project file with [`mujoco-mojo settings set --project KEY VALUE`](../../../reference/cli.md#mujoco-mojo-settings-set) or edit it by hand.

---

## What's Changed

The version in the footer opens a window that lists the release notes, newest first, with a menu of versions on the left. A badge on the button pulses when a newer release exists. The window opens by itself the first time you launch after an update, when the changelog has entries you have not seen, and those entries are marked **New**. Turn that off from inside the window, or with `dojo.show_whats_changed`.

The Dojo fetches the changelog from GitHub. If it cannot reach GitHub it falls back to a saved copy, or the one bundled with your install, and tells you so.

---

!!! success

    Dojo is now live! Now that you have the interface running, move on to the [**Monitor**](monitor.md) tool to learn how to track your job's progress in real-time.
