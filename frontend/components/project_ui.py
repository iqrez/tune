import json
from typing import Any, Dict, List

import pandas as pd
import plotly.graph_objects as go


def default_project_state() -> Dict[str, Any]:
    return {
        "current": "untitled",
        "projects": [],
        "history": [],
        "file_tree": [],
        "last_compare": {},
    }


def build_project_timeline_html(history: List[Dict[str, Any]]) -> str:
    if not history:
        return "<div style='padding:8px;color:#94a3b8'>No versions yet.</div>"
    rows = []
    for h in history:
        ts = h.get("timestamp", 0)
        rows.append(
            "<div style='border-bottom:1px solid #334155;padding:8px'>"
            f"<div style='font-weight:700'>v{h.get('version')} | {h.get('table_name','table')}</div>"
            f"<div style='font-size:12px;color:#94a3b8'>{ts:.0f} | {h.get('summary','')}</div>"
            "</div>"
        )
    return "<div style='max-height:280px;overflow:auto;border:1px solid #334155;border-radius:8px'>" + "".join(rows) + "</div>"


def build_file_tree_html(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "<div style='padding:8px;color:#94a3b8'>No files.</div>"
    lines = []
    for it in items:
        icon = "[DIR]" if it.get("type") == "dir" else "[FILE]"
        lines.append(f"<div style='padding:3px 6px;font-family:Consolas,monospace'>{icon} {it.get('path','')}</div>")
    return "<div style='max-height:320px;overflow:auto;border:1px solid #334155;border-radius:8px'>" + "".join(lines) + "</div>"


def build_delta_heatmap(diff_json: Dict[str, Any]) -> go.Figure:
    delta = (diff_json or {}).get("delta", [])
    fig = go.Figure()
    if not delta:
        fig.update_layout(title="Delta Heatmap (no diff)", height=340)
        return fig
    fig.add_trace(
        go.Heatmap(
            z=delta,
            colorscale="RdYlGn",
            zmid=0,
            hovertemplate="Row=%{y}<br>Col=%{x}<br>Delta=%{z}<extra></extra>",
        )
    )
    fig.update_layout(title="Tune Delta Heatmap", xaxis_title="Col", yaxis_title="Row", height=360)
    return fig


def build_compare_tables(diff_json: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
    left = pd.DataFrame((diff_json or {}).get("left", []))
    right = pd.DataFrame((diff_json or {}).get("right", []))
    delta = pd.DataFrame((diff_json or {}).get("delta", []))
    return {"left": left, "right": right, "delta": delta}


def build_shortcuts_html(payload_id: str, trigger_id: str) -> str:
    return f"""
<div style='font-size:12px;color:#94a3b8;padding:4px 0'>Shortcuts: Ctrl+N new project, Ctrl+O open project, Ctrl+Shift+Z rollback</div>
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
    if (e.ctrlKey && e.key.toLowerCase() === 'n') {{ e.preventDefault(); emit('new'); }}
    if (e.ctrlKey && e.key.toLowerCase() === 'o') {{ e.preventDefault(); emit('open'); }}
    if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'z') {{ e.preventDefault(); emit('rollback'); }}
  }});
}})();
</script>
"""
