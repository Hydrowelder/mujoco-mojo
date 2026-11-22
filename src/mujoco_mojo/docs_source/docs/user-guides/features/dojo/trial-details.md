# Trial Details

!!! abstract

    Under the plot of every [Mosaic](mosaic.md) trial page are four panels that answer the questions a plot cannot: _what did this trial look like?_, _where did its random draws land?_, _did it meet its requirements?_ and _what did it say while it ran?_ A panel only appears when the trial has something to show, and each one folds away with a click on its title. The Dojo remembers which you left open.

---

## Animation

When a trial recorded a video (a [`VideoRecorder`][mujoco_mojo.runtime.video_recorder.VideoRecorder] in the [runtime script](../../workflow/runtime-script.md), saved as `.mp4`, `.webm` or `.gif`), the **Animation** panel plays it beside your plot. If the trial recorded more than one video, pick one from the list beside the title.

<figure markdown="span">
    ![Animation panel](../../../assets/user-guides/light-animation.jpg#only-light){ width="85%" height="auto" }
    ![Animation panel](../../../assets/user-guides/dark-animation.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The <b>Animation</b> panel playing a trial's recording, with its playback line and frame markers drawn on the plot above.</figcaption>
</figure>

| Control         | What it does                                                                                                                                                    |
| :-------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Mode: Play**  | Plays the video. Use the speed presets or type a speed from 0.1x to 8x.                                                                                         |
| **Mode: Scrub** | Ties the video to your pointer: hover over the plot and the video shows the moment under it. This is the fastest way to see _what happened at the spike_.       |
| **Plot line**   | Draws a vertical line on the plot that moves with the video, so you can see where in the data the picture is. Needs the x-axis to be `time`.                    |
| **Frames**      | Marks every video frame on the plot. Needs the x-axis to be `time`.                                                                                             |
| Miniplayer      | The button in the panel's title floats the video over the plot, so you can keep it in view while you work. Drag it to move it and drag its corner to resize it. |

!!! note "GIFs and scrubbing"

    A GIF cannot be scrubbed, so the Dojo converts it to a WebM the first time you open it (the panel says _preparing scrub..._), and keeps the converted copy in your system's temporary folder. If the conversion cannot be done, the panel says _scrub unavailable_ and still plays the GIF. An `.mp4` or `.webm` file needs no conversion.

---

## Distributions

A trial's inputs are drawn from the [distributions](../../workflow/generate-script.md) you sampled in the generate script. The **Distributions** panel lists every one of them with the value this trial drew, so you can tell whether a trial that behaved oddly drew something unusual.

<figure markdown="span">
    ![Distributions panel](../../../assets/user-guides/light-distributions.jpg#only-light){ width="85%" height="auto" }
    ![Distributions panel](../../../assets/user-guides/dark-distributions.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The <b>Distributions</b> table. Hovering a row shows the shape of its distribution and where this trial's draw fell.</figcaption>
</figure>

| Column       | Meaning                                                                                                                   |
| :----------- | :------------------------------------------------------------------------------------------------------------------------ |
| **Name**     | The name you gave the distribution.                                                                                       |
| **Category** | The group it belongs to.                                                                                                  |
| **Type**     | The kind of distribution (normal, truncated normal, uniform, categorical and so on).                                      |
| **Units**    | The unit of the values, or a dash when none was declared.                                                                 |
| **Nominal**  | The value the nominal trial uses.                                                                                         |
| **Sampled**  | The value this trial drew.                                                                                                |
| **Stat**     | How far out the draw is: its z-score in standard deviations (`+1.25σ`), or its percentile where a z-score does not apply. |

- **Hover** a row to see the distribution drawn as its probability density (or its probability mass, as bars, for a discrete or categorical one), with markers for the sampled and the nominal values.
- **Sort** by clicking a column title. **Resize** a column by dragging the edge of its title, and **double-click** the edge to fit it to its contents.
- **Filter** by name with the box at the top, and by category, type or unit with the menus. Each menu counts how many parameters match.

A job with no distributions has no panel.

---

## Trial Execution

The **Trial Execution** panel shows how the trial itself ran, and carries a badge with its outcome (`SUCCESS`, `FAILURE`, `TERMINATED`, `ERROR` or `INCOMPLETE`, see [Requirements](../requirements.md#completion-states)).

<figure markdown="span">
    ![Trial execution panel](../../../assets/user-guides/light-trial-execution.jpg#only-light){ width="85%" height="auto" }
    ![Trial execution panel](../../../assets/user-guides/dark-trial-execution.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The <b>Trial Execution</b> panel of a trial that failed a requirement.</figcaption>
</figure>

**Steps:** A table of the two steps of a trial, `generating` (your generate script builds the model) and `solving` (your runtime script runs the simulation), with the local time each started and how long it took, in seconds. A step that is still going shows _running..._. This is the table to read when one trial took far longer than the others.

**Requirements:** When the trial had [requirements](../requirements.md), each is listed with its verdict, the simulation time it was decided at, and its message. The badge counts how many passed (`1/2 PASSED`). Hover the info icon of a requirement to see how it was set up: how often it was checked (every N steps, or at the end of the trial only), and whether it terminates the trial on a failure or a pass, or latches.

!!! tip "Requirements as a signal"

    A requirement that is checked during the run can also record its verdicts as a signal named `Requirements/<name>:result`, which you can plot against the rest of the telemetry. The Dojo labels the two values `PASS` and `FAIL` on a shared axis.

---

## Logs

Every trial writes its own log, `mojo.log`, in its folder: what it did, any warnings, and for an error the exception with its full traceback. The **Logs** panel shows it as a table, so you do not have to open the file.

<figure markdown="span">
    ![Logs panel](../../../assets/user-guides/light-trial-logs.jpg#only-light){ width="85%" height="auto" }
    ![Logs panel](../../../assets/user-guides/dark-trial-logs.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The <b>Logs</b> of a trial that raised an error, including the entry with the error.</figcaption>
</figure>

| Column      | Meaning                                                                                                                       |
| :---------- | :---------------------------------------------------------------------------------------------------------------------------- |
| **Time**    | When the entry was written, shown as how long ago. Hover for the exact time.                                                  |
| **Level**   | `INFO`, `WARNING`, `ERROR` and so on. Click the title to sort, and use the menu to show only the levels you want.             |
| **Source**  | The file and line that wrote it. Click it to copy the full path and line, which an editor can jump to.                        |
| **Message** | What it said. The filter box matches entries containing your text, or a regular expression when you turn the regex button on. |

The panel's title counts the entries (`mojo.log · 12/40` while a filter shows 12 of 40). As in the other tables, you can resize a column by dragging its edge and fit it with a double-click.

!!! tip "Debugging an errored trial"

    An error never reaches the Monitor's cards as more than a count, but the trial's log holds the whole story. From the Monitor, click an errored trial's chip, and read the last `ERROR` entry. [SensAI](sensai.md) can read these logs too, so you can ask _why did my trials error?_.

---

!!! success

    That is the full tour of a trial. To change what the data looks like, see the [Signal Lab](signal-lab.md); to work with it in code, see [MojoDataFrame](../mojo-dataframe.md).
