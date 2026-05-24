"""
Lab graph executor.

Takes a LiteGraph-serialised graph (from graph.serialize() in the browser)
and executes it against a Polars DataFrame, returning the output series keyed
by their Signal Out labels.

LiteGraph link format:
    links: [[link_id, from_node_id, from_slot, to_node_id, to_slot, type], ...]
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

import polars as pl

from mujoco_mojo.utils.filters.filters import (
    AbsoluteValueFilter,
    ClipFilter,
    DeadbandFilter,
    HighPassFilter,
    LowPassFilter,
    MedianFilter,
    NormalizeFilter,
    RollingMeanFilter,
    SavitzkyGolayFilter,
    ScaleFilter,
    TaringFilter,
    WrapFilter,
)

# Map node type string → filter class (single-input filters only)
_FILTER_MAP = {
    "low_pass": LowPassFilter,
    "high_pass": HighPassFilter,
    "scale": ScaleFilter,
    "rolling_mean": RollingMeanFilter,
    "median": MedianFilter,
    "savitzky_golay": SavitzkyGolayFilter,
    "clip": ClipFilter,
    "deadband": DeadbandFilter,
    "wrap": WrapFilter,
    "taring": TaringFilter,
    "normalize": NormalizeFilter,
    "absolute_value": AbsoluteValueFilter,
}


class LabExecutor:
    """
    Execute a LiteGraph filter graph against a Polars DataFrame.

    Usage::

        executor = LabExecutor(graph_dict)
        outputs  = executor.execute(df)   # {label: pl.Series}
    """

    def __init__(self, graph: dict[str, Any]) -> None:
        self.nodes: dict[int, dict] = {n["id"]: n for n in graph.get("nodes", [])}
        # links keyed by link_id → [link_id, from_node, from_slot, to_node, to_slot, type]
        self.links: dict[int, list] = {lnk[0]: lnk for lnk in graph.get("links", [])}

    # ── public helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _bare_type(node: dict) -> str:
        """Strip the LiteGraph category prefix, e.g. 'Signal/signal_in' → 'signal_in'."""
        return node.get("type", "").split("/")[-1]

    @property
    def signal_in_columns(self) -> list[str]:
        """Column names used by all Signal In nodes — used for validation."""
        return [
            n.get("properties", {}).get("column", "")
            for n in self.nodes.values()
            if self._bare_type(n) == "signal_in"
        ]

    @property
    def output_labels(self) -> list[str]:
        """Labels produced by all Signal Out nodes."""
        return [
            n.get("properties", {}).get("label") or f"out_{n['id']}"
            for n in self.nodes.values()
            if self._bare_type(n) == "signal_out"
        ]

    def execute(self, df: pl.DataFrame) -> dict[str, pl.Series]:
        """Run the graph and return {output_label: series}."""
        # slot_data[node_id][slot_index] = computed series
        slot_data: dict[int, dict[int, pl.Series]] = defaultdict(dict)

        for nid in self._topo_sort():
            node = self.nodes[nid]
            ntype = self._bare_type(node)
            props = node.get("properties", {})

            if ntype == "signal_in":
                col = props.get("column", "")
                series = (
                    df[col].cast(pl.Float64)
                    if col in df.columns
                    else pl.Series(name=col, values=[0.0] * len(df))
                )
                slot_data[nid][0] = series

            elif ntype == "signal_out":
                signal = self._get_input(node, 0, slot_data)
                if signal is not None:
                    slot_data[nid][0] = signal

            else:
                signal = self._get_input(node, 0, slot_data)
                if signal is None:
                    continue
                wrt = self._get_input(node, 1, slot_data)
                slot_data[nid][0] = self._apply(ntype, props, signal, wrt, df)

        # Collect Signal Out results
        outputs: dict[str, pl.Series] = {}
        for nid, node in self.nodes.items():
            if node.get("type") == "signal_out":
                series = slot_data.get(nid, {}).get(0)
                if series is not None:
                    label = node.get("properties", {}).get("label") or f"out_{nid}"
                    outputs[label] = series
        return outputs

    # ── internals ─────────────────────────────────────────────────────────────

    def _topo_sort(self) -> list[int]:
        in_degree: dict[int, int] = {nid: 0 for nid in self.nodes}
        adj: dict[int, list[int]] = defaultdict(list)
        for _, from_node, _, to_node, _, *_ in self.links.values():
            adj[from_node].append(to_node)
            in_degree[to_node] += 1
        queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
        order: list[int] = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for nxt in adj[nid]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
        return order

    def _get_input(
        self,
        node: dict,
        slot: int,
        slot_data: dict[int, dict[int, pl.Series]],
    ) -> pl.Series | None:
        inputs = node.get("inputs", [])
        if slot >= len(inputs):
            return None
        link_id = inputs[slot].get("link")
        if link_id is None or link_id not in self.links:
            return None
        lnk = self.links[link_id]
        from_node, from_slot = lnk[1], lnk[2]
        return slot_data.get(from_node, {}).get(from_slot)

    def _apply(
        self,
        ntype: str,
        props: dict,
        signal: pl.Series,
        wrt: pl.Series | None,
        df: pl.DataFrame,
    ) -> pl.Series:
        # Derivative and Integral handle wrt directly
        if ntype == "derivative":
            if wrt is not None:
                dx = (
                    wrt.cast(pl.Float64)
                    .diff()
                    .fill_null(strategy="forward")
                    .fill_null(1)
                )
                return signal.cast(pl.Float64).diff().fill_null(0) / dx
            dt = float(props.get("dt", 0.001)) or 0.001
            return signal.cast(pl.Float64).diff().fill_null(0) / dt

        if ntype == "integral":
            if wrt is not None:
                dx = wrt.cast(pl.Float64).diff().fill_null(0)
                return (signal.cast(pl.Float64) * dx).cum_sum()
            dt = float(props.get("dt", 0.001)) or 0.001
            return signal.cast(pl.Float64).cum_sum() * dt

        cls = _FILTER_MAP.get(ntype)
        if cls is None:
            return signal

        # Strip None values so Pydantic uses field defaults
        clean = {k: v for k, v in props.items() if v is not None}
        try:
            filt = cls(**clean)
        except Exception:
            return signal

        tmp = pl.DataFrame({"_s": signal.cast(pl.Float64)})
        ctx = filt.apply_with_context(tmp["_s"], df)
        if ctx is not None:
            return ctx
        tmp = tmp.with_columns(filt.apply(pl.col("_s")).alias("_s"))
        return tmp["_s"]
