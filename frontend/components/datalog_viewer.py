import ast
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go


DEFAULT_VIEW_CHANNELS = ["RPM", "MAP_kPa", "AFR", "KnockCount", "InjectorDuty_pct"]


def default_datalog_state() -> Dict[str, Any]:
    return {
        "filename": "",
        "rows": [],
        "channels": [],
        "cursor": 0,
        "playing": False,
        "playback_speed": 1.0,
        "table_page": 1,
        "table_page_size": 100,
        "selected_channels": DEFAULT_VIEW_CHANNELS,
        "filter_expr": "",
        "scatter_x": "RPM",
        "scatter_y": "AFR",
        "math_channels": {},
    }


def build_playback_shortcuts_html(payload_elem_id: str, trigger_button_id: str) -> str:
    return f"""
<div style='padding:4px 0;color:#94a3b8;font-size:12px'>Shortcuts: Space play/pause, Left/Right arrow step frame</div>
<script>
(function() {{
  const payloadId = {payload_elem_id!r};
  const triggerId = {trigger_button_id!r};

  function emit(action) {{
    const inp = document.querySelector(`#${{payloadId}} textarea`) || document.querySelector(`#${{payloadId}} input`);
    const btn = document.querySelector(`#${{triggerId}} button`);
    if (!inp || !btn) return;
    inp.value = JSON.stringify({{ action }});
    inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
    btn.click();
  }}

  document.addEventListener('keydown', function(e) {{
    const active = document.activeElement;
    if (active && ['INPUT', 'TEXTAREA'].includes(active.tagName)) return;
    if (e.code === 'Space') {{ e.preventDefault(); emit('toggle'); }}
    if (e.code === 'ArrowRight') {{ e.preventDefault(); emit('next'); }}
    if (e.code === 'ArrowLeft') {{ e.preventDefault(); emit('prev'); }}
  }});
}})();
</script>
"""


