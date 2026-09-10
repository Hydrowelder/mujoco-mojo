"""SensAI domain agent for signal columns - read-only, forced to answer with the current ColumnManifest."""

from __future__ import annotations

from pydantic_ai import Agent, RunContext  # pyright: ignore[reportMissingImports]

from mujoco_mojo.utils.dataframe import ColumnManifest

from .deps import SensAIDeps

_SYSTEM_PROMPT = """\
You are the column-manifest agent inside the MuJoCo Mojo Dojo dashboard.

Answer questions about which signal columns are available for plotting using your tools, \
then finish with the current column manifest.

The manifest is derived telemetry metadata - there is nothing to create, update, or delete \
here, only report on what's available.
"""


def return_column_manifest(ctx: RunContext[SensAIDeps]) -> ColumnManifest:
    """
    Call this once you've gathered whatever you need to answer the request, to finish with the current column manifest.

    Returns it directly rather than asking you to reconstruct it, since re-typing every column name yourself risks dropping or inventing one.

    """
    return ctx.deps.column_manifest


column_manifest_agent: Agent[SensAIDeps, ColumnManifest] = Agent(
    deps_type=SensAIDeps,
    output_type=return_column_manifest,
    system_prompt=_SYSTEM_PROMPT,
)


@column_manifest_agent.tool
async def get_available_signals(ctx: RunContext[SensAIDeps]) -> list[str]:
    """Returns the list of signal column names available in the current trial's telemetry data."""
    return ctx.deps.column_manifest["all"]


@column_manifest_agent.tool
async def get_rotatable_signals(ctx: RunContext[SensAIDeps]) -> list[str]:
    """Returns the list of signal column names which can be rotated by get_quat_signals."""
    return ctx.deps.column_manifest["rotatable_vectors"]


@column_manifest_agent.tool
async def get_quat_signals(ctx: RunContext[SensAIDeps]) -> list[str]:
    """Returns the list of signal column names which can be used to rotate get_rotatable_signals."""
    return ctx.deps.column_manifest["available_quats"]
