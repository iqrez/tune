import json
from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def default_dyno_state() -> Dict[str, Any]:
    return {
        "last_3d": {},
        "last_result": {},
        "last_stream_events": [],
        "units": "imperial",
        "last_peak": 0.0,
    }


def build_3d_table_figure(
    table_name: str,
    data: List[List[float]],
    rpm_axis: List[float],
    map_axis: List[float],
    log_hits: List[Dict[str, Any]] = None,
    corrections: List[Dict[str, Any]] = None,
) -> go.Figure:
    fig = go.Figure()
    if not data:
        fig.update_layout(title=f"{table_name} 3D Surface (no data)", height=500)
        return fig

    fig.add_trace(
        go.Surface(
            x=rpm_axis,
            y=map_axis,
            z=data,
            colorscale="RdBu",
            hovertemplate="RPM=%{x}<br>MAP=%{y}<br>Value=%{z}<extra></extra>",
            name=table_name,
        )
    )

    if log_hits:
        xs = [float(h.get("rpm", h.get("RPM", 0))) for h in log_hits]
        ys = [float(h.get("map", h.get("MAP_kPa", 0))) for h in log_hits]
        zs = [float(h.get("value", h.get("VE", h.get("IgnitionTiming", 0)))) for h in log_hits]
        fig.add_trace(
            go.Scatter3d(
                x=xs,
                y=ys,
                z=zs,
                mode="markers",
                marker=dict(size=3, color="#22c55e", opacity=0.7),
                name="Log Hits",
            )
        )

    if corrections:
        xs = [float(c.get("rpm", 0)) for c in corrections]
        ys = [float(c.get("map", 0)) for c in corrections]
        zs = [float(c.get("after", c.get("value", 0))) for c in corrections]
        colors = [float(c.get("delta_pct", 0)) for c in corrections]
        fig.add_trace(
            go.Scatter3d(
                x=xs,
                y=ys,
                z=zs,
                mode="markers",
                marker=dict(size=4, color=colors or [0], colorscale="RdYlGn", opacity=0.9),
                name="Corrections",
            )
        )

    fig.update_layout(
        title=f"{table_name} 3D Surface",
        scene=dict(xaxis_title="RPM", yaxis_title="MAP/Load", zaxis_title="Value"),
        height=560,
        margin=dict(l=0, r=0, b=0, t=45),
    )
    return fig


def build_slice_figure(data: List[List[float]], rpm_axis: List[float], map_axis: List[float], map_index: int = 0) -> go.Figure:
    fig = go.Figure()
    if not data:
        fig.update_layout(title="Slice View (no data)", height=280)
        return fig
    idx = max(0, min(len(data) - 1, int(map_index)))
    row = data[idx]
    fig.add_trace(go.Scatter(x=rpm_axis, y=row, mode="lines+markers", name=f"MAP {map_axis[idx]:.1f}"))
    fig.update_layout(title="2D Slice (MAP row cut)", xaxis_title="RPM", yaxis_title="Value", height=300)
    return fig