def prepare_rows(rows: List[Dict[str, Any]], downsample_max: int = 200000) -> List[Dict[str, Any]]:
    if len(rows) <= downsample_max:
        return rows
    step = max(1, len(rows) // downsample_max)
    return rows[::step]


def build_timeseries_figure(state: Dict[str, Any], selected_channels: Optional[List[str]] = None) -> go.Figure:
    rows = state.get("rows", [])
    if not rows:
        return go.Figure().update_layout(title="No log loaded", height=420)

    df = pd.DataFrame(rows)
    if "timestamp" not in df.columns:
        df["timestamp"] = range(len(df))

    channels = selected_channels or state.get("selected_channels") or DEFAULT_VIEW_CHANNELS
    fig = go.Figure()

    for ch in channels:
        if ch not in df.columns:
            continue
        fig.add_trace(
            go.Scattergl(
                x=df["timestamp"],
                y=df[ch],
                name=ch,
                mode="lines",
                line=dict(width=1.6),
            )
        )

    if "KnockCount" in df.columns:
        knock_df = df[df["KnockCount"] > 0]
        if not knock_df.empty:
            fig.add_trace(
                go.Scattergl(
                    x=knock_df["timestamp"],
                    y=knock_df.get(channels[0], pd.Series([0] * len(knock_df))),
                    mode="markers",
                    marker=dict(color="red", size=6),
                    name="Knock Events",
                    hovertemplate="Knock at %{x}<extra></extra>",
                )
            )

    if "InjectorDuty_pct" in df.columns:
        duty_df = df[df["InjectorDuty_pct"] > 85]
        if not duty_df.empty:
            fig.add_trace(
                go.Scattergl(
                    x=duty_df["timestamp"],
                    y=duty_df.get(channels[0], pd.Series([0] * len(duty_df))),
                    mode="markers",
                    marker=dict(color="yellow", size=5),
                    name="High Duty >85%",
                    hovertemplate="High duty at %{x}<extra></extra>",
                )
            )

    cursor = int(state.get("cursor", 0) or 0)
    if len(df) > 0 and 0 <= cursor < len(df):
        ts = float(df.iloc[cursor]["timestamp"])
        fig.add_vline(x=ts, line_width=1, line_color="#f97316", line_dash="dash")

    fig.update_layout(
        title=f"Log Playback: {state.get('filename', 'unknown')}",
        xaxis_title="Time (s)",
        yaxis_title="Channel Value",
        hovermode="x unified",
        height=450,
    )
    return fig


def build_scatter_figure(state: Dict[str, Any], x_channel: str, y_channel: str) -> go.Figure:
    rows = state.get("rows", [])
    if not rows:
        return go.Figure().update_layout(title="No scatter data", height=360)

    df = pd.DataFrame(rows)
    if x_channel not in df.columns or y_channel not in df.columns:
        return go.Figure().update_layout(title=f"Missing channel(s): {x_channel}, {y_channel}", height=360)

    fig = go.Figure()
    fig.add_trace(
        go.Scattergl(
            x=df[x_channel],
            y=df[y_channel],
            mode="markers",
            marker=dict(size=4, opacity=0.55, color="#60a5fa"),
            name=f"{y_channel} vs {x_channel}",
        )
    )

    if len(df) >= 2:
        try:
            coeff = pd.Series(df[y_channel]).corr(pd.Series(df[x_channel]))
            poly = np.polyfit(df[x_channel].astype(float), df[y_channel].astype(float), 1)
            x_sorted = df[x_channel].astype(float).sort_values()
            y_line = poly[0] * x_sorted + poly[1]
            fig.add_trace(go.Scatter(x=x_sorted, y=y_line, mode="lines", name=f"Regression (r={coeff:.3f})", line=dict(color="#f97316")))
        except Exception:
            pass

    fig.update_layout(title=f"Scatter: {y_channel} vs {x_channel}", xaxis_title=x_channel, yaxis_title=y_channel, height=380)
    return fig


def build_filtered_table(
    state: Dict[str, Any],
    filter_expr: str,
    page: int,
    page_size: int,
) -> Tuple[pd.DataFrame, int]:
    rows = state.get("rows", [])
    if not rows:
        return pd.DataFrame(), 0

    df = pd.DataFrame(rows)
    if filter_expr and filter_expr.strip():
        try:
            df = df.query(filter_expr)
        except Exception:
            pass

    total_pages = max(1, int((len(df) + page_size - 1) / page_size))
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    end = start + page_size
    return df.iloc[start:end].copy(), total_pages


def apply_math_formula(state: Dict[str, Any], formula: str) -> Dict[str, Any]:
    rows = state.get("rows", [])
    if not rows or "=" not in formula:
        return state

    left, right = formula.split("=", 1)
    channel_name = left.strip()
    expr = right.strip()
    if not channel_name or not expr:
        return state

    safe_expr = _sanitize_formula(expr)
    if not safe_expr:
        return state

    df = pd.DataFrame(rows)
    local_vars = {col: df[col] for col in df.columns}

    try:
        values = eval(compile(ast.parse(safe_expr, mode="eval"), "<formula>", "eval"), {"__builtins__": {}}, local_vars)
        df[channel_name] = values
        state["rows"] = df.to_dict(orient="records")
        channels = set(state.get("channels", []))
        channels.add(channel_name)
        state["channels"] = sorted(channels)
        mc = dict(state.get("math_channels", {}))
        mc[channel_name] = formula
        state["math_channels"] = mc
    except Exception:
        return state

    return state


def summarize_log_for_ai(state: Dict[str, Any]) -> Dict[str, Any]:
    rows = state.get("rows", [])
    if not rows:
        return {"samples": 0}

    df = pd.DataFrame(rows)
    summary = {
        "filename": state.get("filename"),
        "samples": len(df),
        "duration_sec": float(df["timestamp"].max() - df["timestamp"].min()) if "timestamp" in df.columns else 0.0,
        "channels": list(df.columns),
        "max_rpm": float(df["RPM"].max()) if "RPM" in df.columns else 0.0,
        "avg_afr": float(df["AFR"].mean()) if "AFR" in df.columns else 0.0,
        "knock_events": int((df["KnockCount"] > 0).sum()) if "KnockCount" in df.columns else 0,
        "max_injector_duty": float(df["InjectorDuty_pct"].max()) if "InjectorDuty_pct" in df.columns else 0.0,
    }
    return summary


def format_recording_status(status: Dict[str, Any]) -> str:
    elapsed = int(status.get("elapsed_sec", 0))
    hh = elapsed // 3600
    mm = (elapsed % 3600) // 60
    ss = elapsed % 60
    samples = int(status.get("samples", 0))
    est_bytes = samples * 200
    mb = est_bytes / (1024 * 1024)
    state = "Recording" if status.get("recording") else "Idle"
    return f"{state}: {hh:02d}:{mm:02d}:{ss:02d} • {samples:,} samples • File size {mb:.1f}MB"


def _sanitize_formula(expr: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+-*/(). <>!=&|%")
    if not set(expr) <= allowed:
        return ""
    return expr
