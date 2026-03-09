import json
from typing import Any, Dict, List, Tuple

import pandas as pd
import plotly.graph_objects as go


AUTO_TUNE_TOOLS = [
    "VE Analyze",
    "Ignition Tune",
    "WUE Analyze",
    "Trim Table",
]


def default_autotune_state() -> Dict[str, Any]:
    return {
        "tool_name": "VE Analyze",
        "mode": "balanced",
        "min_samples": 50,
        "ignore_transient": True,
        "steady_state_only": True,
        "rpm_variance": 100,
        "tps_delta": 5,
        "max_change_pct": 10.0,
        "use_current_log": True,
        "latest_preview": {},
        "latest_apply": {},
        "run_log": [],
        "connected": False,
        "last_run_cells": 0,
    }


def build_tool_cards_html() -> str:
    cards = [
        ("VE Analyze", "AFR-target based VE cell correction with sample filtering."),
        ("Ignition Tune", "Knock-limited timing adjustments with conservative advance."),
        ("WUE Analyze", "Warm-up enrichment correction using ECT-vs-AFR behavior."),
        ("Trim Table", "Global trim model using IAT and barometric response."),
    ]
    chunks = []
    for title, desc in cards:
        chunks.append(
            f"<div style='border:1px solid #334155;border-radius:10px;padding:10px;background:#0b1220'>"
            f"<div style='font-weight:700'>{title}</div>"
            f"<div style='font-size:12px;color:#94a3b8'>{desc}</div>"
            f"</div>"
        )
    return "<div style='display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px'>" + "".join(chunks) + "</div>"


def build_correction_heatmap(
    changes: List[Dict[str, Any]],
    rows: int = 16,
    cols: int = 16,
    title: str = "Correction Heatmap",
) -> go.Figure:
    z = [[0.0 for _ in range(cols)] for _ in range(rows)]
    text = [["" for _ in range(cols)] for _ in range(rows)]

    for c in changes or []:
        r = int(c.get("row", -1))
        col = int(c.get("col", -1))
        if 0 <= r < rows and 0 <= col < cols:
            dv = float(c.get("delta_pct", c.get("delta_deg", 0.0)) or 0.0)
            z[r][col] = dv
            text[r][col] = f"{dv:+.2f}"

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            text=text,
            texttemplate="%{text}",
            colorscale="RdYlGn",
            zmid=0,
            hovertemplate="Row=%{y}<br>Col=%{x}<br>Delta=%{z:.2f}<extra></extra>",
        )
    )
    fig.update_layout(title=title, xaxis_title="RPM Index", yaxis_title="MAP Index", height=360)
    return fig


def build_before_after_scatter(changes: List[Dict[str, Any]], title: str = "Before/After") -> go.Figure:
    before = []
    after = []
    label = []
    for c in changes or []:
        if "before" in c and "after" in c:
            before.append(float(c.get("before", 0.0)))
            after.append(float(c.get("after", 0.0)))
            label.append(f"r{c.get('row','?')} c{c.get('col','?')}")

    fig = go.Figure()
    if before:
        fig.add_trace(
            go.Scattergl(
                x=before,
                y=after,
                mode="markers",
                marker=dict(size=7, color="#22c55e", opacity=0.7),
                text=label,
                hovertemplate="%{text}<br>Before=%{x:.3f}<br>After=%{y:.3f}<extra></extra>",
                name="Cells",
            )
        )
        mn = min(before + after)
        mx = max(before + after)
        fig.add_trace(go.Scatter(x=[mn, mx], y=[mn, mx], mode="lines", name="1:1", line=dict(color="#f97316", dash="dash")))

    fig.update_layout(title=title, xaxis_title="Before", yaxis_title="After", height=360)
    return fig


def summarize_autotune_result(result: Dict[str, Any]) -> str:
    if not result:
        return "No result"
    summary = result.get("summary", {})
    warnings = result.get("warnings", [])
    lines = [
        f"Status: {result.get('status', 'unknown')}",
        f"Tool: {result.get('tool_name', 'n/a')}",
        f"Cells tuned: {summary.get('cells_tuned', 0)}",
    ]
    if "avg_correction_pct" in summary:
        lines.append(f"Avg correction: {summary.get('avg_correction_pct', 0):.3f}%")
    if "avg_correction_deg" in summary:
        lines.append(f"Avg correction: {summary.get('avg_correction_deg', 0):.3f} deg")
    if warnings:
        lines.append("Warnings:")
        for w in warnings:
            lines.append(f"- {w}")
    return "\n".join(lines)


def build_changes_table(changes: List[Dict[str, Any]]) -> pd.DataFrame:
    if not changes:
        return pd.DataFrame()
    return pd.DataFrame(changes)


def format_run_log(lines: List[str]) -> str:
    if not lines:
        return "Ready"
    return "\n".join(lines[-200:])


def parse_stream_ndjson(payload: str) -> List[Dict[str, Any]]:
    out = []
    for line in (payload or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out
