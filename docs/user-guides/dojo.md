# Dojo Dashboard

!!! abstract
    The **Dojo Dashboard** is where your data is mastered. It is a high-performance, web-based analytics suite designed from the ground up to turn raw simulation results into actionable insights.

    Far from being a simple static viewer, Dojo is a **collaborative platform**. It features a responsive design (mobile-ready), native light/dark mode support, and built-in security for sharing your progress with colleagues across a network.

---

## Getting Started

Dojo is launched via the CLI and points directly at your specified workdir. It reads the internal `job_status.json` to understand the context of your simulation.

### The CLI Command

To start the dashboard, simply provide the path to your work directory:

```bash linenums="0"
mujoco-mojo dojo ./mojo-models
```

| Argument     | Shortcut | Default      | Description                                                |
|:-------------|:---------|:-------------|:-----------------------------------------------------------|
| `workdir`    | *N/A*    | **Required** | The workspace directory containing the simulation results. |
| `--host`     | `-h`     | `127.0.0.1`  | The IP address to serve the dashboard on.                  |
| `--port`     | `-p`     | `8000`       | The port number for the web server.                        |
| `--password` | `-pw`    | *None*       | Enables Basic Auth protection.                             |
| `--n-proc`   | `-np`    | `1`          | Processes used for background status file processing.      |

---

## Design Philosophy

Dojo isn't just a local tool; it is designed for the modern, distributed engineering workflow.

### Data Sharing and Collaboration

Dojo is built on a "Share First" principle. By serving the dashboard on your local network, anyone with the URL can view the live progress of a Monte Carlo run.

- **The Host Flag:** To make Dojo shareable or viewable on a mobile device, launch with `--host 0.0.0.0`. Mojo will automatically detect your local IP and provide a "Mobile URL" in the terminal.
- **Basic Auth:** If you are sharing results on a public-facing server, use the `--password` flag. This enables a login screen where users can enter any username and your specified password to keep your data private.

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

Dojo is split into two primary environments depending on your current needs:

### Monitor

**Real-Time Oversight.** Designed for use while a job is actively running.

- **Live Tracking:** Dynamic progress bars and color-coded status cards.
- **Success/Failure Analytics:** Built-in checks to identify "empty" vs "failed" runs.
- **Deep-Linking:** One-click navigation from a status card directly to the trial's telemetry.

### Mosaic

**Advanced Telemetry Analysis.** Designed for deep-dives and regression testing.

- **Hardware-Accelerated:** Smooth interaction with millions of data points via Plotly.js.
- **Dynamic Versus Mode:** Overlay current telemetry against previous trials for instant regression testing.
- **State Persistence:** Share your exact view configuration (zoom, filters, selected signals) via a single compressed URL.

---

## Plot Notes

The trial viewer supports freeform notes anchored to specific points on a plot.

- **Add a note:** Middle-click anywhere on the plot area. The Notes panel opens with the cursor's data coordinates pre-filled.
- **Edit or delete:** Open the Notes panel (the speech-bubble icon in the sidebar) and use the edit/delete controls next to each note.
- **Jump to a note:** Click the note's coordinates in the list to zoom the plot to that location.
- **Close the panel:** Left-click anywhere outside the Notes panel, or press ++esc++.

Notes are persisted in the trial's saved configuration and are included when sharing a view via the share URL.

---

!!! success
    Dojo is now live! Now that you have the interface running, move on to the **Monitor** tool to learn how to track your job's progress in real-time.
