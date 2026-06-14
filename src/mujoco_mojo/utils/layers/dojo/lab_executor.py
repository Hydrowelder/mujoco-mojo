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
    ComparisonFilter,
    DeadbandFilter,
    ExpFilter,
    FirstFilter,
    HighPassFilter,
    LastFilter,
    LogFilter,
    LowPassFilter,
    MaxFilter,
    MeanFilter,
    MedianFilter,
    MinFilter,
    ModeFilter,
    NormalizeFilter,
    PowerFilter,
    ReverseFilter,
    RollingMeanFilter,
    RollingMedianFilter,
    RotationFilter,
    RoundFilter,
    SavitzkyGolayFilter,
    ScaleFilter,
    SignFilter,
    SortFilter,
    StandardDeviationFilter,
    TaringFilter,
    TrigFilter,
    WrapFilter,
)

# Map node type string → filter class (single-input filters only)
_FILTER_MAP = {
    "low_pass": LowPassFilter,
    "high_pass": HighPassFilter,
    "scale": ScaleFilter,
    "rolling_mean": RollingMeanFilter,
    "median": RollingMedianFilter,
    "savitzky_golay": SavitzkyGolayFilter,
    "clip": ClipFilter,
    "deadband": DeadbandFilter,
    "wrap": WrapFilter,
    "taring": TaringFilter,
    "normalize": NormalizeFilter,
    "absolute_value": AbsoluteValueFilter,
    "log": LogFilter,
    "exp": ExpFilter,
    "power": PowerFilter,
    "round": RoundFilter,
    "trig": TrigFilter,
    "sign": SignFilter,
    "comparison": ComparisonFilter,
    "stat_max": MaxFilter,
    "stat_min": MinFilter,
    "stat_mean": MeanFilter,
    "stat_median": MedianFilter,
    "stat_mode": ModeFilter,
    "stat_standard_deviation": StandardDeviationFilter,
    "stat_first": FirstFilter,
    "stat_last": LastFilter,
    "sort": SortFilter,
    "reverse": ReverseFilter,
}


