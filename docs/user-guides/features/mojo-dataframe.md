# MojoDataFrame

!!! abstract

    Every trial writes its telemetry to a Parquet file, and a **MojoDataFrame** is how you read it back. It is an ordinary [Polars](https://docs.pola.rs/) `DataFrame`, so everything you know about Polars still works, with a `.mojo` namespace added that understands how Mojo names signals, what units they carry, and how to move them between reference frames. It is the same machinery the [Dojo](dojo/dojo.md) uses to plot your results.

    This guide reads one trial from the [Monte Carlo example](../workflow/running-jobs/running-jobs.md). Run that example first, or point `TELEMETRY` at any `telemetry.parquet` of your own.

    Working with MojoDataFrames was designed to work cleanly with [trendify2](https://github.com/Hydrowelder/trendify). Check it out!

---

## Plain Polars, plus a namespace

A telemetry file is a wide table: one `time` column and one column for each signal you requested, which can be thousands of columns. The column names follow a grammar that Mojo reads for you:

``` text linenums="0" title=""
Category/subgroup/...:attribute
Bodies/box1/xpos:x        the x component of box1's position
Bodies/box1:ke_total      a scalar channel of box1 (no components)
Sensors/gyro/data:z       the z component of a sensor named gyro
```

What a plain Polars frame cannot tell you is which columns belong together, what unit a column is in, whether three columns are a position or a vector or a rotation, or what the integer in a column means. Mojo records that in the Parquet file's footer next to the data (the column's _metadata_), and the [`.mojo` namespace][mujoco_mojo.utils.dataframe.MojoNamespace] reads it.

| Question                                     | With plain Polars                         | With a MojoDataFrame                                    |
| :------------------------------------------- | :---------------------------------------- | :------------------------------------------------------ |
| Which columns did `box1` record?             | Write a regex yourself                    | `df.mojo.select_body(BodyName("box1"))`                 |
| Give me every body's `x` component           | Write a regex yourself                    | `df.mojo.select(Column(category="Bodies", attr="x"))`   |
| What is the unit of this column?             | Not stored                                | `MojoDataFrame.read_column_metadata(path)`              |
| Convert the whole frame's unit system        | Look up each column's unit by hand        | `df.mojo.with_unit_system(UnitSystem.cgs(), path=path)` |
| Express everything relative to a moving body | Rotate and translate each column yourself | `df.mojo.change_frame(quat, origin, path=path)`         |
| Swap `0.0`/`1.0` for `FAIL`/`PASS`           | Write a mapping yourself                  | `df.mojo.convert_enums(path=path)`                      |

???+ info "Every Polars frame has `.mojo`"

    Importing `mujoco_mojo` registers the namespace on all Polars `DataFrame`s, so `.mojo` works on a frame you read with `pl.read_parquet` too. [`MojoDataFrame`][mujoco_mojo.utils.dataframe.MojoDataFrame] is the same frame with Mojo's loaders and with type hints, so your editor and your type checker know about `.mojo` and keep the type through `select`, `filter`, `with_columns` and the rest. Prefer it in your own code.

    ``` python
    --8<-- "docs/user-guides/features/mojo_dataframe_example.py:imports"
    ```

---

## Loading telemetry

Each trial's folder (for example `monte_carlo_study/trials/trial_0/`) has a `telemetry.parquet`. There are four ways to bring it in.

``` python
--8<-- "docs/user-guides/features/mojo_dataframe_example.py:load"
```

| Loader                                                                                                       | Use it to                                                                                                                                                                   |
| :----------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`MojoDataFrame.read_parquet(path)`][mujoco_mojo.utils.dataframe.MojoDataFrame.read_parquet]                 | Read the whole file, or only the `columns` you name. With `n_rows=0` it reads **no rows**, only the column names and types, which is instant whatever the size of the file. |
| [`MojoDataFrame.read_column_metadata(path)`][mujoco_mojo.utils.dataframe.MojoDataFrame.read_column_metadata] | Read the metadata of every column: a dictionary of [`ColumnMetadata`][mujoco_mojo.utils.signal_metadata.ColumnMetadata], keyed by column name.                              |
| [`MojoDataFrame.from_dict(data)`][mujoco_mojo.utils.dataframe.MojoDataFrame.from_dict]                       | Build a frame from your own data, for a test or a synthetic signal.                                                                                                         |
| [`MojoDataFrame.from_pl(df)`][mujoco_mojo.utils.dataframe.MojoDataFrame.from_pl]                             | View a Polars frame you already have as a `MojoDataFrame` (nothing is copied).                                                                                              |

