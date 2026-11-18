# Signal Lab

!!! abstract

    The **Signal Lab** builds new signals **after** a run has finished. You wire the signals you recorded through filters, arithmetic and frame changes on a canvas, and the result is a new signal you can plot, compare across trials and share, without touching your runtime script or running the job again.

---

## Opening the Lab

Press **Lab** beside the trial's name in the header of a [Mosaic](mosaic.md) trial page. The Lab covers the page as an overlay, with a toolbar across the top, a tab for each lab you have open, a canvas, and a status bar of shortcuts at the bottom. ++esc++ closes it.

<figure markdown="span">
    ![Signal Lab](../../../assets/user-guides/light-signal-lab.jpg#only-light){ width="85%" height="auto" }
    ![Signal Lab](../../../assets/user-guides/dark-signal-lab.jpg#only-dark){ width="85%" height="auto" }
    <figcaption>The <b>Signal Lab</b> overlay with the <code>box1-speed</code> lab from the example below open: Signal In, Scale and Signal Out, with the toolbar above and the lab's tab.</figcaption>
</figure>

---

## Building a graph

A lab is a graph. Signals flow from left to right through **nodes**, joined by wires. **Right-click** the canvas to add a node, **scroll** to zoom and **drag** the background to pan. Drag from one node's output dot to another's input dot to wire them, and select a node and press ++delete++ to remove it.

Every graph has the same two ends:

- **Signal In** picks one of the trial's signals as the start of a wire. Click its dropdown to search the signals the same way the Mosaic selectors do.
- **Signal Out** ends a wire and **names the new signal**. Give it a label (it becomes the signal's name and the y-axis label), and set the metadata of the result: its unit, dimension, quantity and transform type, so that the Dojo can convert units and change reference frames for it like any recorded signal.

Between them, the nodes are grouped in the add-node menu:

| Group            | Nodes                                                                                                                                                   |
| :--------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Signal**       | Signal In, Signal Out, and **Constant** (a number as a signal).                                                                                         |
| **Smoothing**    | Low Pass, High Pass, Rolling Mean, Median and Savitzky-Golay, with their parameters as widgets on the node.                                             |
| **Calculus**     | **Derivative** and **Integral**. Each has an optional second input, `wrt`, to differentiate or integrate with respect to another signal instead of time. |
| **Arithmetic**   | **Add**, **Subtract**, **Multiply** and **Divide** of two signals, the **Norm** of several (the length of a vector, from its components), and Scale, Absolute Value, Log, Exp and Power of one. |
| **Trigonometry** | Sine, cosine, tangent, their inverses and hyperbolic forms, and conversions between degrees and radians.                                                |
| **Comparison**   | **Greater Than**, **Less Than**, **Equal** and the rest, which compare two signals and give 1 or 0, and Sign.                                           |
| **Bounding**     | Clip, Deadband, Wrap, Taring, Normalize and Round.                                                                                                      |
| **Statistics**   | Max, Min, Mean, Median, Mode, Standard Deviation, First and Last, each reduced to a single value.                                                       |
| **Ordering**     | Sort and Reverse.                                                                                                                                       |
| **Vector**       | **Rotation** (into the frame of an orientation, and optionally an origin) and **Translation** (add or subtract a position).                             |
| **Template**     | Template In and Template Out, and each saved template as one node (see [Templates](#templates)).                                                        |

The single-signal nodes are the same filters that work in code on a [`MojoDataFrame`](../mojo-dataframe.md#filters), so a graph you prove out here can be written down as a short script.

---

## The toolbar

| Button      | What it does                                                                                              |
| :---------- | :-------------------------------------------------------------------------------------------------------- |
| **Refresh** | Checks again that every signal the lab reads exists in this trial.                                         |
| **Fit**     | Zooms the canvas to show the whole graph (++ctrl+shift+f++).                                               |
| **Arrange** | Lays the nodes out in tidy columns (++ctrl+shift+a++).                                                     |
| **Clear**   | Empties the canvas.                                                                                        |
| **Save**    | Saves the lab under the name in the box beside it (++ctrl+s++).                                            |
| **Load**    | Opens a saved lab in a new tab.                                                                            |

++ctrl+z++ and ++ctrl+y++ undo and redo, as everywhere in the Dojo (++cmd+z++ and ++cmd+shift+z++ on a Mac).

### Tabs

Like the plots, the Lab keeps several graphs open at once as tabs: **New** starts a blank one, **Duplicate** copies the one you are on, and you can drag the tabs to reorder them. A tab is named by the name you save its lab under, and it is marked while it has changes you have not saved. The Lab remembers your open tabs, so a reload picks up where you left off.

---

## Saving and using a lab

Type a name in the box beside **Save** and press **Save**. Use `folder/name` to keep labs in folders (for example `arm/tip-speed`), and ++tab++ completes the folder names. Saved labs live in `~/.mujoco-mojo/lab/`, so they are available for every job.

A saved lab's outputs become **signals of the trial**. Close the Lab and open the Y-axes dropdown: the new signals are listed under `Lab/<lab name>/<label>`, next to the ones the run recorded, and you can plot them, filter them, and put them in a [profile](mosaic.md#saved-profiles) like any other. They are computed when the plot is drawn, so a lab applies to **every** trial that has the signals it reads, and you can flip between trials and [compare them in versus mode](mosaic.md#versus-mode) with no extra step.

!!! note "Lab signals are not stored in your data"

    A lab's outputs live in the Dojo only. They are not written into `telemetry.parquet`, so a script that reads the file with [`MojoDataFrame`](../mojo-dataframe.md) will not see them. To keep one, express the same steps in code.

The **Load** list shows each saved lab with when it changed, and flags the ones that cannot run on the trial in front of you:

- A lab is **valid** only when every signal it reads exists in this trial. A lab that needs a signal you did not record is marked, with the signals it is missing. **Hide invalid** hides them.
- A lab can read the outputs of another lab, and the Dojo works out the order. Two labs that read each other are flagged as a **circular dependency**.
- **A-Z** and **Recent** sort the list by name or by when it was changed, and clicking the active one again reverses the order.

---

## Templates

A lab with **Template In** and **Template Out** nodes is a **template**: instead of reading named signals, it takes inputs and gives outputs through those ports. Once saved, a template appears in the **Template** group as a single node, so a chain of filters you use again and again, such as _remove the offset, then smooth, then differentiate_, becomes one box you can drop into any graph. A template can contain other templates.

Templates are marked `tmpl` in the saved-lab list.

---

## An example

To plot the speed of `box1` in centimeters per second:

1. Press **Lab**. Add a **Signal In** and choose `Bodies/box1/xvelp:m`, the magnitude of its velocity in meters per second.
2. Add an **Arithmetic > Scale** node and set its factor to `100`.
3. Add a **Signal Out** and label it `speed_cm_s`.
4. Wire **In** to the scale, and the scale to **Out**.
5. Name the lab `box1-speed` and press **Save**, then close the Lab.
6. Open the Y-axes dropdown and choose `Lab/box1-speed/speed_cm_s`.

---

!!! success

    You can now make the signal your analysis needs, even when the run did not record it. To do the same in a script, continue to [MojoDataFrame](../mojo-dataframe.md).