class LabExecutor:
    """
    Execute a LiteGraph filter graph against a Polars DataFrame.

    Usage::

        executor = LabExecutor(graph_dict)
        outputs  = executor.execute(df)   # {label: pl.Series}
    """

    def __init__(self, graph: dict[str, Any]) -> None:
        self._raw_nodes: list[dict] = graph.get("nodes", [])
        self.nodes: dict[int, dict] = {n["id"]: n for n in self._raw_nodes}
        # links keyed by link_id → [link_id, from_node, from_slot, to_node, to_slot, type]
        self.links: dict[int, list] = {lnk[0]: lnk for lnk in graph.get("links", [])}

    # ── public helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _bare_type(node: dict) -> str:
        """Strip the LiteGraph category prefix, e.g. 'Signal/signal_in' → 'signal_in'."""
        return node.get("type", "").split("/")[-1]

    @property
    def signal_in_columns(self) -> list[str]:
        """Column names used by all Signal In nodes - used for validation."""
        return [
            n.get("properties", {}).get("column", "")
            for n in self.nodes.values()
            if self._bare_type(n) == "signal_in"
        ]

    @property
    def rotation_dependencies(self) -> set[str]:
        """
        Parquet columns required by any Rotation node in this graph: the
        quaternion's x/y/z/w components, and the x/y/z siblings of the vector
        feeding the rotation's input (which must come directly from a Signal In
        node - see the rotation handling note in `_apply`).
        """
        deps: set[str] = set()
        for node in self.nodes.values():
            if self._bare_type(node) != "rotation":
                continue

            quat_col = node.get("properties", {}).get("quat_col")
            if quat_col:
                deps.update(f"{quat_col}:{k}" for k in ("x", "y", "z", "w"))

            link_id = node.get("inputs", [{}])[0].get("link")
            lnk = self.links.get(link_id) if link_id is not None else None
            if lnk is None:
                continue
            from_node = self.nodes.get(lnk[1])
            if from_node is None or self._bare_type(from_node) != "signal_in":
                continue
            column = from_node.get("properties", {}).get("column", "")
            if ":" not in column:
                continue
            base = column.rsplit(":", 1)[0]
            deps.update(f"{base}:{k}" for k in ("x", "y", "z"))

        return deps

    @property
    def output_labels(self) -> list[str]:
        """Labels produced by all Signal Out nodes."""
        return [
            n.get("properties", {}).get("label") or f"out_{n['id']}"
            for n in self.nodes.values()
            if self._bare_type(n) == "signal_out"
        ]

    @property
    def _template_in_labels(self) -> list[str]:
        """Template In port labels in graph-definition order."""
        return [
            n.get("properties", {}).get("label") or f"in_{n['id']}"
            for n in self._raw_nodes
            if self._bare_type(n) == "template_in"
        ]

    @property
    def _template_out_labels(self) -> list[str]:
        """Template Out port labels in graph-definition order."""
        return [
            n.get("properties", {}).get("label") or f"out_{n['id']}"
            for n in self._raw_nodes
            if self._bare_type(n) == "template_out"
        ]

    def execute(
        self,
        df: pl.DataFrame,
        template_inputs: dict[str, pl.Series] | None = None,
    ) -> dict[str, pl.Series]:
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

            elif ntype == "template_in":
                label = props.get("label", "")
                if template_inputs and label in template_inputs:
                    slot_data[nid][0] = template_inputs[label]
                else:
                    slot_data[nid][0] = pl.Series(
                        name=label or "_tmpl_in",
                        values=[0.0] * len(df),
                        dtype=pl.Float64,
                    )

            elif ntype == "constant":
                value = float(props.get("value", 0.0))
                slot_data[nid][0] = pl.Series(
                    name="const", values=[value] * len(df), dtype=pl.Float64
                )

            elif ntype in ("signal_out", "template_out"):
                signal = self._get_input(node, 0, slot_data)
                if signal is not None:
                    slot_data[nid][0] = signal

            elif ntype == "template_ref":
                template_graph = props.get("graph")
                if not template_graph:
                    continue
                sub = LabExecutor(template_graph)
                # map parent input slots to Template In labels by position
                sub_inputs: dict[str, pl.Series] = {}
                for i, label in enumerate(sub._template_in_labels):
                    s = self._get_input(node, i, slot_data)
                    if s is not None:
                        sub_inputs[label] = s
                sub_outputs = sub.execute(df, template_inputs=sub_inputs)
                # map Template Out labels to parent output slots by position
                for i, label in enumerate(sub._template_out_labels):
                    if label in sub_outputs:
                        slot_data[nid][i] = sub_outputs[label]

            elif ntype == "norm":
                inputs = [
                    s.cast(pl.Float64)
                    for i in range(len(node.get("inputs", [])))
                    if (s := self._get_input(node, i, slot_data)) is not None
                ]
                if not inputs:
                    continue
                acc = inputs[0].pow(2)
                for s in inputs[1:]:
                    acc = acc + s.pow(2)
                slot_data[nid][0] = acc.sqrt()

            else:
                signal = self._get_input(node, 0, slot_data)
                if signal is None:
                    continue
                wrt = self._get_input(node, 1, slot_data)
                slot_data[nid][0] = self._apply(ntype, props, signal, wrt, df)

        # when called as a template sub-execution (template_inputs provided), collect
        # template_out nodes; otherwise collect signal_out nodes for regular lab execution
        terminal = "template_out" if template_inputs is not None else "signal_out"
        outputs: dict[str, pl.Series] = {}
        for nid, node in self.nodes.items():
            if self._bare_type(node) == terminal:
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
        # Individual trig nodes (one node per function, no combo widget)
        _TRIG_FNS = {
            "sin",
            "cos",
            "tan",
            "asin",
            "acos",
            "atan",
            "sinh",
            "cosh",
            "tanh",
            "degrees",
            "radians",
        }
        if ntype in _TRIG_FNS:
            filt = TrigFilter(func=ntype)  # type: ignore[arg-type]
            tmp = pl.DataFrame({"_s": signal.cast(pl.Float64)})
            return tmp.with_columns(filt.apply(pl.col("_s")).alias("_s"))["_s"]

        # Individual comparison nodes - signal vs signal, returns 1.0/0.0
        _CMP_OPS = {"gt", "gte", "lt", "lte", "eq", "neq"}
        if ntype in _CMP_OPS:
            if wrt is None:
                return signal
            a = signal.cast(pl.Float64)
            b = wrt.cast(pl.Float64)
            if ntype == "gt":
                return (a > b).cast(pl.Float64)
            if ntype == "gte":
                return (a >= b).cast(pl.Float64)
            if ntype == "lt":
                return (a < b).cast(pl.Float64)
            if ntype == "lte":
                return (a <= b).cast(pl.Float64)
            if ntype == "eq":
                return (a == b).cast(pl.Float64)
            return (a != b).cast(pl.Float64)

        # Two-input arithmetic (signal a op signal b)
        if ntype in ("add", "subtract", "multiply", "divide"):
            if wrt is None:
                return signal
            a = signal.cast(pl.Float64)
            b = wrt.cast(pl.Float64)
            if ntype == "add":
                return a + b
            if ntype == "subtract":
                return a - b
            if ntype == "multiply":
                return a * b
            # divide: propagate zero denominator as null (will become NaN in JSON)
            tmp = pl.DataFrame({"_a": a, "_b": b})
            return tmp.select(
                pl.when(pl.col("_b") != 0)
                .then(pl.col("_a") / pl.col("_b"))
                .otherwise(None)
                .cast(pl.Float64)
            ).to_series()

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

        # Rotation needs the full dataframe and the signal's original column
        # name (to find its x/y/z siblings and the quaternion columns), so it
        # is applied directly rather than via the renamed "_s" tmp column.
        if ntype == "rotation":
            clean = {k: v for k, v in props.items() if v is not None}
            try:
                filt = RotationFilter(**clean)
            except Exception:
                return signal
            ctx = filt.apply_with_context(signal.cast(pl.Float64), df)
            return ctx if ctx is not None else signal

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