!!! tip "Read only what you need"

    Reading ten columns of a file with five thousand is much faster than reading all of them. Use [`read_parquet(path, n_rows=0)`][mujoco_mojo.utils.dataframe.MojoDataFrame.read_parquet] to look at the names, choose what you want, then [`read_parquet(path, columns=[...])`][mujoco_mojo.utils.dataframe.MojoDataFrame.read_parquet].

---

## Selecting signals

Because the names have a grammar, a selection can say _what you mean_ and not match a pattern. A name part such as `box.1` is matched literally, so a body whose name has a dot or a bracket in it selects only itself.

``` python
--8<-- "docs/user-guides/features/mojo_dataframe_example.py:select"
```

[`df.mojo.select(...)`][mujoco_mojo.utils.dataframe.MojoNamespace.select] is the general tool. It takes [`Column`][mujoco_mojo.utils.column.Column] objects or strings (a string is parsed as a name), and a **partial** column selects everything beneath it:

| You write                             | You get                                                       |
| :------------------------------------ | :------------------------------------------------------------ |
| `"Bodies/box1"`                       | Everything `box1` recorded, including `Bodies/box1:ke_total`. |
| `"Bodies/box1/xpos"`                  | The position group of `box1`: `:x`, `:y`, `:z` and `:m`.      |
| `Column(category="Bodies", attr="x")` | The `:x` component of every body.                             |
| `"time"`                              | The clock.                                                    |

### Reading a name

[`Column`][mujoco_mojo.utils.column.Column] is the model behind the grammar. It splits a name into its parts and back, which is the same code that writes the names during a run, so a reader and a writer cannot disagree.

``` python
--8<-- "docs/user-guides/features/mojo_dataframe_example.py:column"
```

A name part may not contain `/` or `:`, since those delimit the grammar. If you record your own signals, building a `Column` once is how you name them (see [Runtime Script](../workflow/runtime-script.md)).

---

## Poses

A pose is a position and an orientation, which telemetry stores as seven columns (`xpos:x/y/z` and `quat:w/x/y/z`). The pose readers find those columns for you and raise an error that names every one that is missing.

``` python
--8<-- "docs/user-guides/features/mojo_dataframe_example.py:poses"
```

Use [`pose_at`][mujoco_mojo.utils.dataframe.MojoNamespace.pose_at] for a single moment. For a whole trajectory use [`pose_arrays`][mujoco_mojo.utils.dataframe.MojoNamespace.pose_arrays], which makes one array copy per group where calling `pose_at` for each row would build a validated model for every row.

---

## Finding vectors and quaternions

The namespace can tell you which columns are three-component vectors and which are quaternions, which is what you need to choose a reference frame.

``` python
--8<-- "docs/user-guides/features/mojo_dataframe_example.py:discover"
```

[`get_manifest()`][mujoco_mojo.utils.dataframe.MojoNamespace.get_manifest] returns the lists the Dojo shows in its signal selectors: every column, the vectors that can be rotated, the quaternions that can rotate them, and the metadata of each column. A group tagged `scalar` is left out of the rotatable vectors, because three independent numbers that happen to be named `x`, `y` and `z` are not a vector.

---

## Metadata: units, tags and labels

Every column can carry a [`ColumnMetadata`][mujoco_mojo.utils.signal_metadata.ColumnMetadata]:

| Field             | Meaning                                                                                     |
| :---------------- | :------------------------------------------------------------------------------------------ |
| `unit`            | A concrete unit, such as `radian / second`.                                                 |
| `dimension`       | What the column measures, such as `[length]`. Used when the model never declared its units. |
| `quantity`        | The physical quantity, when it is more specific than the dimension.                         |
| `transform_type`  | How the column behaves in a reference frame: `point`, `vector`, `quaternion` or `scalar`.   |
| `enumeration_map` | Labels for integer codes, such as `{"FAIL": 0, "PASS": 1}`.                                 |
| `description`     | What the column holds, in plain words, to tell apart columns with similar names.            |

