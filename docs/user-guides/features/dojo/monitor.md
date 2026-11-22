# Monitor

!!! abstract

    The **Monitor** tool is your real-time oversight interface. It transforms the abstract numbers of a multi-process simulation into a dynamic dashboard. The Monitor keeps you informed of the health and progress of every single trial, whether the job runs on your laptop, across many processes, or as an array on a SLURM cluster.

---

<figure markdown="span">
    ![Monitor dashboard view](../../../assets/user-guides/light-monitor-view.jpg#only-light){ width="85%" height="auto" }
    ![Monitor dashboard view](../../../assets/user-guides/dark-monitor-view.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>A preview of the <b>Monitor</b> page showing a completed progress bar, job statistics, the timeline of the job, and links to <b>Mosaic</b> to assess individual trials.</figcaption>
</figure>

## Real-Time Oversight

The Monitor acts as a nexus for overseeing your [`mujoco-mojo run`](../../../reference/cli.md#mujoco-mojo-run) jobs. It works by monitoring the trial status files in your workspace and reflecting the global state of the simulation. The page updates itself while the job runs (the **Auto** button in the toolbar pauses that), and the footer shows **Live** while the Dojo is connected to the server.

### How a trial ends

Every finished trial lands in exactly one of three outcomes, and the Monitor keeps them apart:

| Outcome     | Color | Meaning                                                                                                           |
| :---------- | :---- | :---------------------------------------------------------------------------------------------------------------- |
| **Success** | Green | The trial ran to the end and passed every [requirement](../requirements.md) (or had none).                        |
| **Failure** | Red   | The trial ran, but missed one or more requirements. This includes a trial that a failing requirement ended early. |
| **Error**   | Amber | The trial raised an unhandled exception. It broke, so it was never judged against its requirements.               |

A trial that has not finished is either **running** (it has started generating or solving) or **pending** (it is waiting for a worker).

### Progress Tracking

The primary progress bar provides a high-level view of your job's timeline.

- **Dynamic Scaling:** The bar fills as trials finish. It is colored by how they ended, so a run with a few failures or errors shows them as segments of the bar, and hovering the bar gives the exact counts.
- **Visual Completion:** Once a job hits 100%, the bar and the page title mark the job as done and the Monitor celebrates (see [Notifications and celebration](#notifications-and-celebration)).

### The "Health" Deck

The stat cards at the top of the page provide an instantaneous look at your run's integrity. Each card has an info icon that explains it.

| Metric                          | Description                                                             | Sub-Value                                                                                 |
| :------------------------------ | :---------------------------------------------------------------------- | :---------------------------------------------------------------------------------------- |
| **Successes**                   | Trials which passed every requirement, with their share of all trials.  | The most recently completed successful trial.                                             |
| **Failures**                    | Trials which ran but failed a requirement.                              | The most recently completed failed trial.                                                 |
| **Errors**                      | Trials which raised an unhandled runtime error.                         | The most recently errored trial.                                                          |
| **Time Elapsed**                | **Total runtime** since starting the job.                               | What time the job was started at.                                                         |
| **Remaining**                   | How many trials **have yet** to finish, with their share of all trials. | How many trials per minute are being completed, and how many trials the job has in total. |
| **Est. Remaining**/**Finished** | Prediction on how much time until job completion.                       | The projected local time of completion (**ETA**), or the time the job finished.           |

---

## Progress Over Time

Under the cards, a stacked bar chart shows how the job moved through time. Each bar is one slice of the job's wall-clock life, and its segments count the trials in each state then: **Success**, **Failure**, **Error**, **Running** and **Pending**. It shows at a glance when the job sped up, when a batch of trials began to fail, or whether it stalled.

<figure markdown="span">
    ![Progress over time chart](../../../assets/user-guides/light-monitor-timeline.jpg#only-light){ width="85%" height="auto" }
    ![Progress over time chart](../../../assets/user-guides/dark-monitor-timeline.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The <b>Progress Over Time</b> chart of a finished job.</figcaption>
</figure>

A trial counts as running from when it begins until it ends, so a finished trial still shows as running over the time it ran. The chart's right edge follows the clock while the job is going. Once nothing is running, it stops at the last completed trial, so a stalled job shows no long flat tail.

---

## Trial Lists

Below the chart, trials are listed as chips in up to three groups: **Success Trials**, **Failed Trials** and **Error Trials**. Click a chip to inspect that trial's telemetry in **Mosaic**.

A trial that never wrote telemetry, such as one that errored before its first step, has nothing to plot. Its chip is grayed out and says _No telemetry data available_ on hover, and its [log and status](trial-details.md) are still in the trial folder.

---

## Notifications and celebration

Simulations can take hours, so the Dojo tells you what happened without you watching the page.

- **Toasts:** a message names trials as they finish while you watch (_Trial 5 succeeded_, _Trial 6 errored_, or a tally such as _3 trials done - 2 ok, 1 failed, 0 errored_). Failures and errors show as error toasts. A final message reports the elapsed time and totals when the job completes.
- **Notification history:** every toast is kept under the bell in the toolbar, with a badge for unread ones. Your browser remembers the history.
- **Chime and celebration:** when the job completes, confetti is thrown and a chime plays if you have unmuted it, with a seasonal theme around some holidays. This happens once per job in each browser, so a reload does not replay it.

<figure markdown="span">
    ![Notification history](../../../assets/user-guides/light-notifications.jpg#only-light){ width="40%" height="auto" }
    ![Notification history](../../../assets/user-guides/dark-notifications.jpg#only-dark){ width="40%" height="auto" }
    <figcaption>The notification history, opened from the bell in the toolbar.</figcaption>
</figure>

The Dojo starts **muted** in a new browser. Click the speaker in the toolbar to unmute it, and the browser remembers your choice.

Two settings, in the [settings panel](dojo.md#settings) or `settings.toml`, apply to everyone who opens the Dojo:

- `dojo.chime_enabled` turns the chime off completely.
- `dojo.chime_source` plays your own sound (a file path or web address) instead.

---

## Other kinds of jobs

- **SLURM jobs:** the Monitor reads the status files the workers write. Without the wizard's watcher, [`mujoco-mojo run watch-workdir`](../../../reference/cli.md#mujoco-mojo-run-watch-workdir) keeps `job_status.json` current (see [Running Jobs](../../workflow/running-jobs/running-jobs.md)).
- **Optimization jobs:** the Monitor shows the optimizer's trials like any other, plus a **Morph** tab beside Mosaic for the study itself (see [Morph](morph.md)).

---

!!! success

    You now know how to monitor your "fleet" of simulations. Now it's time to look at the data itself. Head over to the [Mosaic guide](mosaic.md) to learn about data plotting, multi-trial comparison, and data sharing.