def build_dyno_figure(result: Dict[str, Any], units: str = "imperial") -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    curves = (result or {}).get("curves", [])
    if not curves:
        fig.update_layout(title="Dyno Curves (no data)", height=520)
        return fig

    x = [float(p.get("rpm", 0)) for p in curves]
    y_power = [float(p.get("power", 0)) for p in curves]
    y_torque = [float(p.get("torque", 0)) for p in curves]
    y_afr = [float(p.get("afr", 0)) for p in curves]
    y_boost = [float(p.get("boost_kpa", 0)) for p in curves]
    knock = [float(p.get("knock", 0)) for p in curves]

    power_name = "HP" if units == "imperial" else "kW"
    torque_name = "ft-lb" if units == "imperial" else "Nm"

    fig.add_trace(go.Scatter(x=x, y=y_power, mode="lines", name=power_name, line=dict(color="#60a5fa", width=3)), secondary_y=False)
    fig.add_trace(go.Scatter(x=x, y=y_torque, mode="lines", name=torque_name, line=dict(color="#f97316", width=3)), secondary_y=False)
    fig.add_trace(go.Scatter(x=x, y=y_afr, mode="lines", name="AFR", line=dict(color="#22c55e", dash="dot")), secondary_y=True)
    fig.add_trace(go.Scatter(x=x, y=y_boost, mode="lines", name="Boost kPa", line=dict(color="#a855f7", dash="dash")), secondary_y=True)

    kx = [x[i] for i, kv in enumerate(knock) if kv > 0]
    ky = [y_power[i] for i, kv in enumerate(knock) if kv > 0]
    if kx:
        fig.add_trace(
            go.Scatter(
                x=kx,
                y=ky,
                mode="markers",
                marker=dict(color="red", size=7),
                name="Knock Events",
            ),
            secondary_y=False,
        )

    # Powerband highlight
    fig.add_vrect(x0=4000, x1=7000, fillcolor="rgba(37,99,235,0.08)", line_width=0)

    peaks = (result or {}).get("peaks", {})
    peak_rpm = float(peaks.get("peak_hp_rpm", 0) or 0)
    peak_power = float(peaks.get("peak_hp", peaks.get("peak_kw", 0)) or 0)
    if peak_rpm > 0:
        fig.add_trace(
            go.Scatter(
                x=[peak_rpm],
                y=[peak_power],
                mode="markers+text",
                marker=dict(size=10, color="#f43f5e"),
                text=[f"Peak {power_name}"],
                textposition="top center",
                name="Peak",
            ),
            secondary_y=False,
        )

    fig.update_layout(
        title="Dyno View: Power/Torque vs RPM",
        xaxis_title="RPM",
        yaxis_title=f"Power/Torque ({power_name}, {torque_name})",
        legend=dict(orientation="h"),
        hovermode="x unified",
        height=560,
        margin=dict(l=30, r=30, t=50, b=30),
    )
    fig.update_yaxes(title_text="AFR / Boost", secondary_y=True)
    return fig


def summarize_dyno(result: Dict[str, Any], units: str = "imperial") -> str:
    if not result:
        return "No dyno result"
    peaks = result.get("peaks", {})
    warnings = result.get("warnings", [])
    if units == "metric":
        peak_power = peaks.get("peak_kw", 0)
        power_unit = "kW"
        peak_torque = peaks.get("peak_torque_nm", 0)
        tq_unit = "Nm"
    else:
        peak_power = peaks.get("peak_hp", 0)
        power_unit = "HP"
        peak_torque = peaks.get("peak_torque_ftlb", 0)
        tq_unit = "ft-lb"

    text = [
        f"Peak Power: {peak_power:.2f} {power_unit} @ {peaks.get('peak_hp_rpm', 0):.0f} RPM",
        f"Peak Torque: {peak_torque:.2f} {tq_unit} @ {peaks.get('peak_torque_rpm', 0):.0f} RPM",
        f"Powerband AUC: {float(result.get('auc_power', 0)):.2f}",
    ]
    if warnings:
        text.append("Warnings: " + " | ".join(warnings[:4]))
    return "\n".join(text)


def build_curve_table(result: Dict[str, Any]) -> pd.DataFrame:
    curves = (result or {}).get("curves", [])
    return pd.DataFrame(curves)


def build_shortcuts_html(payload_id: str, trigger_id: str) -> str:
    return f"""
<div style='font-size:12px;color:#94a3b8;padding:4px 0'>Shortcuts: R run test, E export, Z zoom peaks</div>
<script>
(function() {{
  const payloadId = {payload_id!r};
  const triggerId = {trigger_id!r};
  function emit(action) {{
    const inp = document.querySelector(`#${{payloadId}} textarea`) || document.querySelector(`#${{payloadId}} input`);
    const btn = document.querySelector(`#${{triggerId}} button`);
    if (!inp || !btn) return;
    inp.value = JSON.stringify({{action}});
    inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
    btn.click();
  }}
  document.addEventListener('keydown', function(e) {{
    const active = document.activeElement;
    if (active && ['INPUT', 'TEXTAREA'].includes(active.tagName)) return;
    if (e.key.toLowerCase() === 'r') {{ e.preventDefault(); emit('run'); }}
    if (e.key.toLowerCase() === 'e') {{ e.preventDefault(); emit('export'); }}
    if (e.key.toLowerCase() === 'z') {{ e.preventDefault(); emit('zoom'); }}
  }});
}})();
</script>
"""
