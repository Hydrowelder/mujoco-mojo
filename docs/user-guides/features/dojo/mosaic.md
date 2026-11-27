# Mosaic

!!! abstract

    The **Mosaic** tool is the heart of the Dojo. While the Monitor tells you that a job finished, Mosaic shows you how it performed. It is a high-performance telemetry viewer designed to handle massive datasets while staying very customizable.

---

## Choosing a Trial

Mosaic opens on a tile for every trial that wrote telemetry. The tiles are colored the way the [Monitor](monitor.md) colors outcomes (green for a success, red for a requirement failure, yellow for an error), so you can go straight to the trials worth a look. Click a tile to open that trial.

<figure markdown="span">
    ![Trial list](../../../assets/user-guides/light-trial-list.jpg#only-light){ width="85%" height="auto" }
    ![Trial list](../../../assets/user-guides/dark-trial-list.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The <b>Mosaic</b> landing page. Trials that failed a requirement or raised an error stand out from the successes.</figcaption>
</figure>

---

## The Trial Page

<figure markdown="span">
    ![Mosaic dashboard view](../../../assets/user-guides/light-mosaic-view.jpg#only-light){ width="85%" height="auto" }
    ![Mosaic dashboard view](../../../assets/user-guides/dark-mosaic-view.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>A preview of the <b>Mosaic</b> page showing run results for <code>trial_00</code>. The header holds the trial navigation and the versus control, the selectors choose the signals, and the plot has its editing sidebar beside it.</figcaption>
</figure>

A trial page is built from, top to bottom:

1. The **header**: where you are, how to move to another trial, and versus mode.
2. The **plot tabs**: one tab for each plot you have open.
3. The **selectors**: which signals to plot, and how to transform them.
4. The **plot** and its sidebar.
5. The **trial details**: animation, distributions, status and logs (see [Trial Details](trial-details.md)).
6. The **JSON configuration** of the plot.

---

## Selection Ribbon

The top of the page is dedicated to Data Navigation and Signal Selection.

### Trial Navigation

- **Sequential Access:** Use the PREV and NEXT buttons (or ++ctrl+left++ and ++ctrl+right++, ++cmd+left++ and ++cmd+right++ on a Mac) to flip through trials like a slide deck.
- **The Warp Box:** Want to jump to a specific trial? Press ++slash++ to focus the box, type the number (or use ++up++ and ++down++), and hit ++enter++ (or click Warp). A small dot beside the number shows how that trial ended, so you know before you jump.
- **Back to All:** The link at the left returns to the list of trials. Beside the trial's name, the **Lab** button opens the [Signal Lab](signal-lab.md).
- **Shortcuts:** Hover the question mark for the list of keyboard shortcuts.

### Versus Mode

Toggle the **VS.** switch to overlay the current trial against other trials. This is essential for identifying outliers in a Monte Carlo run, and for comparing a failed trial with a good one. Click the pill to open its panel:

<figure markdown="span">
    ![Versus panel](../../../assets/user-guides/light-versus.jpg#only-light){ width="85%" height="auto" }
    ![Versus panel](../../../assets/user-guides/dark-versus.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The <b>versus</b> panel: a range of trials chosen with the slider, and a few more pinned by hand.</figcaption>
</figure>

- **Range:** drag either end of the slider, drag the filled bar to move the whole range without changing its width, or type the **START** and **END** trial numbers. **±10**, **±25** and **All** are presets around the current trial.
- **Pinned trials:** below the slider, every trial is a chip you can pin. A pinned trial is compared whether or not it is inside the range, which is how you compare against, say, the three trials that failed. A chip's color tells how that trial ended (hover it to read _Trial failed requirements_ or _Trial errored_). **Deselect All** clears the pins.
- **Apply:** the trials are loaded when you press **Apply**, since each one's data has to be fetched.

### Plot Tabs

A page can hold several plots at once, each with its own signals, filters, annotations and settings. Use the tab strip above the selectors:

- **New** adds a tab, and **Duplicate** copies the tab you are on.
- **Double-click** a tab to rename it. A tab's name is the plot's title.
- **Drag** a tab to reorder them. Click while holding ++shift++ or ++ctrl++ to select several, and closing one of a selection closes them all.
- **Close** a tab with its **x** or a middle-click. **Reopen** brings back the one you closed last, in case it was an accident.

Your tabs are remembered by your browser, so a reload brings them back. [Profiles](#saved-profiles) and the [Share](#share-button) link carry them to somewhere else.

### Signal Selection (X and Y Axes)

-   **X-Axis:** Usually set to time, but you can map any telemetry signal to the X-axis to create phase-space plots (e.g., `velocity` vs. `position`). **X-Axis Filters** transform the x signal as well (one filter per stack here; use the Lab to chain more).
-   **Reference Frame:** Re-expresses vector signals (those ending in `:(x|y|z)`) relative to a frame instead of `world`. A frame is an orientation (a signal ending in `quat:(w|x|y|z)`), an origin (a position signal ending in `:(x|y|z)`), or both. An orientation alone only rotates, and an origin alone only translates.
    - Positions are translated and rotated. Other vectors, such as velocities and forces, are only rotated, and so is any signal not tagged as a position, such as custom signals and Signal Lab outputs.
    - Saved profiles and shared links that use the older single-signal frame reset to `world`.
-   **Y-Axes (Multi-Select):** You can overlay as many signals as you want. The button shows how many are selected, and opens a folder-style tree of the signals with a search box. Opening a folder that holds only one folder or signal opens straight down to it. With a reference frame other than `world` selected this list is automatically filtered to available vectors.
-   **Labeled Signals (Enums):** A signal that carries labels for its integer codes (an `enumeration_map`) is drawn as a step line on its own axis on the right, with the labels as the tick marks. Signals that share the same labels share one axis, and hovering shows the label next to the code. Filters and reference frames do not apply to these signals.
-   **Descriptions:** Hover a signal in the X-Axis, Y-Axes or Reference Frame list to see its full name and, if it has one, its description. The built-in signals describe themselves, and you can [describe your own](../mojo-dataframe/mojo-dataframe.md#metadata-units-tags-and-labels) to tell apart signals with similar names. Turn on the tag button in a signal list's search box to search by description.
-   **Metadata:** The info button on a signal shows what Mojo recorded about it (its unit, dimension and tags). Where a unit is known, the Dojo offers the matching unit conversion as a quick filter.
-   **The Ribbon:** Selected signals appear as color-coded chips. Use the arrows on the chips to reorder them (hold ++shift++ to send one straight to the start or the end). The order in the ribbon determines the color mapping on the plot. You can also remove signals with the "x" button, or clear them all with **Deselect All**.

!!! tip "Pro Tip: Regex Filtering"

    The dropdowns aren't just lists; they are Regex-aware. You can use the segment buttons (like quat, ctrl, or sens) to quickly filter down hundreds of signals to just the ones you need. If you would rather not see the buttons, turn off `dojo.show_quick_filters`.

???+ info "The search box has two buttons"

    Every signal list's search box has two buttons at its right:

    - **`.*`** switches between a regular expression (the default, and what the segment buttons write) and plain text. In plain text no character is special, and each space-separated word only has to be part of the signal's name, so `box1 vel` finds `Bodies/box1/xvelp:x`. The segment buttons are hidden while it is on, since they write regular expressions.
    - **The tag** also searches the signals' [descriptions](../mojo-dataframe/mojo-dataframe.md#metadata-units-tags-and-labels), along with their quantity and unit. In plain text each word of your search has to be in the name, or be the start of a word of the description, so `box1 angular` finds the angular velocity of `box1` even though its name never says so. In a regular expression the description is searched with the same expression as the name.

    Both are remembered by your browser and are the same in every signal list.

<figure markdown="span">
    ![Selector bar](../../../assets/user-guides/light-selector-bar.jpg#only-light){ width="85%" height="auto" }
    ![Selector bar](../../../assets/user-guides/dark-selector-bar.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The dropdown for <b>Y-Axes</b> is active. Two telemetry signals are selected, showing the translational and rotational kinetic energy.</figcaption>
</figure>

### Per-Signal Settings and Filters

Click a signal's name in the ribbon to open its settings. They apply to that one line:

- **Legend Label, Width, Opacity, Style and Marker** change how the line is drawn and named in the legend.
- **Filters** are a stack that runs in order on the signal before it is plotted: low pass, derivative, rolling mean, unit conversion, rotation and more. Add one from the menu, then set its parameters (a number box accepts arithmetic such as `180/pi` or `sqrt(2)`). You can reorder filters, switch one off without deleting it, duplicate it, or delete it. Press **Apply Changes** to draw the result.

<figure markdown="span">
    ![Signal settings](../../../assets/user-guides/light-signal-config.jpg#only-light){ width="40%" height="auto" }
    ![Signal settings](../../../assets/user-guides/dark-signal-config.jpg#only-dark){ width="40%" height="auto" }
    <figcaption>The settings of one signal, opened from its chip: how its line is drawn, and its filter stack.</figcaption>
</figure>

The filters are the same ones you can use in code with [`MojoDataFrame`](../mojo-dataframe/mojo-dataframe.md#filters), and the ones the [Signal Lab](signal-lab.md) offers as nodes.

---

## The Plot

The plot is Plotly: scroll to zoom, drag to pan, double-click to reset the view, and hover for the values. Drag the handle in the corner of the plot to resize it (hold ++shift++ to lock its aspect ratio). When a trial has an animation, a miniplayer can float over the plot (see [Trial Details](trial-details.md#animation)).

With **Plot Type** set to _polar_, the plot is drawn as a polar chart with the x signal as the angle, which suits headings and other angles. Notes and shapes are not available in polar mode.

<figure markdown="span">
    ![Polar plot](../../../assets/user-guides/light-polar.jpg#only-light){ width="60%" height="auto" }
    ![Polar plot](../../../assets/user-guides/dark-polar.jpg#only-dark){ width="60%" height="auto" }
    <figcaption>A polar plot.</figcaption>
</figure>

---

## Sidebar

The sidebar provides many plot appearance configuration options.

### Share Button

This button opens a panel to share your plot. **Copy link to this tab** compacts the current plot (trial, selected data, plot appearance, etc.) into a link that you can send to others. Great for getting a second opinion, or sharing an interesting result! To bring someone else's link into your own session, paste it under **Add tab from link**, which adds it as a new tab beside what you already have open.

<figure markdown="span">
    ![Share panel](../../../assets/user-guides/light-share.jpg#only-light){ width="40%" height="auto" }
    ![Share panel](../../../assets/user-guides/dark-share.jpg#only-dark){ width="40%" height="auto" }
    <figcaption>The <b>share</b> panel, opened with the Share button at the top of the sidebar.</figcaption>
</figure>

### Plot Editor

Adjust the visual style of the plot. Hover the question mark beside any field for what it does, and use the small reset button that appears when a field differs from its default.

| Field                 | Options                                                                                                            |
| :-------------------- | :----------------------------------------------------------------------------------------------------------------- |
| **Gridlines**         | None, major or all.                                                                                                |
| **Mode**              | Lines, markers, or both.                                                                                           |
| **Interpolation**     | Linear, spline, or one of the step shapes (`hv`, `vh`, `hvh`, `vhv`).                                              |
| **Hover**             | How the tooltip groups values: unified on x or y, the closest point, the x or y value, or off.                     |
| **Legend**            | Below the plot, to its right, or hidden.                                                                           |
| **Show Spikes**       | Draws guide lines from the pointer to the axes.                                                                    |
| **Plot Type**         | Cartesian or polar.                                                                                                |
| **Max Points**        | Downsamples a long signal to at most this many points, so a plot of millions of samples stays smooth.              |
| **Display Units**     | Converts every signal with a known unit to a system: as logged, SI, CGS, FPS or IPS.                               |
| **X-Scale / Y-Scale** | Linear or logarithmic, with the base of the logarithm.                                                             |
| **X-Range / Y-Range** | The limits of each axis. Leave a limit empty for automatic. Arithmetic works here too, such as `-pi` or `sqrt(2)`. |
| **Titles**            | The plot's title and the label of each axis.                                                                       |

**Reset to Defaults** at the bottom returns the plot to its starting appearance.

<figure markdown="span">
    ![Plot editor menu](../../../assets/user-guides/light-plot-editor.jpg#only-light){ width="40%" height="auto" }
    ![Plot editor menu](../../../assets/user-guides/dark-plot-editor.jpg#only-dark){ width="40%" height="auto" }
    <figcaption>The menu for <b>plot editor</b>, opened with the Plot button, is active. It shows the many dropdown options available to configure the layout of the plot area as well as the interaction behavior when hover over data.</figcaption>
</figure>

### Notes Editor

**Middle-click** anywhere on the plot to drop a persistent note at the exact data coordinates of your cursor. Notes are saved into the JSON config and help you flag specific events (like "Impact Start" or "Sensor Saturation"). The editor allows you to go back and edit the note's label. Press ++esc++ to cancel an in-progress note or close the panel.

???+ tip "Tip: Clickable Buttons"

    You can click on a note in the editor to "focus" on the note!

<figure markdown="span">
    ![Notes editor menu](../../../assets/user-guides/light-notes-editor.jpg#only-light){ width="85%" height="auto" }
    ![Notes editor menu](../../../assets/user-guides/dark-notes-editor.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The menu for <b>notes editor</b>, opened with the Notes button, lists two notes. Each is drawn on the plot at its coordinates.</figcaption>
</figure>

### Shapes Editor

Add various shapes to the plot. After selecting an option in the menu, your mouse becomes a placement tool. Clicking on the plot configures the placement of the shape. Press ++esc++ at any time to cancel placement.

- **V-Line:** Draws a vertical line on the plot. The abscissa of the mouse determines the abscissa of the line.
- **H-Line:** Draws a horizontal line on the plot. The ordinate of the mouse determines the ordinate of the line.
- **Rect:** Draws a rectangle on the plot. The abscissa and ordinate of the mouse determines one of the corners of the rectangle. Likewise, the second click determines the other corner.

Each new shape is automatically assigned the next color in the preset palette so overlapping shapes remain visually distinct. The shape editor includes a full color picker (identical to the signal color picker) for precise color control, a line style, and a label that is drawn beside the shape.

<figure markdown="span">
    ![Shapes editor menu](../../../assets/user-guides/light-shapes-editor.jpg#only-light){ width="85%" height="auto" }
    ![Shapes editor menu](../../../assets/user-guides/dark-shapes-editor.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The menu for <b>shapes editor</b>, opened with the Shapes button, holds a vertical line, a horizontal line and a rectangle, each with its label. The plot draws them.</figcaption>
</figure>

### Saved Profiles

Profiles save your complete workspace under a named key so you can restore a view instantly. A profile holds **every open plot tab**: each one's selected signals, axes, display settings, zoom, annotations and shapes.

Profiles are stored globally in your user data folder (`~/.local/share/mujoco-mojo/profiles/` on Linux) and are available across all workdirs, making it easy to share a standard analysis setup between projects.

<figure markdown="span">
    ![Saved profiles menu](../../../assets/user-guides/light-profiles.jpg#only-light){ width="40%" height="auto" }
    ![Saved profiles menu](../../../assets/user-guides/dark-profiles.jpg#only-dark){ width="40%" height="auto" }
    <figcaption>The <b>saved profiles</b> menu, opened with the Profiles button, with one profile saved in a folder.</figcaption>
</figure>

**Creating a profile**

Type a name in the save box and press **Save** or ++enter++ (++ctrl+s++ is the shortcut). To organize profiles into folders use a `folder/name` path, for example `arm-reach/baseline`. Folders are created automatically and the input field completes existing folder names with ++tab++.

**Loading a profile**

Click **Load** next to any profile in the list. If the profile references signals, axes, or reference frames that do not exist in the current trial it will be rejected with an error toast rather than silently applying an invalid configuration. Profiles that are incompatible with the current trial are marked with a warning icon in the list, and **Hide invalid** hides them.

**Searching and sorting profiles**

A search box filters the profile list by name (including folder path) as you type. **A-Z** and **Recent** sort it by name or by when it was changed, and clicking the active one again reverses the order.

### Undo/Redo

Every change to the plot configuration is tracked. Use the standard shortcuts (++ctrl+z++ / ++ctrl+y++ or ++cmd+z++ / ++cmd+shift+z++) to step through your edits.

### Export Options

Dojo provides a few basic export options to capture an image of the plot or save data from the configuration.

- **Capture Plot:** Image options for saving the plot appearance: SVG (a vector image that stays sharp at any size), a 1080p PNG, a high-DPI PNG, or a compressed 1080p JPG.
- **Filtered CSV:** A CSV file containing the data currently being plotted can be downloaded for a look at the raw data.
- **Config JSON:** The current page configuration can be downloaded as a JSON so it can be reloaded at a later time.
- **Column Manifest:** The list of the trial's signals, with which can be rotated and each one's metadata, as JSON, for a script or any other tool that needs to know what the trial recorded.
- **Chat History:** The conversation with [SensAI](sensai.md), when you have one.

<figure markdown="span">
    ![Export options menu](../../../assets/user-guides/light-export-options.jpg#only-light){ width="40%" height="auto" }
    ![Export options menu](../../../assets/user-guides/dark-export-options.jpg#only-dark){ width="40%" height="auto" }
    <figcaption>The menu for <b>export options</b>, opened with the Export button at the bottom of the sidebar.</figcaption>
</figure>

## The JSON Editor

At the bottom of the page sits the **Live JSON Configuration**.

Everything you do in the UI is mirrored in this JSON block in real-time, from selecting axes, adding notes, changing colors.

- **Live Editing:** You can type directly into this editor. If you have a specific list of 20 Y-axes you want to add, pasting them into the JSON is often faster than clicking 20 boxes.
- **Validation:** The editor features a Syntax Health indicator and description of any issues. A config that is valid JSON but does not fit the plot's schema is reported too, with where it goes wrong.
- **Copy/Format:** A copy and format button are also provided to provide improved quality of life.

???+ tip "Tip: Drag and Drop"

    If you downloaded a Config JSON in the [export options menu](#export-options), you can drag and drop that file back on this page to update the JSON configuration!

---

!!! success

    You are now an expert with the Mosaic! Below the plot, the [Trial Details](trial-details.md) show how the trial ran. To build signals the run did not record, open the [Signal Lab](signal-lab.md), and to ask for any of this in plain language, try [SensAI](sensai.md).
