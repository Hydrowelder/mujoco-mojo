"""
Type-checked source for the code examples in `docs/user-guides/features/custom-signals/custom-signals.md`.

The documentation embeds these snippets directly via `pymdownx.snippets` section markers (`--8<-- [start:name]` / `--8<-- [end:name]`), so the examples shown to users are exactly the code that ruff and the type checkers validate. If an API change breaks an example, the checkers fail on this file instead of the documentation silently rotting. Nothing here is run.
"""

from __future__ import annotations

from enum import IntEnum

import mujoco_mojo as mojo
import mujoco_mojo.runtime as rt

# --8<-- [start:column]
spring_force = mojo.utils.Column(
    category=mojo.SignalCategory.CUSTOM,
    subgroups=("suspension", "front_left"),
    attr="force",
)
# str(spring_force) is "Custom/suspension/front_left:force"
# --8<-- [end:column]


# --8<-- [start:sampler]
def runtime(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    # built once: the sampler runs on every recorded step
    contacts = mojo.utils.Column(
        category=mojo.SignalCategory.CUSTOM,
        subgroups=("contacts",),
        attr="count",
    )

    def sample_contacts(state: mojo.MjState) -> None:
        assert runtime_manager.signal_manager
        runtime_manager.signal_manager.post(state.data.ncon, contacts)

    with runtime_manager as rm:
        if rm.signal_manager:
            rm.signal_manager.register_sampler(sample_contacts)

        while state.data.time < 2.0:
            rm.step(state)

    return mojo_model


# --8<-- [end:sampler]


def runtime_with_track(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    # --8<-- [start:track]
    target = 0.5
    error = 0.0

    with runtime_manager as rm:
        if rm.signal_manager:
            rm.signal_manager.track(
                lambda: error,
                mojo.utils.Column(
                    category=mojo.SignalCategory.CUSTOM,
                    subgroups=("controller",),
                    attr="error",
                ),
            )

        while state.data.time < 2.0:
            error = target - float(state.data.qpos[0])
            state.data.ctrl[0] = 10.0 * error
            rm.step(state)
    # --8<-- [end:track]

    return mojo_model


def runtime_with_a_stale_track(
    mojo_model: mojo.MojoModel,
    runtime_manager: rt.RuntimeManager,
    state: mojo.MjState,
    *args,
    **kwargs,
) -> mojo.MojoModel:
    height = mojo.utils.Column(
        category=mojo.SignalCategory.CUSTOM,
        subgroups=("ball",),
        attr="height",
    )

    with runtime_manager as rm:
        assert rm.signal_manager
        # --8<-- [start:track_stale]
        # wrong: the height is read once, so every row holds the starting height
        start = float(state.data.qpos[2])
        rm.signal_manager.track(lambda: start, height)

        # right: the height is read again each time the function is called
        rm.signal_manager.track(lambda: float(state.data.qpos[2]), height)
        # --8<-- [end:track_stale]

        while state.data.time < 2.0:
            rm.step(state)

    return mojo_model


# --8<-- [start:metadata]
spring_stretch = mojo.utils.Column(
    category=mojo.SignalCategory.CUSTOM,
    subgroups=("suspension", "front_left"),
    attr="stretch",
    metadata=mojo.utils.ColumnMetadata(
        dimension="[length]",
        description="How far the front left spring is stretched past its rest length",
    ),
)
# --8<-- [end:metadata]


# --8<-- [start:enum]
class Mode(IntEnum):
    IDLE = 0
    RUNNING = 1


mode = mojo.utils.Column(
    category=mojo.SignalCategory.CUSTOM,
    subgroups=("controller",),
    attr="mode",
    metadata=mojo.utils.ColumnMetadata.from_enum(Mode),
)
# --8<-- [end:enum]
