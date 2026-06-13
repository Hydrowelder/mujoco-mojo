# Mosaic

!!! abstract
    The **Mosaic** tool is the heart of the Dojo. While the Monitor tells you that a job finished, Mosaic shows you how it performed. It is a high-performance telemetry viewer designed to handle massive datasets while staying very customizable.

---

<figure markdown="span">
    ![Mosaic dashboard view](../../assets/user-guides/light-mosaic-view.jpg#only-light){ width="85%" height="auto" }
    ![Mosaic dashboard view](../../assets/user-guides/dark-mosaic-view.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>A preview of the <b>Mosaic</b> page showing run results for <code>trial_00</code>. Annotations indicate key moments in the simulations. Two telemetry signals per trial are shown with 9 additional trials displayed for comparison.</figcaption>
</figure>

## Selection Ribbon

The top of the page is dedicated to Data Navigation and Signal Selection.
Trial Navigation

- **Sequential Access:** Use the PREV and NEXT buttons (or your arrow keys) to flip through trials like a slide deck.
- **The Warp Box:** Want to jump to a specific trial? Type the number into the center box and hit Enter (or click Warp).
- **Versus Mode:** Toggle the VS switch to overlay the current trial against a range of other trials. This is essential for identifying outliers in a Monte Carlo run.

### Signal Selection (X and Y Axes)

- **X-Axis:** Usually set to time, but you can map any telemetry signal to the X-axis to create phase-space plots (e.g., `velocity` vs. `position`).
- **Reference Frame:** For signals which could have a full quaternion defined (ends with `quat:(w|x|y|z)`), a reference frame can be defined to rotate vector based columns (those ending in `:(x|y|z)`). It is assumed these vector columns are defined in the `world` frame.
- **Y-Axes (Multi-Select):** You can overlay as many signals as you want. With a reference frame other than `world` selected this list is automatically filtered to available vectors.
- **The Ribbon:** Selected signals appear as color-coded chips. Use the arrows on the chips to reorder them. The order in the ribbon determines the color mapping on the plot. You can also remove signals with the "x" button.

!!! tip "Pro Tip: Regex Filtering"
    The dropdowns aren't just lists; they are Regex-aware. You can use the segment buttons (like quat, ctrl, or sens) to quickly filter down hundreds of signals to just the ones you need.

<figure markdown="span">
    ![Selector bar](../../assets/user-guides/light-selector-bar.jpg#only-light){ width="85%" height="auto" }
    ![Selector bar](../../assets/user-guides/dark-selector-bar.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The dropdown for <b>Y-Axes</b> is active with the Bodies and box1 quick filters active. Two telemetry signals are selected showing the rotational and total kinetic energy.</figcaption>
</figure>

---

## Sidebar

The sidebar provides many plot appearance configuration options.

### Share Button

This button compacts your current plot view (trial, selected data, plot appearance, etc.) and converts it to a link that you can send to others. Great for getting a second opinion, or sharing an interesting result!

### Plot Editor

Adjust the visual style. Switch between Lines, Markers, or both. Change interpolation (Spline vs. Linear) or toggle Logarithmic scales for high-dynamic-range data.

<figure markdown="span">
    ![Plot editor menu](../../assets/user-guides/light-plot-editor.jpg#only-light){ width="40%" height="auto" }
    ![Plot editor menu](../../assets/user-guides/dark-plot-editor.jpg#only-dark){ width="40%" height="auto" }
    <figcaption>The menu for <b>plot editor</b> is active. It shows the many dropdown options available to configure the layout of the plot area as well as the interaction behavior when hover over data.</figcaption>
</figure>

### Notes Editor

**Middle-click** anywhere on the plot to drop a persistent note at the exact data coordinates of your cursor. Notes are saved into the JSON config and help you flag specific events (like "Impact Start" or "Sensor Saturation"). The editor allows you to go back and edit the note's label. Press ++esc++ to cancel an in-progress note or close the panel.

???+ tip "Tip: Clickable Buttons"
    You can click on a note in the editor to "focus" on the note!

<figure markdown="span">
    ![Notes editor menu](../../assets/user-guides/light-notes-editor.jpg#only-light){ width="60%" height="auto" }
    ![Notes editor menu](../../assets/user-guides/dark-notes-editor.jpg#only-dark){ width="60%" height="auto" }
    <figcaption>The menu for <b>notes editor</b> is active and in editing mode. A note is being edited. The plot area shows the two notes shown in the menu.</figcaption>
</figure>

### Shapes Editor

Add various shapes to the plot. After selecting an option in the menu, your mouse becomes a placement tool. Clicking on the plot configures the placement of the shape. Press ++esc++ at any time to cancel placement.

- **V-Line:** Draws a vertical line on the plot. The abscissa of the mouse determines the abscissa of the line.
- **H-Line:** Draws a horizontal line on the plot. The ordinate of the mouse determines the ordinate of the line.
- **Rect:** Draws a rectangle on the plot. The abscissa and ordinate of the mouse determines one of the corners of the rectangle. Likewise, the second click determines the other corner.

Each new shape is automatically assigned the next color in the preset palette so overlapping shapes remain visually distinct. The shape editor includes a full color picker (identical to the signal color picker) for precise color control.

<figure markdown="span">
    ![Shapes editor menu](../../assets/user-guides/light-shapes-editor.jpg#only-light){ width="60%" height="auto" }
    ![Shapes editor menu](../../assets/user-guides/dark-shapes-editor.jpg#only-dark){ width="60%" height="auto" }
    <figcaption>The menu for <b>shapes editor</b> is active and in editing mode. A shape's label and color is being edited. The plot area shows a vertical (yellow) and horizontal (red) line and a rectangle (purple).</figcaption>
</figure>

### Saved Profiles

Profiles save your complete plot configuration (selected signals, axes, display settings, zoom, annotations, and shapes) under a named key so you can restore a view instantly.

Profiles are stored globally in `~/.mujoco-mojo/profiles/` and are available across all workdirs, making it easy to share a standard analysis setup between projects.

**Creating a profile**

Type a name in the save box and press **Save** or ++enter++. To organize profiles into folders use a `folder/name` path, for example `arm-reach/baseline`. Folders are created automatically and the input field offers Tab-completion for existing folder names.

**Loading a profile**

Click **Load** next to any profile in the list. If the profile references signals, axes, or reference frames that do not exist in the current trial it will be rejected with an error toast rather than silently applying an invalid configuration. Profiles that are incompatible with the current trial are marked with a warning icon in the list.

**Searching profiles**

A search box filters the profile list by name (including folder path) as you type.

### Undo/Redo

Every change to the plot configuration is tracked. Use the standard shortcuts (++ctrl+z++ / ++ctrl+y++ or ++cmd+z++ / ++cmd+shift+z++) to step through your edits.

### Export Options

Dojo provides a few basic export options to capture an image of the plot or save data from the configuration.

- **Capture Plot:** Three options for saving the plot appearance are provided (SVG, PNG, or JPG)
- **Filtered CSV:** A CSV file containing the data currently being plotted can be downloaded for a look at the raw data.
- **Config JSON:** The current page configuration can be downloaded as a JSON so it can be reloaded at a later time.

<figure markdown="span">
    ![Export options menu](../../assets/user-guides/light-export-options.jpg#only-light){ width="60%" height="auto" }
    ![Export options menu](../../assets/user-guides/dark-export-options.jpg#only-dark){ width="60%" height="auto" }
    <figcaption>The menu for <b>export options</b> is active. </figcaption>
</figure>

## The JSON Editor

At the bottom of the page sits the **Live JSON Configuration**.

Everything you do in the UI is mirrored in this JSON block in real-time, from selecting axes, adding notes, changing colors.

- **Live Editing:** You can type directly into this editor. If you have a specific list of 20 Y-axes you want to add, pasting them into the JSON is often faster than clicking 20 boxes.
- **Validation:** The editor features a Syntax Health indicator and description of any issues.
- **Copy/Format:** A copy and format button are also provided to provide improved quality of life.

???+ tip "Tip: Drag and Drop"
    If you downloaded a Config JSON in the [export options menu](#export-options), you can drag and drop that file back on this page to update the JSON configuration!

---

!!! success
    You are now an expert with MuJoCo Mojo!

    > Live long and prosper!