Built-in signals are tagged and described for you. Declare a unit system on the model (`mojo_model.u = UnitSystem.si()`) and the dimensions become concrete units. For your own signals, pass `metadata=` when you request them. The Dojo reads all of this too: it shows the unit next to a signal, offers the matching unit conversion, and plots a labeled signal on its own axis.

???+ note "A file written by another version still opens"

    A metadata entry that fails validation, such as a unit written by a different version, is still loaded (unvalidated, with a warning) so older results keep opening.

---

## Converting units

[`with_unit_system`][mujoco_mojo.utils.dataframe.MojoNamespace.with_unit_system] converts every column that has a known unit into the matching unit of a target system: `UnitSystem.si()`, `cgs()`, `fps()` or `ips()`. All the conversions run in one pass over the data, however many columns change.

``` python
--8<-- "docs/user-guides/features/mojo_dataframe_example.py:units"
```

A column with only a dimension (no unit) is converted when you pass `assume_source`, which says which system the recorded numbers are in. A column with neither is left as it is.

---

## Changing the reference frame

[`change_frame`][mujoco_mojo.utils.dataframe.MojoNamespace.change_frame] re-expresses a frame's signals relative to a moving frame, defined by an **origin** (a position group) and an **orientation** (a quaternion group). Each column is treated by its `transform_type`:

- **Points** are translated to the new origin and then rotated.
- **Vectors** (velocities, forces) are only rotated.
- **Quaternions** are composed with the inverse of the frame's orientation.
- **Scalars** are left alone.

``` python
--8<-- "docs/user-guides/features/mojo_dataframe_example.py:frames"
```

Pass `invert=False` to go the other way, from the local frame back to the world. Every vector, point and quaternion in the frame must be tagged, or `change_frame` raises and names the column: there is no untagged fallback, because guessing wrong would silently corrupt the data. This is the same calculation the Dojo's **Ref. Frame** selector performs.

---

## Labels for integer signals

Telemetry stores everything as numbers. A requirement's verdict, a proximity type and an `insidesite` sensor are integer codes, and they carry an `enumeration_map` so they can be read as words. [`convert_enums`][mujoco_mojo.utils.dataframe.MojoNamespace.convert_enums] swaps the codes for their labels as a Polars `Enum` column, ordered by code.

``` python
--8<-- "docs/user-guides/features/mojo_dataframe_example.py:enums"
```

A NaN, a null, a fractional number or a code the map does not name becomes null. Pass `strict=True` to raise instead. To label a signal of your own, build its metadata with `ColumnMetadata.from_enum(MyEnum)` when you request it.

---

## Filters

The filters you stack in the Dojo (low pass, derivative, rolling mean, unit conversion, rotation, and the rest) are plain Pydantic models, and the same models work in code. [`with_filters`][mujoco_mojo.utils.dataframe.MojoNamespace.with_filters] applies one stack to the columns you name (every column, if you name none), and [`with_filter_map`][mujoco_mojo.utils.dataframe.MojoNamespace.with_filter_map] gives each column its own stack. The `time` column is skipped unless you pass `omit_time=False`.

``` python
--8<-- "docs/user-guides/features/mojo_dataframe_example.py:filters"
```

!!! tip "See available [filters here][mujoco_mojo.utils.filters.filters]"

---

## Where you meet a MojoDataFrame

- **[Requirements](requirements.md):** the `df` your check receives is the trial's telemetry as a `MojoDataFrame`, so `df.mojo.select_body(...)` works inside a requirement.
- **[Optimization](optimization.md):** an objective gets the path to the telemetry and can read it the same way.
- **Your own analysis:** loop over `trials/*/telemetry.parquet`, load the columns you need from each, and compare trials with plain Polars.

!!! success

    You now know how to get from a Parquet file to the numbers you care about without writing a regex or a rotation matrix. To look at the same data with a mouse instead, see the [Dojo Dashboard](dojo/dojo.md).
