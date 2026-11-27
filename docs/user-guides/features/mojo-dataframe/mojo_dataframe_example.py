"""
Type-checked source for every code example in `docs/user-guides/features/mojo-dataframe/mojo-dataframe.md`.

The documentation embeds these snippets directly via `pymdownx.snippets` section markers (`--8<-- [start:name]` / `--8<-- [end:name]`), so the examples shown to users are exactly the code that ruff and ty validate. Run it after the Monte Carlo example (`python -m mujoco_mojo.examples.boxes_and_springs.simulation`), whose `monte_carlo_study` folder it reads.
"""

from __future__ import annotations

from pathlib import Path

# --8<-- [start:imports]
import mujoco_mojo as mojo
from mujoco_mojo.stochas import UnitSystem
from mujoco_mojo.utils import MojoDataFrame
from mujoco_mojo.utils.column import Column
from mujoco_mojo.utils.filters import DerivativeFilter, LowPassFilter, ScaleFilter
from mujoco_mojo.utils.signal_metadata import ColumnMetadata

# --8<-- [end:imports]


def load() -> MojoDataFrame:
    # --8<-- [start:load]
    # every trial folder holds the telemetry its runtime script requested
    TELEMETRY = Path("monte_carlo_study/trials/trial_0/telemetry.parquet")

    # the whole file
    df = MojoDataFrame.read_parquet(TELEMETRY)

    # only the columns you name, which is much faster for a file with thousands of them
    some = MojoDataFrame.read_parquet(TELEMETRY, columns=["time", "Bodies/box1/xpos:x"])
    print(some.height, "rows in the small frame")

    # the units, dimensions and tags each column was recorded with
    metadata = MojoDataFrame.read_column_metadata(TELEMETRY)
    print(metadata["Bodies/box1/xpos:x"].transform_type)
    # --8<-- [end:load]
    return df


def select(df: MojoDataFrame) -> None:
    # --8<-- [start:select]
    # everything one body recorded, including its scalar channels such as
    # `Bodies/box1:ke_total`
    box1 = df.mojo.select_body(mojo.BodyName("box1"))

    # a partial column selects a whole subtree
    box1_positions = df.mojo.select("Bodies/box1/xpos")

    # or the same attribute of everything: every body's `:x` component, and the time
    every_x = df.mojo.select(Column(category="Bodies", attr="x"), "time")

    # one channel across all objects, for example the translational velocity of
    # every body and site
    velocities = df.mojo.select_channel("xvelp")

    # simulation clock time
    time = df.mojo.time
    # --8<-- [end:select]
    print(box1.width, box1_positions.width, every_x.width, velocities.width, time.len())


def parse_names(df: MojoDataFrame) -> None:
    # --8<-- [start:column]
    column = Column.parse("Bodies/box1/xpos:x")
    print(column.category, column.subgroups, column.attr)  # Bodies ('box1', 'xpos') x

    # `in` asks whether a column lies under another one
    print(
        "Bodies/box1/xpos:x" in Column(category="Bodies", subgroups=("box1",))
    )  # True

    # the frame's own columns, parsed (a column that does not follow the grammar is left out)
    first = df.mojo.columns[0]
    print(str(first))
    # --8<-- [end:column]


def poses(df: MojoDataFrame) -> None:
    # --8<-- [start:poses]
    # the pose of a site or body at one row, as a `PoseQuat`
    pose = df.mojo.pose_at(0, "Sites/box1_rot_site")

    # the whole trajectory as plain arrays: positions (n, 3) and quaternions (n, 4)
    # in w, x, y, z order
    positions, quaternions = df.mojo.pose_arrays("Sites/box1_rot_site")
    # --8<-- [end:poses]
    print(pose.pos, positions.shape, quaternions.shape)


def discover(df: MojoDataFrame) -> None:
    TELEMETRY = Path("monte_carlo_study/trials/trial_0/telemetry.parquet")
    # --8<-- [start:discover]

    # groups with x, y and z, like `Bodies/box1/xpos`
    print(sorted(df.mojo.rotatable_bases))

    # groups with w, x, y and z, like `Sites/A/quat`
    print(sorted(df.mojo.quaternion_bases))

    # the same lists the Dojo uses to offer reference frames
    manifest = df.mojo.get_manifest(
        column_metadata=MojoDataFrame.read_column_metadata(TELEMETRY)
    )
    print(
        len(manifest["all"]),
        len(manifest["rotatable_vectors"]),
        len(manifest["available_quats"]),
    )
    # --8<-- [end:discover]


def units(df: MojoDataFrame) -> MojoDataFrame:
    # --8<-- [start:units]
    TELEMETRY = Path("monte_carlo_study/trials/trial_0/telemetry.parquet")

    # convert every column that has a known unit
    cgs = df.mojo.with_unit_system(UnitSystem.cgs(), path=TELEMETRY)

    # a model that never declared its units records dimensions only (`[length]`), so say
    # which system the numbers are in to convert those too
    cgs = df.mojo.with_unit_system(
        UnitSystem.cgs(), path=TELEMETRY, assume_source=UnitSystem.si()
    )
    # --8<-- [end:units]
    return cgs


def frames(df: MojoDataFrame) -> MojoDataFrame:
    # --8<-- [start:frames]
    TELEMETRY = Path("monte_carlo_study/trials/trial_0/telemetry.parquet")

    # re-express every position, vector and quaternion relative to a site: positions are
    # translated and rotated, vectors only rotated, quaternions composed
    relative = df.mojo.change_frame(
        "Sites/box1_rot_site/quat", "Sites/box1_rot_site/xpos", path=TELEMETRY
    )
    # --8<-- [end:frames]
    return relative


def enums() -> MojoDataFrame:
    # --8<-- [start:enums]
    from enum import IntEnum

    class Mode(IntEnum):
        IDLE = 0
        ACTIVE = 1

    metadata = {"Custom/controller:mode": ColumnMetadata.from_enum(Mode)}
    df = MojoDataFrame.from_dict({"Custom/controller:mode": [0.0, 0.0, 1.0, 1.0]})

    # swap the integer codes for their labels
    labeled = df.mojo.convert_enums(column_metadata=metadata)
    print(
        labeled["Custom/controller:mode"].to_list()
    )  # ['IDLE', 'IDLE', 'ACTIVE', 'ACTIVE']
    # --8<-- [end:enums]
    return labeled


def filters(df: MojoDataFrame) -> None:
    # --8<-- [start:filters]
    # one stack of filters for the columns you name
    smooth = df.mojo.with_filters(
        [LowPassFilter(alpha=0.2)], columns=["Bodies/box1:ke_total"]
    )

    # or a different stack for each column
    custom = df.mojo.with_filter_map(
        {
            "Bodies/box1/xpos:x": [DerivativeFilter(dt=0.01)],
            "Bodies/box2/xpos:x": [ScaleFilter(factor=100.0)],
        }
    )
    # --8<-- [end:filters]
    print(smooth.height, custom.height)


if __name__ == "__main__":
    frame = load()
    select(frame)
    parse_names(frame)
    poses(frame)
    discover(frame)
    units(frame)
    frames(frame)
    enums()
    filters(frame)
