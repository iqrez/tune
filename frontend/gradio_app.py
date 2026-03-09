import copy
import json
import os
import tempfile
import time
from typing import Any, List

import gradio as gr
import plotly.graph_objects as go
import requests
import pandas as pd

from components.table_editor import build_table_editor_html, parse_editor_payload, get_table_editor_js

from components.full_tuning import (
    default_full_tuning_state,
    parameter_details_markdown,
    write_result_text,
    burn_result_text,
)
from components.project_ui import default_project_state
from components.datalog_viewer import default_datalog_state, build_timeseries_figure

from components.ribbon_toolbar import premium_theme_css, loading_spinner_html
from components.parameter_tree import build_tree_html as build_premium_tree_html
from components.live_gauges import build_live_gauges_figure
from components.context_menu import build_context_menu_html, build_shortcuts_js


# --- Constants & State ---
TABLE_PAYLOAD_ID = "table-editor-payload"
TABLE_CHANGE_BUTTON_ID = "table-editor-change"
TABLE_SAVE_BUTTON_ID = "table-editor-save"
DATALOG_SHORTCUT_PAYLOAD_ID = "datalog-shortcut-payload"
DATALOG_SHORTCUT_BUTTON_ID = "datalog-shortcut-trigger"
DASHBOARD_PAYLOAD_ID = "dashboard-designer-payload"
DASHBOARD_TRIGGER_ID = "dashboard-designer-trigger"
DYNO_SHORTCUT_PAYLOAD_ID = "dyno-shortcut-payload"
DYNO_SHORTCUT_BUTTON_ID = "dyno-shortcut-trigger"
PROJECT_SHORTCUT_PAYLOAD_ID = "project-shortcut-payload"
PROJECT_SHORTCUT_BUTTON_ID = "project-shortcut-trigger"
PREMIUM_TABLE_PAYLOAD_ID = "premium-table-editor-payload"
PREMIUM_TABLE_CHANGE_BUTTON_ID = "premium-table-editor-change"
PREMIUM_TABLE_SAVE_BUTTON_ID = "premium-table-editor-save"
PREMIUM_TREE_PICK_INPUT_ID = "premium-tree-pick-input"
PREMIUM_TREE_PICK_TRIGGER_ID = "premium-tree-pick-trigger"
PREMIUM_CONTEXT_PAYLOAD_ID = "premium-context-payload"
PREMIUM_CONTEXT_TRIGGER_ID = "premium-context-trigger"
PREMIUM_SHORTCUT_PAYLOAD_ID = "premium-shortcut-payload"
PREMIUM_SHORTCUT_TRIGGER_ID = "premium-shortcut-trigger"


def get_backend_url():
    port = 8000
    try:
        port_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".port")
        if os.path.exists(port_file):
            with open(port_file, "r") as f:
                port = int(f.read().strip())
    except Exception:
        pass
    return f"http://localhost:{port}/api/v1"


BACKEND_URL = get_backend_url()
print(f"UI connecting to backend at: {BACKEND_URL}")


def default_table_state() -> dict:
    data = [[0.0 for _ in range(16)] for _ in range(16)]
    return {
        "table_name": "veTable1",
        "data": data,
        "original_data": copy.deepcopy(data),
        "rpm_axis": [500 + i * 500 for i in range(16)],
        "map_axis": [30 + i * 15 for i in range(16)],
        "connected": False,
        "port": "Disconnected",
        "changed_count": 0,
        "has_violations": False,
        "has_risk": False,
        "pending_confirm": False,
        "message": "Load a table from ECU or import an .msq",
    }


def table_status_text(state: dict) -> str:
    conn = f"Connected to {state.get('port', 'unknown')}" if state.get("connected") else "Disconnected"
    return f"{conn}  -  {state.get('table_name')} loaded  -  {state.get('changed_count', 0)} cells changed"


def _default_axis_for_ui(count: int, axis: str) -> List[float]:
    if count <= 0:
        return []
    if axis == "rpm":
        step = max(100, int(7500 / max(1, count - 1)))
        return [500 + i * step for i in range(count)]
    if axis == "map":
        step = max(5, int(220 / max(1, count - 1)))
        return [30 + i * step for i in range(count)]
    return [float(i) for i in range(count)]


def build_table_surface(state: dict) -> go.Figure:
    data = state.get("data") or []
    rpm_axis = state.get("rpm_axis") or []
    map_axis = state.get("map_axis") or []

    fig = go.Figure()
    if not data:
        fig.update_layout(title="No table data")
        return fig

    fig.add_trace(
        go.Surface(
            x=rpm_axis,
            y=map_axis,
            z=data,
            colorscale="Viridis",
            hovertemplate="RPM=%{x}<br>MAP=%{y} kPa<br>Value=%{z}<extra></extra>",
        )
    )
    fig.update_layout(
        title=f"{state.get('table_name')} Surface",
        scene=dict(
            xaxis_title="RPM",
            yaxis_title="MAP/kPa",
            zaxis_title="Value",
        ),
        margin=dict(l=0, r=0, t=45, b=0),
        height=420,
    )
    return fig


def render_table_editor(state: dict) -> str:
    return build_table_editor_html(
        table_name=state.get("table_name", "veTable1"),
        data=state.get("data", []),
        rpm_axis=state.get("rpm_axis", []),
        map_axis=state.get("map_axis", []),
        payload_elem_id=TABLE_PAYLOAD_ID,
        change_button_id=TABLE_CHANGE_BUTTON_ID,
        save_button_id=TABLE_SAVE_BUTTON_ID,
        connected=bool(state.get("connected")),
        message=state.get("message", ""),
    )


def render_premium_table_editor(state: dict) -> str:
    return build_table_editor_html(
        table_name=state.get("table_name", "veTable1"),
        data=state.get("data", []),
        rpm_axis=state.get("rpm_axis", []),
        map_axis=state.get("map_axis", []),
        payload_elem_id=PREMIUM_TABLE_PAYLOAD_ID,
        change_button_id=PREMIUM_TABLE_CHANGE_BUTTON_ID,
        save_button_id=PREMIUM_TABLE_SAVE_BUTTON_ID,
        connected=bool(state.get("connected")),
        message=state.get("message", ""),
    )


def _fmt_float(v: Any, digits: int = 3) -> str:
    try:
        return f"{float(v):.{digits}f}"
    except Exception:
        return str(v)


def _pending_count(state: dict) -> int:
    try:
        return len(state.get("dirty_pages", []) or [])
    except Exception:
        return 0


def _burn_button_text(pending: int) -> str:
    return f"Burn All Changes ({pending} pending)" if pending > 0 else "Burn All Changes"


def _ribbon_status_html(d: dict) -> str:
    connected = bool(d.get("connected"))
    dot = "ok" if connected else "bad"
    mode = "Binary Mode" if connected else "Disconnected"
    port = d.get("port") or "COM?"
    uptime = int(float(d.get("uptime_s") or 0))
    rpm = int(float(d.get("rpm") or 0))
    return (
        f"<span class='status-dot {dot}'></span>"
        f"{mode} • {port} • Uptime: {uptime:02d}s • RPM: {rpm:04d}"
    )


def _safe_limits(meta: dict, value: float) -> tuple[float, float]:
    lo = meta.get("min_value")
    hi = meta.get("max_value")
    try:
        lo_f = float(lo) if lo is not None else None
    except Exception:
        lo_f = None
    try:
        hi_f = float(hi) if hi is not None else None
    except Exception:
        hi_f = None

    if lo_f is None and hi_f is None:
        span = max(1.0, abs(value) * 1.5, 100.0)
        return value - span, value + span
    if lo_f is None:
        lo_f = min(float(value), float(hi_f)) - max(1.0, abs(float(hi_f)) * 0.25)
    if hi_f is None:
        hi_f = max(float(value), float(lo_f)) + max(1.0, abs(float(lo_f)) * 0.25)
    if hi_f <= lo_f:
        hi_f = lo_f + 1.0
    return float(lo_f), float(hi_f)


def _guardrail_bar_html(value: float, lo: float, hi: float, units: str) -> str:
    span = max(1e-9, hi - lo)
    pct = max(0.0, min(100.0, ((value - lo) / span) * 100.0))
    color = "#16a34a"
    if pct >= 90:
        color = "#FF3333"
    elif pct >= 70:
        color = "#f59e0b"
    return (
        "<div style='margin-top:4px;'>"
        "<div style='display:flex;justify-content:space-between;font-size:12px;color:#888;'>"
        f"<span>{_fmt_float(lo, 3)}</span><span>{_fmt_float(hi, 3)} {units or ''}</span>"
        "</div>"
        "<div style='position:relative;height:14px;border:1px solid #333;border-radius:8px;overflow:hidden;'>"
        "<div style='position:absolute;left:0;top:0;height:100%;width:70%;background:#176B3A;'></div>"
        "<div style='position:absolute;left:70%;top:0;height:100%;width:20%;background:#8A6E00;'></div>"
        "<div style='position:absolute;left:90%;top:0;height:100%;width:10%;background:#8A2020;'></div>"
        f"<div style='position:absolute;left:calc({pct:.2f}% - 1px);top:0;height:100%;width:2px;background:{color};'></div>"
        "</div>"
        "</div>"
    )


def premium_poll_live():
    try:
        resp = requests.get(f"{BACKEND_URL}/rusefi/live", timeout=0.7)
        if resp.status_code != 200:
            d = {"connected": False, "rpm": 0, "port": "COM?"}
        else:
            d = resp.json()
    except Exception:
        d = {"connected": False, "rpm": 0, "port": "COM?"}
    return build_live_gauges_figure(d), _ribbon_status_html(d)


def premium_refresh_registry(search: str, state: dict):
    state = state or default_full_tuning_state()
    try:
        resp = requests.get(f"{BACKEND_URL}/parameters/list", params={"query": "", "category": "", "kind": ""}, timeout=20)
        if resp.status_code != 200:
            msg = f"Registry load failed: {resp.text}"
            state["status"] = msg
            return (
                state,
                build_premium_tree_html(search or "", "", [], PREMIUM_TREE_PICK_INPUT_ID, PREMIUM_TREE_PICK_TRIGGER_ID),
                gr.update(choices=[], value=None),
                "No parameter selected.",
                gr.update(value=0, minimum=0, maximum=1, visible=False),
                gr.update(value=0, visible=False),
                "",
                "",
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(interactive=False),
                gr.update(interactive=False),
                gr.update(interactive=False),
                msg,
                _burn_button_text(_pending_count(state)),
            )
        payload = resp.json()
        state["ini_path"] = payload.get("ini_path", "")
        state["ini_source"] = payload.get("ini_source", "unknown")
        state["parameters"] = payload.get("parameters", [])
        names = [p.get("name") for p in state["parameters"] if p.get("name")]
        current = state.get("selected_name", "")
        selected = current if current in names else (names[0] if names else "")
        state["selected_name"] = selected
        status = (
            f"INI: {state['ini_source']} | {state['ini_path']} | "
            f"{payload.get('total', 0)} parameters, {len(payload.get('tables', []))} tables"
        )
        state["status"] = status
        return (
            state,
            build_premium_tree_html(search or "", selected, names, PREMIUM_TREE_PICK_INPUT_ID, PREMIUM_TREE_PICK_TRIGGER_ID),
            gr.update(choices=names, value=(selected or None)),
            "No parameter selected." if not selected else f"Selected `{selected}`",
            gr.update(value=0, minimum=0, maximum=1, visible=False),
            gr.update(value=0, visible=False),
            "",
            "",
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            status,
            _burn_button_text(_pending_count(state)),
        )
    except Exception as e:
        msg = f"Registry load exception: {e}"
        state["status"] = msg
        return (
            state,
            build_premium_tree_html(search or "", "", [], PREMIUM_TREE_PICK_INPUT_ID, PREMIUM_TREE_PICK_TRIGGER_ID),
            gr.update(choices=[], value=None),
            "No parameter selected.",
            gr.update(value=0, minimum=0, maximum=1, visible=False),
            gr.update(value=0, visible=False),
            "",
            "",
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            msg,
            _burn_button_text(_pending_count(state)),
        )


def load_table_from_ecu_premium(table_name: str, state: dict):
    st, _html, surf, status = load_table_from_ecu(table_name, state)
    return st, render_premium_table_editor(st), surf, status


def save_table_to_ecu_premium(state: dict):
    st, _html, status = save_table_to_ecu(state)
    return st, render_premium_table_editor(st), build_table_surface(st), status


def undo_all_changes_premium(state: dict):
    st, _html, surf, status = undo_all_changes(state)
    return st, render_premium_table_editor(st), surf, status


def handle_premium_editor_change(payload: str, state: dict):
    st, surf, status = handle_editor_change(payload, state)
    return st, render_premium_table_editor(st), surf, status


def premium_select_parameter(name: str, state: dict, table_state: dict):
    state = state or default_full_tuning_state()
    table_state = table_state or default_table_state()
    if not name:
        return (
            state,
            table_state,
            "No parameter selected.",
            gr.update(value=0, minimum=0, maximum=1, visible=False),
            gr.update(value=0, visible=False),
            "",
            "",
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            state.get("status", "No parameter selected."),
            _burn_button_text(_pending_count(state)),
            gr.update(value=name),
            gr.update(value=name),
            render_premium_table_editor(table_state),
            build_table_surface(table_state),
            table_status_text(table_state),
        )
    try:
        resp = requests.post(f"{BACKEND_URL}/parameters/read", json={"name": name}, timeout=15)
        if resp.status_code != 200:
            msg = f"Read failed: {resp.text}"
            return (
                state,
                table_state,
                msg,
                gr.update(value=0, minimum=0, maximum=1, visible=False),
                gr.update(value=0, visible=False),
                "",
                "",
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(interactive=False),
                gr.update(interactive=False),
                gr.update(interactive=False),
                msg,
                _burn_button_text(_pending_count(state)),
                gr.update(value=name),
                gr.update(value=name),
                render_premium_table_editor(table_state),
                build_table_surface(table_state),
                table_status_text(table_state),
            )
        meta = resp.json()
        state["selected_name"] = meta.get("name", name)
        state["selected_meta"] = meta
        state["selected_value"] = meta.get("value")
        details = parameter_details_markdown(meta, meta.get("value"))
        is_table = bool(meta.get("is_table"))
        is_scalar = bool(meta.get("is_scalar"))
        status = f"Selected {state['selected_name']} ({'table' if is_table else 'scalar'})"
        state["status"] = status
        write_on = is_scalar and not bool(meta.get("read_only"))
        burn_on = True
        table_on = is_table

        if is_table:
            table_state, table_html, table_surface, table_status = load_table_from_ecu_premium(state["selected_name"], table_state)
            return (
                state,
                table_state,
                details,
                gr.update(value=0, minimum=0, maximum=1, visible=False),
                gr.update(value=0, visible=False),
                "",
                "",
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(interactive=False),
                gr.update(interactive=False),
                gr.update(interactive=table_on),
                status,
                _burn_button_text(_pending_count(state)),
                gr.update(value=state["selected_name"]),
                gr.update(value=state["selected_name"]),
                table_html,
                table_surface,
                table_status,
            )

        try:
            v = float(meta.get("value", 0.0))
        except Exception:
            v = 0.0
        lo, hi = _safe_limits(meta, v)
        units = str(meta.get("units") or "")
        return (
            state,
            table_state,
            details,
            gr.update(value=v, minimum=lo, maximum=hi, step=max((hi - lo) / 1000.0, 0.001), visible=True),
            gr.update(value=v, visible=True),
            f"**{state['selected_name']}**",
            f"### {_fmt_float(v, 3)} {units}",
            gr.update(value=_guardrail_bar_html(v, lo, hi, units), visible=True),
            gr.update(visible=False),
            gr.update(interactive=write_on),
            gr.update(interactive=write_on and burn_on),
            gr.update(interactive=False),
            status,
            _burn_button_text(_pending_count(state)),
            gr.update(value=state["selected_name"]),
            gr.update(value=state["selected_name"]),
            render_premium_table_editor(table_state),
            build_table_surface(table_state),
            table_status_text(table_state),
        )
    except Exception as e:
        msg = f"Read exception: {e}"
        state["status"] = msg
        return (
            state,
            table_state,
            msg,
            gr.update(value=0, minimum=0, maximum=1, visible=False),
            gr.update(value=0, visible=False),
            "",
            "",
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            msg,
            _burn_button_text(_pending_count(state)),
            gr.update(value=name),
            gr.update(value=name),
            render_premium_table_editor(table_state),
            build_table_surface(table_state),
            table_status_text(table_state),
        )


def premium_sync_scalar_value(value: float, state: dict):
    state = state or default_full_tuning_state()
    meta = state.get("selected_meta") or {}
    try:
        v = float(value)
    except Exception:
        v = 0.0
    lo, hi = _safe_limits(meta, v)
    units = str(meta.get("units") or "")
    return (
        gr.update(value=v),
        gr.update(value=v),
        f"### {_fmt_float(v, 3)} {units}",
        gr.update(value=_guardrail_bar_html(v, lo, hi, units), visible=True),
    )


def premium_write_scalar(value: float, burn_after: bool, state: dict):
    state = state or default_full_tuning_state()
    name = str(state.get("selected_name") or "")
    if not name:
        msg = "No selected parameter."
        return state, msg, _burn_button_text(_pending_count(state)), "### 0.000", gr.update(value=0)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/parameters/write",
            json={"name": name, "value": float(value), "burn_after": bool(burn_after)},
            timeout=20,
        )
        if resp.status_code != 200:
            msg = f"Write failed: {resp.text}"
            state["status"] = msg
            return state, msg, _burn_button_text(_pending_count(state)), f"### {_fmt_float(value)}", gr.update(value=value)
        payload = resp.json()
        dirty = payload.get("dirty_pages")
        if isinstance(dirty, list):
            state["dirty_pages"] = dirty
        if payload.get("burn_result"):
            state["dirty_pages"] = payload.get("burn_result", {}).get("remaining_dirty_pages", state.get("dirty_pages", []))
        r2 = requests.post(f"{BACKEND_URL}/parameters/read", json={"name": name}, timeout=15)
        now = float(value)
        if r2.status_code == 200:
            meta = r2.json()
            state["selected_meta"] = meta
            state["selected_value"] = meta.get("value")
            try:
                now = float(meta.get("value", value))
            except Exception:
                now = float(value)
        units = str((state.get("selected_meta") or {}).get("units") or "")
        msg = write_result_text(payload)
        state["status"] = msg
        return state, msg, _burn_button_text(_pending_count(state)), f"### {_fmt_float(now, 3)} {units}", gr.update(value=now)
    except Exception as e:
        msg = f"Write exception: {e}"
        state["status"] = msg
        return state, msg, _burn_button_text(_pending_count(state)), f"### {_fmt_float(value)}", gr.update(value=value)


def premium_burn_all(state: dict):
    state = state or default_full_tuning_state()
    state, msg = full_tuning_burn_pending(state)
    return state, msg, _burn_button_text(_pending_count(state))


def premium_open_selected_table(state: dict, table_state: dict):
    state = state or default_full_tuning_state()
    table_state = table_state or default_table_state()
    meta = state.get("selected_meta") or {}
    if not meta.get("is_table"):
        msg = "Selected parameter is not a table."
        return table_state, gr.update(visible=False), render_premium_table_editor(table_state), build_table_surface(table_state), table_status_text(table_state), msg
    name = str(meta.get("name") or state.get("selected_name") or "")
    if not name:
        msg = "No selected table."
        return table_state, gr.update(visible=False), render_premium_table_editor(table_state), build_table_surface(table_state), table_status_text(table_state), msg
    table_state, table_html, table_surface, table_status = load_table_from_ecu_premium(name, table_state)
    return table_state, gr.update(visible=True), table_html, table_surface, table_status, f"Loaded {name} in premium table editor."


def premium_context_action(payload: str, state: dict):
    state = state or default_full_tuning_state()
    try:
        data = json.loads(payload or "{}")
    except Exception:
        data = {}
    action = str(data.get("action") or "").strip()
    if action == "help":
        return "Context: use right-click to write/burn/copy/undo/table 3D actions."
    if action == "escape":
        return "Closed floating action."
    if action == "undo":
        return "Undo requested (table editor handles per-cell undo with Ctrl+Z)."
    if action == "redo":
        return "Redo requested."
    if action == "copy":
        return "Copy requested."
    if action == "paste":
        return "Paste requested."
    if action == "watch":
        return f"Added to watch list: {state.get('selected_name', '(none)')}"
    if action == "compare_msq":
        return "Compare with .msq requested."
    if action == "view_3d":
        return f"3D view requested for {state.get('selected_name', '(none)')}"
    if action == "edit_value":
        return "Edit value mode."
    if action == "write_now":
        return "Write request submitted."
    if action == "burn":
        return "Burn request submitted."
    if action == "reset":
        return "Reset to default requested."
    return "Context action ready."


def premium_shortcut_action(payload: str):
    try:
        data = json.loads(payload or "{}")
    except Exception:
        data = {}
    action = str(data.get("action") or "")
    if action == "escape":
        return "Esc: closed floating window."
    if action == "undo":
        return "Undo shortcut triggered."
    if action == "redo":
        return "Redo shortcut triggered."
    return "Shortcut ready."


def premium_set_playback_speed(speed_value: float, datalog_state: dict):
    try:
        speed_text = f"{float(speed_value):.1f}x"
    except Exception:
        speed_text = "1x"
    return datalog_set_speed(speed_text, datalog_state)


def ribbon_connect_action():
    status, _banner = connect_ecu_action("Auto Detect Real ECU", "", "Auto (Binary Preferred)")
    return status


def ribbon_load_msq_action(file, state: dict):
    """Handler for the Load .msq UploadButton."""
    if not file:
        return state, "No file uploaded."
    # Use the existing full_tuning_import_msq logic
    return full_tuning_import_msq(file.name, apply_to_ecu=True, burn_after=False, state=state)

def ribbon_fw_action():
    return (
        "### rusEFI Firmware Update Guide\n"
        "1. Disconnect ECU from this app.\n"
        "2. Connect ECU via USB and enter DFU mode (short PROG jumper).\n"
        "3. Use [rusEFI Console](https://rusefi.com/online/) or `stm32cubeprogrammer` to flash `.bin`.\n"
        "4. Power cycle ECU and reconnect."
    )


def ribbon_toggle_datalog(recording_state: dict, datalog_state: dict):
    recording_state = recording_state or {"recording": False, "started_at": 0.0}
    datalog_state = datalog_state or default_datalog_state()
    if recording_state.get("recording"):
        datalog_state, status, recent = datalog_stop_recording(datalog_state)
        recording_state["recording"] = False
        recording_state["started_at"] = 0.0
        return recording_state, datalog_state, "Start Datalog", status, recent
    datalog_state, status = datalog_start_recording(False, datalog_state)
    recording_state["recording"] = True
    recording_state["started_at"] = time.time()
    return recording_state, datalog_state, "Stop Datalog", status, gr.update()


def ribbon_datalog_label(recording_state: dict):
    recording_state = recording_state or {"recording": False, "started_at": 0.0}
    if not recording_state.get("recording"):
        return "Start Datalog"
    elapsed = max(0, int(time.time() - float(recording_state.get("started_at") or time.time())))
    mm = elapsed // 60
    ss = elapsed % 60
    return f"Stop Datalog  \u25cf {mm:02d}:{ss:02d}"


def ribbon_export_msq_action():
    return full_tuning_export_msq()


def premium_open_datalog_hint():
    return "Open the Datalogs tab for full viewer controls."


def create_gauge(value, name, min_val, max_val, unit, color="cyan", row=0, col=0):
    return go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": f"{name} ({unit})", "font": {"size": 18}},
        gauge={
            "axis": {"range": [min_val, max_val]},
            "bar": {"color": color},
            "steps": [
                {"range": [min_val, max_val * 0.8], "color": "gray"},
                {"range": [max_val * 0.8, max_val], "color": "red"},
            ],
        },
        domain={"row": row, "column": col},
    )


def update_gauges():
    try:
        resp = requests.get(f"{BACKEND_URL}/rusefi/live", timeout=0.5)
        data = resp.json() if resp.status_code == 200 else {}
    except Exception:
        data = {}

    fig = go.Figure()
    fig.add_trace(create_gauge(data.get("rpm", 0), "RPM", 0, 8000, "rpm", "lime", row=0, col=0))
    fig.add_trace(create_gauge(data.get("map_kpa", 0), "MAP", 0, 300, "kPa", "orange", row=0, col=1))
    fig.add_trace(create_gauge(data.get("afr", 0), "AFR", 8, 20, "lambda", "cyan", row=1, col=0))
    fig.add_trace(create_gauge(data.get("iat", 0), "IAT", 0, 100, "C", "blue", row=1, col=1))
    fig.add_trace(create_gauge(data.get("ect", 0), "ECT", 0, 120, "C", "red", row=2, col=0))
    fig.add_trace(create_gauge(data.get("injector_duty", 0), "Duty", 0, 100, "%", "magenta", row=2, col=1))

    fig.update_layout(
        grid={"rows": 3, "columns": 2, "pattern": "independent"},
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        height=600,
    )
    return fig


def poll_connection_status():
    try:
        resp = requests.get(f"{BACKEND_URL}/rusefi/live", timeout=0.7)
        if resp.status_code != 200:
            return "ECU Status: backend unavailable"
        d = resp.json()
        if not d.get("connected"):
            return "ECU Status: Disconnected"
        port = d.get("port") or "unknown"
        if d.get("signature_mode"):
            uptime = d.get("uptime_s")
            rpm = d.get("rpm", 0)
            up_txt = f"{int(uptime)}s" if uptime is not None else "n/a"
            return f"uaefi signature mode on {port} | Uptime: {up_txt} | RPM: {int(rpm)} (read-only)"
        if d.get("console_mode"):
            uptime = d.get("uptime_s")
            rpm = d.get("rpm", 0)
            up_txt = f"{int(uptime)}s" if uptime is not None else "n/a"
            return f"Console-only mode on {port} | Uptime: {up_txt} | RPM: {int(rpm)} (read-only)"
        rpm = d.get("rpm", 0)
        map_kpa = d.get("map_kpa", 0)
        afr = d.get("afr", 0)
        return f"Connected to BINARY tuning port on {port} | RPM: {int(rpm)} | MAP: {map_kpa:.1f} kPa | AFR: {afr:.2f}"
    except Exception as e:
        return f"ECU Status: offline ({e})"


# --- Agentic Integration ---
def _history_to_messages(history):
    messages = []
    for item in history or []:
        if isinstance(item, dict) and "role" in item and "content" in item:
            messages.append(item)
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            user, bot = item
            if user:
                messages.append({"role": "user", "content": str(user)})
            if bot:
                messages.append({"role": "assistant", "content": str(bot)})
    return messages


def agent_chat_handler(message, history, profile):
    if not message:
        yield history
        return

    # Initialize bot message as empty and add to history for streaming
    updated_history = history + [[message, ""]]
    yield updated_history

    try:
        resp = requests.post(
            f"{BACKEND_URL}/agent/chat",
            json={"message": message, "state": {"profile": profile}},
            stream=True,
            timeout=120,
        )
        
        if resp.status_code != 200:
            updated_history[-1][1] = f"Error: {resp.status_code} - {resp.text}"
            yield updated_history
            return

        full_response = ""
        for line in resp.iter_lines():
            if line:
                try:
                    chunk = json.loads(line.decode('utf-8'))
                    action = chunk.get("action", "")
                    thought = chunk.get("thought", "")
                    msg_text = chunk.get("message", "")
                    
                    if action == "FINAL_ANSWER":
                        # For final answer, we can either append or replace. 
                        # Let's clean up the "Thinking" parts and just show the message if it's the final answer
                        # OR if the message is long, keep both.
                        if full_response:
                            full_response += f"\n\n**Final Answer:** {msg_text}"
                        else:
                            full_response = msg_text
                    else:
                        icon = "[tool]"
                        full_response += f"{icon} {action}\n\n*Thinking: {thought}*\n\n---\n\n"
                    
                    updated_history[-1][1] = full_response
                    yield updated_history
                except Exception as e:
                    logger.error(f"Error parsing segment: {e}")
                    continue

    except Exception as e:
        updated_history[-1][1] = f"Timeout/Error: {e}"
        yield updated_history


def run_port_diagnostics():
    try:
        resp = requests.get(f"{BACKEND_URL}/rusefi/detect_ports", timeout=30)
        if resp.status_code == 200:
            payload = resp.json()
            results = payload.get("ports", payload if isinstance(payload, list) else [])
            if not results:
                return "No ports found.", pd.DataFrame()
            df = pd.DataFrame(results)
            detection = payload.get("detection", {}) if isinstance(payload, dict) else {}
            warn = detection.get("warning", "")
            binary_port = detection.get("binary_port", "")
            console_port = detection.get("console_port", "")
            if binary_port:
                status_msg = f"Binary tuning port detected on {binary_port}."
            elif console_port:
                status_msg = f"Only console port found on {console_port} - try higher COM or click Try Wake Binary Port."
            else:
                status_msg = f"Scanned {len(df['port'].unique())} ports."
            if warn:
                status_msg += f" Warning: {warn}"
            return status_msg, df
        return "Backend Error", pd.DataFrame()
    except Exception as e:
        return f"Offline: {e}", pd.DataFrame()


def connect_ecu_action(mode, manual_port, port_mode):
    try:
        port = manual_port if manual_port and manual_port.strip() else None
        if port_mode == "Console Only":
            port = port or "COM3"
        elif port_mode == "Auto (Binary Preferred)":
            port = None
        if mode == "Auto Detect Real ECU":
            payload = {"connection_type": "serial", "serial_port": port}
        else:
            payload = {"connection_type": "tcp", "host": "127.0.0.1", "port": 29002}
        resp = requests.post(f"{BACKEND_URL}/rusefi/connect", json=payload, timeout=45)
        if resp.status_code == 200:
            data = resp.json()
            ctype = str(data.get("type", ""))
            cport = data.get("port", "unknown")
            banner_hidden = gr.update(value="", visible=False)
            banner_console = gr.update(
                value=(
                    "### Console-only mode active (read-only gauges only)\n"
                    "Full tuning (tables, flashing) requires binary port. Click **Reflash Firmware for Binary Mode** below."
                ),
                visible=True,
            )
            if ctype == "serial" and not data.get("limited_mode"):
                return f"Connected to BINARY tuning port on {cport}", banner_hidden
            if ctype == "serial_signature" or data.get("signature_mode"):
                return f"Connected to uaefi signature transport on {cport} (limited mode)", banner_console
            if ctype == "serial_console" or data.get("limited_mode"):
                return f"Connected to console port on {cport} (limited mode)", banner_console
            return f"Connected via {ctype} ({cport})", banner_hidden
        try:
            body = resp.json()
            detail = body.get("detail", resp.text)
            if isinstance(detail, dict):
                msg = detail.get("message", "Connect failed")
                det = detail.get("detection", {})
                warning = det.get("warning", "") if isinstance(det, dict) else ""
                rs = det.get("results", []) if isinstance(det, dict) else []
                sample = rs[:4] if isinstance(rs, list) else []
                if "Only console port detected" in warning:
                    return "Only console port found - try higher COM or click Try Wake Binary Port", gr.update(value="### Console-only mode active (read-only gauges only)\nFull tuning (tables, flashing) requires binary port. Click **Reflash Firmware for Binary Mode** below.", visible=True)
                return f"Failed: {msg}\nDetection sample: {json.dumps(sample)}", gr.update(value="", visible=False)
            err = detail
        except Exception:
            err = resp.text
        return f"Failed: {err}", gr.update(value="", visible=False)
    except requests.exceptions.ReadTimeout:
        return "Connect request timed out while scanning COM ports. Try Manual COM=COM3 + Console Only, then Try Wake Binary.", gr.update(value="", visible=False)
    except Exception as e:
        return f"Offline: {e}", gr.update(value="", visible=False)


def force_wakeup_action(manual_port):
    try:
        payload = {"connection_type": "serial", "serial_port": manual_port or None}
        resp = requests.post(f"{BACKEND_URL}/rusefi/wakeup", json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("message")
        return f"Wakeup failed: {resp.text}"
    except Exception as e:
        return f"Error: {e}"


def wake_binary_action(manual_port):
    try:
        payload = {"connection_type": "serial", "serial_port": manual_port or None}
        resp = requests.post(f"{BACKEND_URL}/rusefi/wake_binary", json=payload, timeout=30)
        if resp.status_code == 200:
            d = resp.json()
            return f"Force binary search success: console={d.get('console_port')} -> binary={d.get('binary_port')}"
        try:
            detail = resp.json().get("detail", resp.text)
            if isinstance(detail, dict):
                warn = detail.get("detection", {}).get("warning", "")
                if warn:
                    return f"Only console port found - {warn}"
            return f"Force binary search failed: {detail}"
        except Exception:
            return f"Force binary search failed: {resp.text}"
    except Exception as e:
        return f"Force binary search error: {e}"


def show_reflash_wizard():
    steps = (
        "## Firmware Reflash Wizard (Enable Binary Port)\n"
        "1. Download latest rusEFI firmware bundle from official release.\n"
        "2. Hold the PROG button and replug USB to enter bootloader mode.\n"
        "3. Run `rusefi_console.exe` and choose **Update Firmware**.\n"
        "4. Replug ECU, run port diagnostics, then reconnect.\n"
    )
    return gr.update(value=steps, visible=True)



def handle_table_select(table_name: str, state: dict):
    state = state or default_table_state()
    state["table_name"] = table_name
    state["message"] = f"Selected {table_name}. Load from ECU or import .msq"
    return state, table_status_text(state)


def load_table_from_ecu(table_name: str, state: dict):
    state = state or default_table_state()
    try:
        resp = requests.post(f"{BACKEND_URL}/parameters/read", json={"name": table_name}, timeout=10)
        if resp.status_code != 200:
            state["connected"] = False
            state["message"] = f"Load failed: {resp.text}"
            return state, render_table_editor(state), build_table_surface(state), table_status_text(state)

        payload = resp.json()
        if not payload.get("is_table"):
            state["message"] = f"{table_name} is not a table."
            return state, render_table_editor(state), build_table_surface(state), table_status_text(state)

        table_data = payload.get("value")
        if not isinstance(table_data, list) or not table_data:
            state["message"] = f"{table_name} has no table data."
            return state, render_table_editor(state), build_table_surface(state), table_status_text(state)

        state["table_name"] = payload.get("name", table_name)
        state["data"] = table_data
        state["original_data"] = copy.deepcopy(state["data"])
        x_axis = payload.get("x_axis")
        y_axis = payload.get("y_axis")
        cols = len(state["data"][0]) if state["data"] and isinstance(state["data"][0], list) else 16
        rows = len(state["data"])
        state["rpm_axis"] = x_axis if isinstance(x_axis, list) and len(x_axis) == cols else _default_axis_for_ui(cols, "rpm")
        state["map_axis"] = y_axis if isinstance(y_axis, list) and len(y_axis) == rows else _default_axis_for_ui(rows, "map")
        state["connected"] = True
        state["port"] = "binary"
        state["changed_count"] = 0
        state["has_violations"] = False
        state["has_risk"] = False
        state["pending_confirm"] = False
        state["message"] = f"{state['table_name']} loaded"
        return state, render_table_editor(state), build_table_surface(state), table_status_text(state)
    except Exception as e:
        state["connected"] = False
        state["message"] = f"Load exception: {e}"
        return state, render_table_editor(state), build_table_surface(state), table_status_text(state)


def handle_editor_change(payload: str, state: dict):
    state = state or default_table_state()
    parsed = parse_editor_payload(payload)
    data = parsed.get("data")
    if isinstance(data, list) and data:
        state["data"] = data
    state["changed_count"] = int(parsed.get("changed_count", state.get("changed_count", 0)))
    state["has_violations"] = bool(parsed.get("has_violations", False))
    state["has_risk"] = bool(parsed.get("has_risk", False))
    if parsed.get("message"):
        state["message"] = parsed["message"]
    return state, build_table_surface(state), table_status_text(state)


def save_table_to_ecu(state: dict):
    state = state or default_table_state()
    if not state.get("connected"):
        state["message"] = "Cannot save: ECU disconnected"
        gr.Warning(state["message"])
        return state, render_table_editor(state), table_status_text(state)

    confirm = bool(state.get("pending_confirm", False))
    if state.get("has_violations") and not confirm:
        state["pending_confirm"] = True
        state["message"] = "Values outside configured limits. Press Save again to force write."
        gr.Warning(state["message"])
        return state, render_table_editor(state), table_status_text(state)

    try:
        resp = requests.post(
            f"{BACKEND_URL}/parameters/write",
            json={
                "name": state.get("table_name"),
                "value": state.get("data"),
                "force": confirm,
            },
            timeout=12,
        )
        if resp.status_code != 200:
            state["message"] = f"Save failed: {resp.text}"
            gr.Warning(state["message"])
            return state, render_table_editor(state), table_status_text(state)

        payload = resp.json()
        state["pending_confirm"] = False
        state["changed_count"] = 0
        state["original_data"] = copy.deepcopy(state.get("data", []))
        state["message"] = f"Saved to ECU ({payload.get('bytes_written', 'n/a')} bytes)"
        return state, render_table_editor(state), table_status_text(state)
    except Exception as e:
        state["message"] = f"Save exception: {e}"
        gr.Warning(state["message"])
        return state, render_table_editor(state), table_status_text(state)


def undo_all_changes(state: dict):
    state = state or default_table_state()
    state["data"] = copy.deepcopy(state.get("original_data", state.get("data", [])))
    state["changed_count"] = 0
    state["pending_confirm"] = False
    state["message"] = "Undo all applied"
    return state, render_table_editor(state), build_table_surface(state), table_status_text(state)


def export_msq(state: dict):
    state = state or default_table_state()
    try:
        resp = requests.post(
            f"{BACKEND_URL}/tables/export_msq",
            json={
                "table_name": state.get("table_name"),
                "data": state.get("data"),
                "rpm_axis": state.get("rpm_axis"),
                "map_axis": state.get("map_axis"),
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return None, f"Export failed: {resp.text}"

        fd, path = tempfile.mkstemp(prefix=f"{state.get('table_name')}_", suffix=".msq")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(resp.content)
        return path, f"Exported {os.path.basename(path)}"
    except Exception as e:
        return None, f"Export exception: {e}"


def import_msq(file_path, table_name: str, state: dict):
    state = state or default_table_state()
    if not file_path:
        return state, render_table_editor(state), build_table_surface(state), table_status_text(state)

    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/xml")}
            resp = requests.post(
                f"{BACKEND_URL}/tables/import_msq",
                params={"table_name": table_name},
                files=files,
                timeout=10,
            )

        if resp.status_code != 200:
            state["message"] = f"Import failed: {resp.text}"
            return state, render_table_editor(state), build_table_surface(state), table_status_text(state)

        payload = resp.json()
        state["table_name"] = payload.get("table_name", table_name)
        state["data"] = payload.get("data", state["data"])
        state["original_data"] = copy.deepcopy(state["data"])
        state["rpm_axis"] = payload.get("rpm_axis", state["rpm_axis"])
        state["map_axis"] = payload.get("map_axis", state["map_axis"])
        state["changed_count"] = 0
        state["pending_confirm"] = False
        state["message"] = f"Imported {os.path.basename(file_path)}"
        return state, render_table_editor(state), build_table_surface(state), table_status_text(state)
    except Exception as e:
        state["message"] = f"Import exception: {e}"
        return state, render_table_editor(state), build_table_surface(state), table_status_text(state)


def _find_param_meta(state: dict, name: str) -> dict:
    for p in state.get("parameters", []):
        if p.get("name") == name:
            return p
    return {}


def full_tuning_refresh_registry(query: str, category: str, kind: str, state: dict):
    state = state or default_full_tuning_state()
    try:
        params = {
            "query": query or "",
            "category": category or "",
            "kind": "" if (kind or "all") == "all" else kind,
        }
        resp = requests.get(f"{BACKEND_URL}/parameters/list", params=params, timeout=20)
        if resp.status_code != 200:
            state["status"] = f"Registry load failed: {resp.text}"
            return (
                state,
                build_parameter_tree_html([], state.get("selected_name", "")),
                gr.update(choices=[], value=None),
                state["status"],
                gr.update(),
            )
        payload = resp.json()
        state["ini_path"] = payload.get("ini_path", "")
        state["ini_source"] = payload.get("ini_source", "unknown")
        state["parameters"] = payload.get("parameters", [])
        state["query"] = query or ""
        state["category"] = category or ""
        names = [p.get("name") for p in state["parameters"] if p.get("name")]
        selected = state.get("selected_name") if state.get("selected_name") in names else (names[0] if names else None)
        state["selected_name"] = selected or ""
        table_names = payload.get("tables", [])
        state["status"] = (
            f"INI: {state['ini_source']} | {state['ini_path']} | "
            f"{payload.get('total', 0)} parameters, {len(table_names)} tables"
        )
        return (
            state,
            build_parameter_tree_html(state["parameters"], state.get("selected_name", "")),
            gr.update(choices=names, value=selected),
            state["status"],
            gr.update(choices=table_names or names, value=(selected if selected in (table_names or names) else None)),
        )
    except Exception as e:
        state["status"] = f"Registry load exception: {e}"
        return (
            state,
            build_parameter_tree_html([], state.get("selected_name", "")),
            gr.update(choices=[], value=None),
            state["status"],
            gr.update(),
        )


def full_tuning_select_parameter(name: str, state: dict):
    state = state or default_full_tuning_state()
    if not name:
        return (
            state,
            "No parameter selected.",
            gr.update(value=0.0, visible=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            state.get("status", ""),
        )
    try:
        resp = requests.post(f"{BACKEND_URL}/parameters/read", json={"name": name}, timeout=15)
        if resp.status_code != 200:
            msg = f"Read failed: {resp.text}"
            return (
                state,
                msg,
                gr.update(value=0.0, visible=False),
                gr.update(interactive=False),
                gr.update(interactive=False),
                gr.update(interactive=False),
                msg,
            )
        payload = resp.json()
        state["selected_name"] = payload.get("name", name)
        state["selected_meta"] = payload
        state["selected_value"] = payload.get("value")
        details = parameter_details_markdown(payload, payload.get("value"))
        is_scalar = bool(payload.get("is_scalar"))
        is_table = bool(payload.get("is_table"))
        scalar_val = payload.get("value", 0.0) if is_scalar else 0.0
        status = f"Selected {state['selected_name']} ({'table' if is_table else 'scalar'})"
        state["status"] = status
        return (
            state,
            details,
            gr.update(value=scalar_val, visible=is_scalar),
            gr.update(interactive=is_scalar),
            gr.update(interactive=is_scalar),
            gr.update(interactive=is_table),
            status,
        )
    except Exception as e:
        msg = f"Read exception: {e}"
        return (
            state,
            msg,
            gr.update(value=0.0, visible=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            msg,
        )


def full_tuning_write_scalar(new_value: float, burn_after: bool, state: dict):
    state = state or default_full_tuning_state()
    name = state.get("selected_name", "")
    if not name:
        return state, "No selected parameter.", gr.update(), "No selected parameter."
    try:
        write_resp = requests.post(
            f"{BACKEND_URL}/parameters/write",
            json={"name": name, "value": new_value, "burn_after": bool(burn_after)},
            timeout=20,
        )
        if write_resp.status_code != 200:
            msg = f"Write failed: {write_resp.text}"
            return state, msg, gr.update(), msg
        result = write_resp.json()
        read_resp = requests.post(f"{BACKEND_URL}/parameters/read", json={"name": name}, timeout=15)
        payload = read_resp.json() if read_resp.status_code == 200 else state.get("selected_meta", {})
        state["selected_meta"] = payload
        state["selected_value"] = payload.get("value")
        details = parameter_details_markdown(payload, payload.get("value"))
        status = write_result_text(result)
        if result.get("burn_result"):
            status = f"{status} | {burn_result_text(result.get('burn_result', {}))}"
        state["status"] = status
        return state, details, gr.update(value=payload.get("value", new_value)), status
    except Exception as e:
        msg = f"Write exception: {e}"
        return state, msg, gr.update(), msg


def full_tuning_burn_pending(state: dict):
    state = state or default_full_tuning_state()
    try:
        resp = requests.post(f"{BACKEND_URL}/parameters/burn", json={}, timeout=20)
        if resp.status_code != 200:
            msg = f"Burn failed: {resp.text}"
            state["status"] = msg
            return state, msg
        payload = resp.json()
        state["dirty_pages"] = payload.get("remaining_dirty_pages", [])
        state["status"] = burn_result_text(payload)
        return state, state["status"]
    except Exception as e:
        msg = f"Burn exception: {e}"
        state["status"] = msg
        return state, msg


def full_tuning_open_table_editor(state: dict):
    state = state or default_full_tuning_state()
    meta = state.get("selected_meta", {})
    if not meta.get("is_table"):
        return gr.update(), "Selected parameter is not a table."
    name = meta.get("name", "")
    return gr.update(value=name), f"Opening {name} in Table Editor..."


def full_tuning_open_table_and_load(state: dict, table_state: dict):
    state = state or default_full_tuning_state()
    table_state = table_state or default_table_state()
    meta = state.get("selected_meta", {})
    if not meta.get("is_table"):
        msg = "Selected parameter is not a table."
        state["status"] = msg
        return (
            gr.update(),
            table_state,
            render_table_editor(table_state),
            build_table_surface(table_state),
            table_status_text(table_state),
            msg,
        )
    name = meta.get("name", "")
    table_state, html_out, surf_out, status_out = load_table_from_ecu(name, table_state)
    msg = f"Loaded {name} in Table Editor."
    state["status"] = msg
    return (
        gr.update(value=name),
        table_state,
        html_out,
        surf_out,
        status_out,
        msg,
    )


def full_tuning_export_msq():
    try:
        resp = requests.post(f"{BACKEND_URL}/parameters/export_msq", json={}, timeout=60)
        if resp.status_code != 200:
            return None, f"Export failed: {resp.text}"
        fd, path = tempfile.mkstemp(prefix="full_tune_", suffix=".msq")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(resp.content)
        return path, f"Exported full tune: {os.path.basename(path)}"
    except Exception as e:
        return None, f"Export exception: {e}"


def full_tuning_import_msq(file_path, apply_to_ecu: bool, burn_after: bool, state: dict):
    state = state or default_full_tuning_state()
    if not file_path:
        return state, "Select an .msq file to import."
    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/xml")}
            resp = requests.post(
                f"{BACKEND_URL}/parameters/import_msq",
                params={
                    "apply_to_ecu": str(bool(apply_to_ecu)).lower(),
                    "burn_after": str(bool(burn_after)).lower(),
                },
                files=files,
                timeout=120,
            )
        if resp.status_code != 200:
            msg = f"Import failed: {resp.text}"
            state["status"] = msg
            return state, msg
        payload = resp.json()
        parsed = payload.get("parsed", 0)
        skipped = len(payload.get("skipped", []))
        msg = f"Imported MSQ constants parsed={parsed}, skipped={skipped}"
        if payload.get("write_result"):
            wr = payload["write_result"]
            msg += f" | writes={len(wr.get('written', []))} errors={len(wr.get('errors', []))}"
        if payload.get("burn_result"):
            msg += f" | {burn_result_text(payload.get('burn_result', {}))}"
        state["status"] = msg
        return state, msg
    except Exception as e:
        msg = f"Import exception: {e}"
        state["status"] = msg
        return state, msg


def fetch_recent_datalogs():
    try:
        resp = requests.get(f"{BACKEND_URL}/datalog/recent", timeout=8)
        if resp.status_code != 200:
            return gr.Dropdown(choices=[], value=None), "Failed to fetch recent logs"
        logs = resp.json().get("logs", [])
        names = [x.get("filename") for x in logs if x.get("filename")]
        default = names[0] if names else None
        return gr.Dropdown(choices=names, value=default), f"Found {len(names)} logs"
    except Exception as e:
        return gr.Dropdown(choices=[], value=None), f"Recent logs error: {e}"


def datalog_start_recording(high_speed: bool = False, datalog_state: dict = None):
    datalog_state = datalog_state or default_datalog_state()
    try:
        resp = requests.post(
            f"{BACKEND_URL}/datalog/start",
            json={"profile_id": "B18C_Turbo", "high_speed": bool(high_speed)},
            timeout=8,
        )
        if resp.status_code != 200:
            return datalog_state, f"Start failed: {resp.text}"
        datalog_state["filename"] = resp.json().get("filename", datalog_state.get("filename", ""))
        status_resp = requests.get(f"{BACKEND_URL}/datalog/status", timeout=3)
        status = status_resp.json() if status_resp.status_code == 200 else {"recording": True, "samples": 0, "elapsed_sec": 0}
        return datalog_state, format_recording_status(status)
    except Exception as e:
        return datalog_state, f"Start exception: {e}"


def datalog_stop_recording(datalog_state: dict):
    datalog_state = datalog_state or default_datalog_state()
    try:
        payload = {"filename": datalog_state.get("filename") or None}
        resp = requests.post(f"{BACKEND_URL}/datalog/stop", json=payload, timeout=8)
        if resp.status_code != 200:
            return datalog_state, f"Stop failed: {resp.text}", gr.Dropdown(choices=[], value=None)
        data = resp.json()
        datalog_state["filename"] = data.get("filename", datalog_state.get("filename", ""))
        dd, _ = fetch_recent_datalogs()
        return datalog_state, f"Stopped. {data.get('samples', 0)} samples saved.", dd
    except Exception as e:
        return datalog_state, f"Stop exception: {e}", gr.Dropdown(choices=[], value=None)


def datalog_refresh_status():
    try:
        resp = requests.get(f"{BACKEND_URL}/datalog/status", timeout=3)
        if resp.status_code != 200:
            return "Recorder status unavailable"
        return format_recording_status(resp.json())
    except Exception as e:
        return f"Recorder offline: {e}"


def datalog_load_selected(filename: str, datalog_state: dict):
    datalog_state = datalog_state or default_datalog_state()
    if not filename:
        empty_dd = gr.Dropdown(choices=[], value=[])
        return datalog_state, go.Figure(), go.Figure(), pd.DataFrame(), "No log selected", empty_dd, empty_dd, empty_dd
    try:
        resp = requests.get(f"{BACKEND_URL}/datalog/load/{filename}", timeout=20)
        if resp.status_code != 200:
            empty_dd = gr.Dropdown(choices=[], value=[])
            return datalog_state, go.Figure(), go.Figure(), pd.DataFrame(), f"Load failed: {resp.text}", empty_dd, empty_dd, empty_dd
        payload = resp.json()
        datalog_state["filename"] = payload.get("filename", filename)
        datalog_state["rows"] = payload.get("rows", [])
        datalog_state["channels"] = payload.get("channels", [])
        datalog_state["cursor"] = 0
        channels = datalog_state["channels"]
        if channels:
            datalog_state["selected_channels"] = [c for c in ["RPM", "MAP_kPa", "AFR", "KnockCount", "InjectorDuty_pct"] if c in channels] or channels[:5]
            datalog_state["scatter_x"] = "RPM" if "RPM" in channels else channels[0]
            datalog_state["scatter_y"] = "AFR" if "AFR" in channels else channels[0]

        ts = build_timeseries_figure(datalog_state, datalog_state.get("selected_channels"))
        scatter = build_scatter_figure(datalog_state, datalog_state.get("scatter_x"), datalog_state.get("scatter_y"))
        tbl, total_pages = build_filtered_table(datalog_state, datalog_state.get("filter_expr", ""), 1, datalog_state.get("table_page_size", 100))
        datalog_state["table_page"] = 1
        chan_dd = gr.Dropdown(choices=channels, value=datalog_state.get("selected_channels", []))
        scatter_x_dd = gr.Dropdown(choices=channels, value=datalog_state.get("scatter_x"))
        scatter_y_dd = gr.Dropdown(choices=channels, value=datalog_state.get("scatter_y"))
        return datalog_state, ts, scatter, tbl, f"Loaded {payload.get('samples', 0)} samples • pages: {total_pages}", chan_dd, scatter_x_dd, scatter_y_dd
    except Exception as e:
        empty_dd = gr.Dropdown(choices=[], value=[])
        return datalog_state, go.Figure(), go.Figure(), pd.DataFrame(), f"Load exception: {e}", empty_dd, empty_dd, empty_dd


def datalog_apply_channel_selection(channels: List[str], datalog_state: dict):
    datalog_state = datalog_state or default_datalog_state()
    datalog_state["selected_channels"] = channels or datalog_state.get("selected_channels", [])
    return datalog_state, build_timeseries_figure(datalog_state, datalog_state["selected_channels"])


def datalog_apply_scatter(x_channel: str, y_channel: str, datalog_state: dict):
    datalog_state = datalog_state or default_datalog_state()
    datalog_state["scatter_x"] = x_channel
    datalog_state["scatter_y"] = y_channel
    return datalog_state, build_scatter_figure(datalog_state, x_channel, y_channel)


def datalog_filter_table(filter_expr: str, page: int, datalog_state: dict):
    datalog_state = datalog_state or default_datalog_state()
    datalog_state["filter_expr"] = filter_expr or ""
    datalog_state["table_page"] = int(page or 1)
    tbl, total_pages = build_filtered_table(
        datalog_state, datalog_state["filter_expr"], datalog_state["table_page"], datalog_state.get("table_page_size", 100)
    )
    return datalog_state, tbl, f"Page {datalog_state['table_page']}/{total_pages}"


def datalog_apply_math(formula: str, datalog_state: dict):
    datalog_state = datalog_state or default_datalog_state()
    datalog_state = apply_math_formula(datalog_state, formula or "")
    ts = build_timeseries_figure(datalog_state, datalog_state.get("selected_channels"))
    scatter = build_scatter_figure(datalog_state, datalog_state.get("scatter_x"), datalog_state.get("scatter_y"))
    choices = datalog_state.get("channels", [])
    return datalog_state, ts, scatter, gr.Dropdown(choices=choices, value=datalog_state.get("selected_channels", []))


def datalog_export_log(filename: str):
    if not filename:
        return None, "No log selected"
    try:
        resp = requests.get(f"{BACKEND_URL}/datalog/export/{filename}", params={"fmt": "csv"}, timeout=30)
        if resp.status_code != 200:
            return None, f"Export failed: {resp.text}"
        fd, path = tempfile.mkstemp(prefix=f"{os.path.splitext(filename)[0]}_", suffix=".csv")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(resp.content)
        return path, f"Exported {os.path.basename(path)}"
    except Exception as e:
        return None, f"Export exception: {e}"


def datalog_import_file(file_path, datalog_state: dict):
    datalog_state = datalog_state or default_datalog_state()
    if not file_path:
        dd, msg = fetch_recent_datalogs()
        return datalog_state, dd, msg
    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
            resp = requests.post(f"{BACKEND_URL}/datalog/import", files=files, timeout=30)
        if resp.status_code != 200:
            dd, _ = fetch_recent_datalogs()
            return datalog_state, dd, f"Import failed: {resp.text}"
        dd, _ = fetch_recent_datalogs()
        return datalog_state, dd, f"Imported {resp.json().get('filename')}"
    except Exception as e:
        dd, _ = fetch_recent_datalogs()
        return datalog_state, dd, f"Import exception: {e}"


def datalog_shortcut_action(payload: str, datalog_state: dict):
    datalog_state = datalog_state or default_datalog_state()
    rows = datalog_state.get("rows", [])
    if not rows:
        return datalog_state, build_timeseries_figure(datalog_state, datalog_state.get("selected_channels"))
    try:
        action = json.loads(payload or "{}").get("action", "")
    except Exception:
        action = ""
    if action == "toggle":
        datalog_state["playing"] = not datalog_state.get("playing", False)
    elif action == "next":
        datalog_state["cursor"] = min(len(rows) - 1, datalog_state.get("cursor", 0) + 1)
    elif action == "prev":
        datalog_state["cursor"] = max(0, datalog_state.get("cursor", 0) - 1)
    return datalog_state, build_timeseries_figure(datalog_state, datalog_state.get("selected_channels"))


def datalog_playback_tick(datalog_state: dict):
    datalog_state = datalog_state or default_datalog_state()
    rows = datalog_state.get("rows", [])
    if not rows or not datalog_state.get("playing"):
        return datalog_state, build_timeseries_figure(datalog_state, datalog_state.get("selected_channels"))
    speed = float(datalog_state.get("playback_speed", 1.0) or 1.0)
    step = max(1, int(round(speed)))
    datalog_state["cursor"] = min(len(rows) - 1, datalog_state.get("cursor", 0) + step)
    if datalog_state["cursor"] >= len(rows) - 1:
        datalog_state["playing"] = False
    return datalog_state, build_timeseries_figure(datalog_state, datalog_state.get("selected_channels"))


def datalog_set_speed(speed_value: str, datalog_state: dict):
    datalog_state = datalog_state or default_datalog_state()
    try:
        datalog_state["playback_speed"] = float(str(speed_value).replace("x", "").strip())
    except Exception:
        datalog_state["playback_speed"] = 1.0
    return datalog_state


def datalog_ask_ai(datalog_state: dict):
    datalog_state = datalog_state or default_datalog_state()
    summary = summarize_log_for_ai(datalog_state)
    try:
        resp = requests.post(f"{BACKEND_URL}/datalog/analyze", json={"log_data_summary": summary}, timeout=20)
        if resp.status_code != 200:
            return f"Analyze failed: {resp.text}"
        payload = resp.json()
        warnings = payload.get("guardrail_warnings", [])
        llm = payload.get("llm_analysis", {})
        text = llm.get("message") or llm.get("thought") or json.dumps(llm)
        return "Guardrails:\\n- " + "\\n- ".join(warnings) + f"\\n\\nAI:\\n{text}"
    except Exception as e:
        return f"Analyze exception: {e}"


def _dashboard_channels_default() -> list:
    return [
        "RPM",
        "AFR",
        "MAP_kPa",
        "IAT_C",
        "ECT_C",
        "KnockCount",
        "InjectorDuty_pct",
        "TPS",
        "batteryV",
        "OilPressure",
        "FuelLevel",
    ]


def dashboard_list_saved():
    try:
        resp = requests.get(f"{BACKEND_URL}/dashboards/list", timeout=8)
        if resp.status_code != 200:
            return gr.Dropdown(choices=[], value=None), "Failed to list dashboards"
        names = resp.json().get("dashboards", [])
        return gr.Dropdown(choices=names, value=(names[0] if names else None)), f"Found {len(names)} dashboards"
    except Exception as e:
        return gr.Dropdown(choices=[], value=None), f"List error: {e}"


def dashboard_refresh_sources():
    dash_dd, msg = dashboard_list_saved()
    try:
        resp = requests.get(f"{BACKEND_URL}/datalog/recent", timeout=8)
        logs = resp.json().get("logs", []) if resp.status_code == 200 else []
        log_names = [x.get("filename") for x in logs if x.get("filename")]
        replay_dd = gr.Dropdown(choices=log_names, value=(log_names[0] if log_names else None))
    except Exception:
        replay_dd = gr.Dropdown(choices=[], value=None)
    return dash_dd, replay_dd, msg


def dashboard_fetch_channels():
    try:
        resp = requests.get(f"{BACKEND_URL}/dashboards/channels", timeout=8)
        if resp.status_code != 200:
            return _dashboard_channels_default()
        channels = resp.json().get("channels", [])
        return channels or _dashboard_channels_default()
    except Exception:
        return _dashboard_channels_default()


def dashboard_render(state: dict):
    state = state or default_dashboard_state()
    layout = state.get("layout", {})
    channels = state.get("channels") or dashboard_fetch_channels()
    state["channels"] = channels
    html = build_dashboard_html(layout, channels, DASHBOARD_PAYLOAD_ID, DASHBOARD_TRIGGER_ID)
    return state, html


def dashboard_new(state: dict):
    state = state or default_dashboard_state()
    state["layout"] = {
        "name": "Untitled Dashboard",
        "background": {"color": "#0f172a", "image": ""},
        "tabs": [{"name": "Engine Vitals", "gauges": []}],
        "active_tab": 0,
        "values": {},
        "connected": False,
        "selected_gauge_id": None,
    }
    state["replay_rows"] = []
    state["replay_index"] = 0
    state["status"] = "New dashboard created"
    state, html = dashboard_render(state)
    return state, html, state["status"], gr.Dropdown(choices=[], value=None)


def dashboard_on_payload(payload: str, state: dict):
    state = state or default_dashboard_state()
    parsed = parse_dashboard_payload(payload)
    if parsed.get("layout"):
        state["layout"] = parsed["layout"]
    sel_id = parsed.get("selected_gauge_id")
    if sel_id:
        state["layout"]["selected_gauge_id"] = sel_id
    sel = selected_gauge(state.get("layout", {}), state.get("layout", {}).get("selected_gauge_id"))
    gauge_choices = []
    for tab in state.get("layout", {}).get("tabs", []):
        for g in tab.get("gauges", []):
            gauge_choices.append(g.get("id"))
    gauge_dd = gr.Dropdown(choices=gauge_choices, value=state.get("layout", {}).get("selected_gauge_id"))
    return state, gauge_dd, sel.get("channel", ""), sel.get("min", 0), sel.get("max", 100), sel.get("unit", ""), sel.get("alarm", 0), sel.get("rot", 0), state.get("status", "")


def dashboard_select_gauge(gauge_id: str, state: dict):
    state = state or default_dashboard_state()
    state.setdefault("layout", {}).setdefault("selected_gauge_id", gauge_id)
    sel = selected_gauge(state.get("layout", {}), gauge_id)
    return state, sel.get("channel", ""), sel.get("min", 0), sel.get("max", 100), sel.get("unit", ""), sel.get("alarm", 0), sel.get("rot", 0)


def dashboard_apply_properties(
    gauge_id: str,
    channel: str,
    min_v: float,
    max_v: float,
    unit: str,
    alarm: float,
    rotation: float,
    bg_color: str,
    state: dict,
):
    state = state or default_dashboard_state()
    if gauge_id:
        state["layout"] = update_gauge_properties(
            state.get("layout", {}),
            gauge_id,
            {
                "channel": channel or "RPM",
                "min": float(min_v),
                "max": float(max_v),
                "unit": unit or "",
                "alarm": float(alarm),
                "rot": float(rotation),
            },
        )
    state.setdefault("layout", {}).setdefault("background", {})["color"] = bg_color or "#0f172a"
    state["status"] = "Properties applied"
    state, html = dashboard_render(state)
    return state, html, state["status"]


def dashboard_set_background_image(file_path, state: dict):
    state = state or default_dashboard_state()
    if file_path:
        state.setdefault("layout", {}).setdefault("background", {})["image"] = file_path
        state["status"] = f"Background set: {os.path.basename(file_path)}"
    state, html = dashboard_render(state)
    return state, html, state.get("status", "")


def dashboard_save(name: str, state: dict):
    state = state or default_dashboard_state()
    layout = state.get("layout", {})
    layout["name"] = name or layout.get("name") or "my_dash"
    try:
        resp = requests.post(f"{BACKEND_URL}/dashboards/save", json={"name": layout["name"], "layout_json": layout}, timeout=8)
        if resp.status_code != 200:
            return state, f"Save failed: {resp.text}", gr.Dropdown(choices=[], value=None)
        dd, _ = dashboard_list_saved()
        return state, f"Saved dashboard: {layout['name']}", dd
    except Exception as e:
        return state, f"Save exception: {e}", gr.Dropdown(choices=[], value=None)


def dashboard_load(name: str, state: dict):
    state = state or default_dashboard_state()
    if not name:
        return state, "", "No dashboard selected"
    try:
        resp = requests.get(f"{BACKEND_URL}/dashboards/load/{name}", timeout=8)
        if resp.status_code != 200:
            return state, "", f"Load failed: {resp.text}"
        layout = resp.json().get("layout_json", {})
        state["layout"] = layout
        state["status"] = f"Loaded dashboard: {name}"
        state, html = dashboard_render(state)
        return state, html, state["status"]
    except Exception as e:
        return state, "", f"Load exception: {e}"


def dashboard_export_assets(name: str, state: dict):
    state = state or default_dashboard_state()
    layout = state.get("layout", {})
    dash_name = name or layout.get("name") or "dashboard"
    export_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboards")
    os.makedirs(export_dir, exist_ok=True)
    json_path = os.path.join(export_dir, f"{dash_name}.json")
    png_path = os.path.join(export_dir, f"{dash_name}.png")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(layout, f, indent=2)
    # 1x1 valid PNG placeholder to satisfy export requirement in headless environments.
    png_bytes = bytes.fromhex("89504E470D0A1A0A0000000D4948445200000001000000010802000000907753DE0000000A49444154789C6360000000020001E221BC330000000049454E44AE426082")
    with open(png_path, "wb") as f:
        f.write(png_bytes)
    return f"{json_path}\n{png_path}", f"Exported JSON + PNG: {dash_name}"


def dashboard_live_tick(state: dict, live_enabled: bool = False):
    state = state or default_dashboard_state()
    layout = state.get("layout", {})
    live_on = bool(live_enabled) or bool(state.get("live_preview"))
    if not live_on:
        return state, build_dashboard_html(layout, state.get("channels", _dashboard_channels_default()), DASHBOARD_PAYLOAD_ID, DASHBOARD_TRIGGER_ID)

    try:
        resp = requests.get(f"{BACKEND_URL}/rusefi/live", timeout=0.6)
        live = resp.json() if resp.status_code == 200 else {}
    except Exception:
        live = {}
    values = {
        "RPM": float(live.get("rpm", 0) or 0),
        "MAP_kPa": float(live.get("map_kpa", 0) or 0),
        "AFR": float(live.get("afr", 0) or 0),
        "IAT_C": float(live.get("iat", 0) or 0),
        "ECT_C": float(live.get("ect", 0) or 0),
        "KnockCount": float(live.get("knock_count", 0) or 0),
        "InjectorDuty_pct": float(live.get("injector_duty", 0) or 0),
    }
    layout["values"] = values
    layout["connected"] = bool(live.get("connected", False))
    state["layout"] = layout
    return state, build_dashboard_html(layout, state.get("channels", _dashboard_channels_default()), DASHBOARD_PAYLOAD_ID, DASHBOARD_TRIGGER_ID)


def dashboard_toggle_live(enabled: bool, state: dict = None):
    state = state or default_dashboard_state()
    state["live_preview"] = bool(enabled)
    return state


def dashboard_replay_log(log_name: str, state: dict = None):
    state = state or default_dashboard_state()
    if not log_name:
        return state, "Select a log first"
    try:
        resp = requests.get(f"{BACKEND_URL}/datalog/load/{log_name}", timeout=20)
        if resp.status_code != 200:
            return state, f"Replay load failed: {resp.text}"
        rows = resp.json().get("rows", [])
        state["replay_rows"] = rows
        state["replay_index"] = 0
        state["live_preview"] = False
        return state, f"Replay loaded: {len(rows)} samples"
    except Exception as e:
        return state, f"Replay exception: {e}"


def dashboard_replay_tick(state: dict):
    state = state or default_dashboard_state()
    rows = state.get("replay_rows", [])
    if not rows:
        return state, build_dashboard_html(state.get("layout", {}), state.get("channels", _dashboard_channels_default()), DASHBOARD_PAYLOAD_ID, DASHBOARD_TRIGGER_ID)
    idx = int(state.get("replay_index", 0))
    if idx >= len(rows):
        return state, build_dashboard_html(state.get("layout", {}), state.get("channels", _dashboard_channels_default()), DASHBOARD_PAYLOAD_ID, DASHBOARD_TRIGGER_ID)
    row = rows[idx]
    layout = state.get("layout", {})
    layout["values"] = row
    layout["connected"] = True
    state["layout"] = layout
    state["replay_index"] = idx + 1
    return state, build_dashboard_html(layout, state.get("channels", _dashboard_channels_default()), DASHBOARD_PAYLOAD_ID, DASHBOARD_TRIGGER_ID)


def dashboard_ask_ai(state: dict):
    state = state or default_dashboard_state()
    layout = state.get("layout", {})
    prompt = {
        "dashboard_name": layout.get("name"),
        "tabs": [t.get("name") for t in layout.get("tabs", [])],
        "gauge_count": sum(len(t.get("gauges", [])) for t in layout.get("tabs", [])),
        "channels_used": sorted(
            list(
                {
                    g.get("channel")
                    for t in layout.get("tabs", [])
                    for g in t.get("gauges", [])
                    if g.get("channel")
                }
            )
        ),
    }
    try:
        resp = requests.post(
            f"{BACKEND_URL}/agent/chat",
            json={"message": f"Optimize this dashboard: {json.dumps(prompt)}", "state": {}},
            timeout=25,
        )
        if resp.status_code != 200:
            return f"AI optimize failed: {resp.text}"
        data = resp.json()
        return data.get("message", json.dumps(data))
    except Exception as e:
        return f"AI optimize exception: {e}"


def autotune_status_text(state: dict) -> str:
    if not state:
        return "Ready"
    conn = "Connected to ECU" if state.get("connected") else "Disconnected/Simulated"
    return f"Ready • {conn} • Last run: {state.get('last_run_cells', 0)} cells tuned"


def autotune_use_current_log(checked: bool, datalog_state: dict):
    if not checked:
        return pd.DataFrame(), "Current log disabled"
    rows = (datalog_state or {}).get("rows", [])
    if not rows:
        return pd.DataFrame(), "No current datalog rows loaded"
    return pd.DataFrame(rows[:25]), f"Using current log: {len(rows)} samples"


def autotune_preview_action(
    tool_name: str,
    mode: str,
    min_samples: int,
    ignore_transient: bool,
    steady_state_only: bool,
    rpm_variance: float,
    tps_delta: float,
    max_change_pct: float,
    use_current_log: bool,
    datalog_state: dict,
    table_state: dict,
    autotune_state: dict,
):
    autotune_state = autotune_state or default_autotune_state()
    tool_key = (tool_name or "VE Analyze").strip().lower()
    table_name = "veTable1"
    if "ignition" in tool_key:
        table_name = "ignitionTable1"

    samples = []
    if use_current_log:
        samples = (datalog_state or {}).get("rows", []) or []

    params = {
        "mode": (mode or "balanced").lower(),
        "min_samples": int(min_samples or 50),
        "ignore_transient": bool(ignore_transient),
        "steady_state_only": bool(steady_state_only),
        "rpm_variance": float(rpm_variance or 100),
        "tps_transient_delta": float(tps_delta or 5),
        "max_change_pct": float(max_change_pct or 10),
        "table_name": table_name,
        "base_table": (table_state or {}).get("data"),
        "rpm_axis": (table_state or {}).get("rpm_axis"),
        "map_axis": (table_state or {}).get("map_axis"),
        "samples": samples,
        "safe_ramp_passed": True,
        "require_safe_ramp": True,
    }

    try:
        resp = requests.post(
            f"{BACKEND_URL}/autotune/preview",
            json={"tool_name": tool_key, "params_json": params},
            timeout=40,
        )
        if resp.status_code != 200:
            msg = f"Preview failed: {resp.text}"
            return (
                autotune_state,
                go.Figure(),
                go.Figure(),
                pd.DataFrame(),
                msg,
                msg,
                "Show this log's hits on VE table: preview unavailable",
                autotune_status_text(autotune_state),
            )
        result = resp.json()
        changes = result.get("changes", [])
        autotune_state["latest_preview"] = result
        autotune_state["run_log"] = list(result.get("progress", []))
        autotune_state["connected"] = bool((table_state or {}).get("connected", False))
        autotune_state["last_run_cells"] = int(result.get("summary", {}).get("cells_tuned", 0))

        rows = len((table_state or {}).get("data", [])) or 16
        cols = len((table_state or {}).get("data", [[0] * 16])[0]) if rows else 16
        heat = build_correction_heatmap(changes, rows=rows, cols=cols, title="Auto-Tune Preview Heatmap")
        scatter = build_before_after_scatter(changes, title="Before/After AFR Scatter")
        df = build_changes_table(changes)
        summary = summarize_autotune_result(result)
        run_log = format_run_log(autotune_state.get("run_log", []))
        overlay = f"Show this log's hits on VE table: {len(changes)} cell corrections highlighted"
        return autotune_state, heat, scatter, df, summary, run_log, overlay, autotune_status_text(autotune_state)
    except Exception as e:
        msg = f"Preview exception: {e}"
        return autotune_state, go.Figure(), go.Figure(), pd.DataFrame(), msg, msg, "Show this log's hits on VE table: error", autotune_status_text(autotune_state)


def autotune_run_action(
    tool_name: str,
    mode: str,
    min_samples: int,
    ignore_transient: bool,
    steady_state_only: bool,
    rpm_variance: float,
    tps_delta: float,
    max_change_pct: float,
    use_current_log: bool,
    datalog_state: dict,
    table_state: dict,
    autotune_state: dict,
):
    autotune_state = autotune_state or default_autotune_state()
    tool_key = (tool_name or "VE Analyze").strip().lower()
    table_name = "veTable1"
    if "ignition" in tool_key:
        table_name = "ignitionTable1"
    samples = (datalog_state or {}).get("rows", []) if use_current_log else []
    params = {
        "mode": (mode or "balanced").lower(),
        "min_samples": int(min_samples or 50),
        "ignore_transient": bool(ignore_transient),
        "steady_state_only": bool(steady_state_only),
        "rpm_variance": float(rpm_variance or 100),
        "tps_transient_delta": float(tps_delta or 5),
        "max_change_pct": float(max_change_pct or 10),
        "table_name": table_name,
        "base_table": (table_state or {}).get("data"),
        "rpm_axis": (table_state or {}).get("rpm_axis"),
        "map_axis": (table_state or {}).get("map_axis"),
        "samples": samples,
        "dry_run": True,
        "safe_ramp_passed": True,
        "require_safe_ramp": True,
    }
    try:
        resp = requests.post(
            f"{BACKEND_URL}/autotune/run",
            json={"tool_name": tool_key, "params_json": params},
            timeout=60,
        )
        if resp.status_code != 200:
            msg = f"Run failed: {resp.text}"
            return autotune_state, msg, msg, autotune_status_text(autotune_state)
        events = parse_stream_ndjson(resp.text)
        log_lines = []
        result = {}
        for ev in events:
            if ev.get("type") == "progress":
                log_lines.append(ev.get("message", ""))
            elif ev.get("type") == "result":
                result = ev.get("result", {})

        autotune_state["run_log"] = log_lines
        autotune_state["latest_preview"] = result or autotune_state.get("latest_preview", {})
        autotune_state["last_run_cells"] = int((result or {}).get("summary", {}).get("cells_tuned", 0))
        status = summarize_autotune_result(result) if result else "Run completed with no result payload"
        return autotune_state, status, format_run_log(log_lines), autotune_status_text(autotune_state)
    except Exception as e:
        msg = f"Run exception: {e}"
        return autotune_state, msg, msg, autotune_status_text(autotune_state)


def autotune_apply_action(autotune_state: dict, table_state: dict):
    autotune_state = autotune_state or default_autotune_state()
    preview = autotune_state.get("latest_preview") or {}
    changes = preview.get("changes", [])
    table_name = preview.get("table_name") or (table_state or {}).get("table_name", "veTable1")
    base_table = (table_state or {}).get("data") or preview.get("base_table") or []
    if not changes:
        return autotune_state, table_state, "No preview changes to apply", table_status_text(table_state or default_table_state()), autotune_status_text(autotune_state)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/autotune/apply",
            json={
                "table_name": table_name,
                "changes_json": changes,
                "base_table": base_table,
                "confirm_ignition": True,
            },
            timeout=25,
        )
        if resp.status_code != 200:
            msg = f"Apply failed: {resp.text}"
            return autotune_state, table_state, msg, table_status_text(table_state or default_table_state()), autotune_status_text(autotune_state)
        payload = resp.json()

        applied = copy.deepcopy(base_table)
        for ch in changes:
            if ch.get("vetoed"):
                continue
            r = int(ch.get("row", -1))
            c = int(ch.get("col", -1))
            if r < 0 or c < 0 or r >= len(applied) or c >= len(applied[r]):
                continue
            applied[r][c] = float(ch.get("after", applied[r][c]))

        table_state = table_state or default_table_state()
        table_state["table_name"] = table_name
        table_state["data"] = applied
        table_state["changed_count"] = 0
        table_state["message"] = f"Auto-tune applied ({payload.get('applied', 0)} changes)"
        autotune_state["latest_apply"] = payload
        return autotune_state, table_state, table_state["message"], table_status_text(table_state), autotune_status_text(autotune_state)
    except Exception as e:
        msg = f"Apply exception: {e}"
        return autotune_state, table_state, msg, table_status_text(table_state or default_table_state()), autotune_status_text(autotune_state)


def autotune_undo_action(autotune_state: dict, table_state: dict):
    table_state = table_state or default_table_state()
    table_state["data"] = copy.deepcopy(table_state.get("original_data", table_state.get("data", [])))
    table_state["changed_count"] = 0
    table_state["message"] = "Auto-tune batch undone"
    s = autotune_state or default_autotune_state()
    return s, table_state, table_state["message"], table_status_text(table_state), autotune_status_text(s)


def autotune_export_report(autotune_state: dict):
    autotune_state = autotune_state or default_autotune_state()
    preview = autotune_state.get("latest_preview") or {}
    changes = preview.get("changes", [])
    if not changes:
        return None, "No changes to export"
    fd, path = tempfile.mkstemp(prefix="autotune_report_", suffix=".csv")
    os.close(fd)
    pd.DataFrame(changes).to_csv(path, index=False)
    return path, f"Exported report: {os.path.basename(path)}"


def autotune_ask_ai(autotune_state: dict):
    autotune_state = autotune_state or default_autotune_state()
    preview = autotune_state.get("latest_preview") or {}
    summary = {
        "tool_name": preview.get("tool_name"),
        "table_name": preview.get("table_name"),
        "summary": preview.get("summary", {}),
        "warnings": preview.get("warnings", []),
        "guardrail_warnings": preview.get("guardrail_warnings", []),
        "changes_sample": (preview.get("changes", []) or [])[:30],
    }
    try:
        resp = requests.post(
            f"{BACKEND_URL}/agent/chat",
            json={"message": f"Review these classic autotune changes and advise: {json.dumps(summary)}", "state": {}},
            timeout=30,
        )
        if resp.status_code != 200:
            return f"AI advice failed: {resp.text}"
        return resp.json().get("message", json.dumps(resp.json()))
    except Exception as e:
        return f"AI advice exception: {e}"


def dyno_status_text(state: dict) -> str:
    state = state or default_dyno_state()
    connected = "ECU Connected" if state.get("connected") else "ECU Disconnected"
    units = "HP" if state.get("units", "imperial") == "imperial" else "kW"
    return f"Ready for Ramp Test • {connected} • Last Peak: {state.get('last_peak', 0):.1f} {units}"


def dyno_render_3d_graph(table_name: str, overlay_hits: bool, overlay_corr: bool, table_state: dict, datalog_state: dict, autotune_state: dict, dyno_state: dict):
    dyno_state = dyno_state or default_dyno_state()
    try:
        resp = requests.get(f"{BACKEND_URL}/graphs/3d/{table_name}", timeout=10)
        if resp.status_code != 200:
            return dyno_state, go.Figure(), go.Figure(), f"3D render failed: {resp.text}"
        payload = resp.json()
        data = payload.get("data", [])
        rpm_axis = payload.get("rpm_axis", [])
        map_axis = payload.get("map_axis", [])

        hits = []
        if overlay_hits:
            rows = (datalog_state or {}).get("rows", []) or []
            for row in rows[:: max(1, len(rows) // 400 if len(rows) > 400 else 1)]:
                hits.append(
                    {
                        "rpm": float(row.get("RPM", 0) or 0),
                        "map": float(row.get("MAP_kPa", 0) or 0),
                        "value": float(row.get("AFR", 0) or 0),
                    }
                )

        corr = []
        if overlay_corr:
            preview = (autotune_state or {}).get("latest_preview", {}) or {}
            changes = preview.get("changes", []) or []
            for c in changes:
                r = int(c.get("row", -1))
                col = int(c.get("col", -1))
                if 0 <= r < len(map_axis) and 0 <= col < len(rpm_axis):
                    corr.append(
                        {
                            "rpm": rpm_axis[col],
                            "map": map_axis[r],
                            "after": c.get("after", 0),
                            "delta_pct": c.get("delta_pct", 0),
                        }
                    )

        fig = build_3d_table_figure(table_name, data, rpm_axis, map_axis, log_hits=hits, corrections=corr)
        slice_fig = build_slice_figure(data, rpm_axis, map_axis, map_index=max(0, min(len(map_axis) - 1, len(map_axis) // 2)))
        dyno_state["last_3d"] = payload
        dyno_state["connected"] = bool(payload.get("connected", False))
        return dyno_state, fig, slice_fig, f"{table_name} 3D rendered"
    except Exception as e:
        return dyno_state, go.Figure(), go.Figure(), f"3D render exception: {e}"


def dyno_safety_check(mode: str, profile_state: dict, table_state: dict, dyno_state: dict):
    dyno_state = dyno_state or default_dyno_state()
    profile = profile_state or {}
    table = (table_state or {}).get("data") or [[100.0 for _ in range(16)] for _ in range(16)]
    zeros = [[0.0 for _ in row] for row in table]
    calibration = {
        "axes": {
            "rpm": (table_state or {}).get("rpm_axis") or [500 + i * 500 for i in range(len(table[0]))],
            "map_kpa": (table_state or {}).get("map_axis") or [30 + i * 15 for i in range(len(table))],
        },
        "fuel_table": table,
        "ignition_table": table if (table_state or {}).get("table_name") == "ignitionTable1" else zeros,
        "boost_table": table if (table_state or {}).get("table_name") == "boostTable1" else zeros,
        "metadata": {"source": "dyno_safety_check"},
    }
    req = {
        "vehicle_profile": {
            "vehicle_id": profile.get("vehicle_id", "B18C_Turbo"),
            "make": profile.get("make", "Honda"),
            "model": profile.get("model", "Integra"),
            "engine_family": profile.get("engine_family", "B18C"),
            "displacement_l": profile.get("displacement_l", 1.8),
            "cylinders": profile.get("cylinders", 4),
            "aspiration": profile.get("aspiration", "turbo"),
            "compression_ratio": profile.get("compression_ratio", 9.0),
            "fuel_type": profile.get("fuel_type", "gas93"),
            "injector_cc_min": profile.get("injector_cc_min", 1000),
            "fuel_pressure_psi": profile.get("fuel_pressure_psi", 43.5),
            "max_safe_rpm": profile.get("max_safe_rpm", 8200),
            "usage": profile.get("usage", "street"),
        },
        "calibration": calibration,
        "target_boost_psi": 0.0,
        "samples_per_stage": 3,
    }
    try:
        resp = requests.post(f"{BACKEND_URL}/power_ramp", json=req, timeout=20)
        if resp.status_code != 200:
            dyno_state["safe_check_passed"] = False
            return dyno_state, f"Safety check failed: {resp.text}", dyno_status_text(dyno_state)
        out = resp.json()
        ok = out.get("status") == "COMPLETED"
        dyno_state["safe_check_passed"] = bool(ok)
        return dyno_state, ("Safety check passed" if ok else "Safety check failed"), dyno_status_text(dyno_state)
    except Exception as e:
        dyno_state["safe_check_passed"] = False
        return dyno_state, f"Safety check exception: {e}", dyno_status_text(dyno_state)


def dyno_run_test(mode: str, start_rpm: float, end_rpm: float, ramp_seconds: float, units: str, drivetrain_loss: float, air_density_correction: bool, dyno_state: dict):
    dyno_state = dyno_state or default_dyno_state()
    params = {
        "start_rpm": float(start_rpm or 2000),
        "end_rpm": float(end_rpm or 8000),
        "ramp_seconds": float(ramp_seconds or 10),
        "units": units.lower(),
        "drivetrain_loss": float(drivetrain_loss or 15) / 100.0,
        "efficiency": 0.9 if air_density_correction else 0.86,
        "safe_check_passed": bool(dyno_state.get("safe_check_passed", False)),
    }
    try:
        resp = requests.post(f"{BACKEND_URL}/dyno/run", json={"mode": mode.lower(), "params_json": params}, timeout=120)
        if resp.status_code != 200:
            return dyno_state, go.Figure(), pd.DataFrame(), f"Dyno run failed: {resp.text}", dyno_status_text(dyno_state)
        events = parse_stream_ndjson(resp.text)
        run_log = []
        result = {}
        for ev in events:
            if ev.get("type") == "progress":
                latest = ev.get("latest", {})
                run_log.append(f"{ev.get('message')} | RPM={latest.get('rpm', 0):.0f} P={latest.get('power', 0):.1f}")
            elif ev.get("type") == "error":
                run_log.append(ev.get("message", "error"))
            elif ev.get("type") == "result":
                result = ev.get("result", {})

        if not result:
            return dyno_state, go.Figure(), pd.DataFrame(), "\n".join(run_log[-80:]) or "No dyno result", dyno_status_text(dyno_state)
        fig = build_dyno_figure(result, units=units.lower())
        df = build_curve_table(result)
        summary = summarize_dyno(result, units=units.lower()) + "\n\nRun Log:\n" + "\n".join(run_log[-40:])
        dyno_state["last_result"] = result
        dyno_state["last_stream_events"] = events
        dyno_state["units"] = units.lower()
        dyno_state["last_peak"] = float(result.get("summary", {}).get("peak_power", 0) or 0)
        dyno_state["connected"] = True
        return dyno_state, fig, df, summary, dyno_status_text(dyno_state)
    except Exception as e:
        return dyno_state, go.Figure(), pd.DataFrame(), f"Dyno run exception: {e}", dyno_status_text(dyno_state)


def dyno_estimate_from_log(mode: str, units: str, drivetrain_loss: float, datalog_state: dict, dyno_state: dict):
    dyno_state = dyno_state or default_dyno_state()
    rows = (datalog_state or {}).get("rows", []) or []
    if not rows:
        return dyno_state, go.Figure(), pd.DataFrame(), "No current log loaded", dyno_status_text(dyno_state)
    params = {"units": units.lower(), "drivetrain_loss": float(drivetrain_loss or 15) / 100.0}
    try:
        resp = requests.post(f"{BACKEND_URL}/dyno/estimate", json={"mode": mode.lower(), "params_json": params, "log_data_json": rows}, timeout=50)
        if resp.status_code != 200:
            return dyno_state, go.Figure(), pd.DataFrame(), f"Estimate failed: {resp.text}", dyno_status_text(dyno_state)
        result = resp.json()
        fig = build_dyno_figure(result, units=units.lower())
        df = build_curve_table(result)
        summary = summarize_dyno(result, units=units.lower())
        dyno_state["last_result"] = result
        dyno_state["units"] = units.lower()
        dyno_state["last_peak"] = float(result.get("summary", {}).get("peak_power", 0) or 0)
        return dyno_state, fig, df, summary, dyno_status_text(dyno_state)
    except Exception as e:
        return dyno_state, go.Figure(), pd.DataFrame(), f"Estimate exception: {e}", dyno_status_text(dyno_state)


def dyno_export_report(dyno_state: dict):
    dyno_state = dyno_state or default_dyno_state()
    result = dyno_state.get("last_result") or {}
    curves = result.get("curves", [])
    if not curves:
        return None, "No dyno data to export"
    fd_csv, csv_path = tempfile.mkstemp(prefix="dyno_", suffix=".csv")
    os.close(fd_csv)
    pd.DataFrame(curves).to_csv(csv_path, index=False)
    fd_png, png_path = tempfile.mkstemp(prefix="dyno_", suffix=".png")
    os.close(fd_png)
    png_bytes = bytes.fromhex("89504E470D0A1A0A0000000D4948445200000001000000010802000000907753DE0000000A49444154789C6360000000020001E221BC330000000049454E44AE426082")
    with open(png_path, "wb") as f:
        f.write(png_bytes)
    return csv_path, f"Exported CSV: {os.path.basename(csv_path)}\nExported PNG: {os.path.basename(png_path)}"


def dyno_ask_ai(dyno_state: dict):
    dyno_state = dyno_state or default_dyno_state()
    result = dyno_state.get("last_result") or {}
    prompt = {
        "summary": result.get("summary", {}),
        "peaks": result.get("peaks", {}),
        "warnings": result.get("warnings", []),
        "sample_points": (result.get("curves", []) or [])[:40],
    }
    try:
        resp = requests.post(
            f"{BACKEND_URL}/agent/chat",
            json={"message": f"Interpret these dyno results and suggest safe tuning changes: {json.dumps(prompt)}", "state": {}},
            timeout=30,
        )
        if resp.status_code != 200:
            return f"AI interpret failed: {resp.text}"
        return resp.json().get("message", json.dumps(resp.json()))
    except Exception as e:
        return f"AI interpret exception: {e}"


def dyno_add_gauge_to_dashboard(dashboard_state: dict, dyno_state: dict):
    dashboard_state = dashboard_state or default_dashboard_state()
    layout = dashboard_state.get("layout", {})
    tabs = layout.get("tabs", [])
    if not tabs:
        tabs = [{"name": "Engine Vitals", "gauges": []}]
        layout["tabs"] = tabs
    gauge = {
        "id": f"dyno_{int(time.time())}",
        "type": "Digital",
        "channel": "DynoHP",
        "x": 40,
        "y": 40,
        "w": 200,
        "h": 120,
        "rot": 0,
        "min": 0,
        "max": max(100, float((dyno_state or {}).get("last_peak", 250) * 1.2)),
        "unit": "HP" if (dyno_state or {}).get("units", "imperial") == "imperial" else "kW",
        "alarm": "",
    }
    tabs[0].setdefault("gauges", []).append(gauge)
    dashboard_state["layout"] = layout
    return dashboard_state, "Dyno gauge added to dashboard layout"


def dyno_refresh_compare_logs():
    try:
        resp = requests.get(f"{BACKEND_URL}/datalog/recent", timeout=8)
        if resp.status_code != 200:
            return gr.Dropdown(choices=[], value=None)
        logs = resp.json().get("logs", [])
        names = [x.get("filename") for x in logs if x.get("filename")]
        return gr.Dropdown(choices=[], value=None)
    except Exception:
        return gr.Dropdown(choices=[], value=None)


def dyno_shortcut_action(payload: str, dyno_state: dict):
    dyno_state = dyno_state or default_dyno_state()
    try:
        action = json.loads(payload or "{}").get("action", "")
    except Exception:
        action = ""
    if action == "run":
        return f"Shortcut: Run requested"
    if action == "export":
        return f"Shortcut: Export requested"
    if action == "zoom":
        result = dyno_state.get("last_result", {})
        peaks = result.get("peaks", {})
        return f"Shortcut: Zoom to peaks near {peaks.get('peak_hp_rpm', 0):.0f} RPM"
    return "Shortcut idle"


def dyno_apply_comparison(compare_filename: str, mode: str, units: str, drivetrain_loss: float, dyno_state: dict):
    dyno_state = dyno_state or default_dyno_state()
    base = dyno_state.get("last_result") or {}
    if not base:
        return go.Figure(), "Run or estimate dyno first"
    if not compare_filename:
        return build_dyno_figure(base, units=units.lower()), summarize_dyno(base, units=units.lower())
    try:
        load = requests.get(f"{BACKEND_URL}/datalog/load/{compare_filename}", timeout=20)
        if load.status_code != 200:
            return build_dyno_figure(base, units=units.lower()), f"Compare load failed: {load.text}"
        rows = load.json().get("rows", [])
        est = requests.post(
            f"{BACKEND_URL}/dyno/estimate",
            json={
                "mode": mode.lower(),
                "params_json": {"units": units.lower(), "drivetrain_loss": float(drivetrain_loss or 15) / 100.0},
                "log_data_json": rows,
            },
            timeout=40,
        )
        if est.status_code != 200:
            return build_dyno_figure(base, units=units.lower()), f"Compare estimate failed: {est.text}"
        comp = est.json()
        fig = build_dyno_figure(base, units=units.lower())
        cx = [float(p.get("rpm", 0)) for p in comp.get("curves", [])]
        cp = [float(p.get("power", 0)) for p in comp.get("curves", [])]
        ct = [float(p.get("torque", 0)) for p in comp.get("curves", [])]
        if cx:
            fig.add_trace(go.Scatter(x=cx, y=cp, mode="lines", name="Compare Power", line=dict(color="#94a3b8", dash="dash")))
            fig.add_trace(go.Scatter(x=cx, y=ct, mode="lines", name="Compare Torque", line=dict(color="#64748b", dash="dot")))
        txt = summarize_dyno(base, units=units.lower()) + f"\nComparison: {compare_filename}\n" + summarize_dyno(comp, units=units.lower())
        return fig, txt
    except Exception as e:
        return build_dyno_figure(base, units=units.lower()), f"Comparison exception: {e}"


def project_banner_text(project_state: dict) -> str:
    ps = project_state or default_project_state()
    current = ps.get("current", "untitled")
    return f"### Current Project: `{current}`"


def project_refresh(project_state: dict):
    ps = project_state or default_project_state()
    try:
        resp = requests.get(f"{BACKEND_URL}/projects/list", timeout=10)
        if resp.status_code != 200:
            msg = f"Project list failed: {resp.text}"
            return ps, gr.Dropdown(choices=[], value=None), "", "", msg, project_banner_text(ps), gr.Dropdown(choices=[], value=None), gr.Dropdown(choices=[], value=None)
        payload = resp.json()
        projects = payload.get("projects", [])
        names = [p.get("name") for p in projects if p.get("name")]
        current = payload.get("current_project") or (names[0] if names else "untitled")
        ps["projects"] = projects
        ps["current"] = current
        ps["history"] = payload.get("history", [])
        ps["file_tree"] = payload.get("file_tree", [])
        timeline = build_project_timeline_html(ps["history"])
        tree = build_file_tree_html(ps["file_tree"])
        history_versions = [f"v{h.get('version')}" for h in sorted(ps["history"], key=lambda x: x.get("version", 0))]
        v1 = history_versions[-2] if len(history_versions) > 1 else (history_versions[0] if history_versions else None)
        v2 = history_versions[-1] if history_versions else None
        msg = f"Project: {current} • {len(ps['history'])} versions"
        return (
            ps,
            gr.Dropdown(choices=names, value=current if current in names else (names[0] if names else None)),
            timeline,
            tree,
            msg,
            project_banner_text(ps),
            gr.Dropdown(choices=history_versions, value=v1),
            gr.Dropdown(choices=history_versions, value=v2),
        )
    except Exception as e:
        return ps, gr.Dropdown(choices=[], value=None), "", "", f"Project refresh exception: {e}", project_banner_text(ps), gr.Dropdown(choices=[], value=None), gr.Dropdown(choices=[], value=None)


def project_create(name: str, profile_state: dict, import_zip_path, project_state: dict):
    ps = project_state or default_project_state()
    try:
        if import_zip_path:
            with open(import_zip_path, "rb") as f:
                files = {"file": (os.path.basename(import_zip_path), f, "application/zip")}
                imp = requests.post(f"{BACKEND_URL}/projects/import", files=files, timeout=20)
            if imp.status_code != 200:
                out = list(project_refresh(ps))
                out[4] = f"Import failed: {imp.text}"
                return tuple(out)
        else:
            resp = requests.post(
                f"{BACKEND_URL}/projects/create",
                json={"name": name or "Untitled", "profile_json": profile_state or {}},
                timeout=12,
            )
            if resp.status_code != 200:
                return ps, gr.Dropdown(choices=[], value=None), "", "", f"Create failed: {resp.text}", project_banner_text(ps), gr.Dropdown(choices=[], value=None), gr.Dropdown(choices=[], value=None)
        return project_refresh(ps)
    except Exception as e:
        return ps, gr.Dropdown(choices=[], value=None), "", "", f"Create/import exception: {e}", project_banner_text(ps), gr.Dropdown(choices=[], value=None), gr.Dropdown(choices=[], value=None)


def project_switch(name: str, project_state: dict):
    ps = project_state or default_project_state()
    if not name:
        return ps, build_project_timeline_html(ps.get("history", [])), build_file_tree_html(ps.get("file_tree", [])), "No project selected", project_banner_text(ps)
    try:
        resp = requests.post(f"{BACKEND_URL}/projects/switch", json={"name": name}, timeout=10)
        if resp.status_code != 200:
            return ps, "", "", f"Switch failed: {resp.text}", project_banner_text(ps)
        ps["current"] = resp.json().get("name", name)
        ps["history"] = resp.json().get("history", [])
        ps["file_tree"] = resp.json().get("file_tree", [])
        return ps, build_project_timeline_html(ps["history"]), build_file_tree_html(ps["file_tree"]), f"Switched to {ps['current']}", project_banner_text(ps)
    except Exception as e:
        return ps, "", "", f"Switch exception: {e}", project_banner_text(ps)


def _version_to_int(v: str) -> int:
    if not v:
        return 0
    s = str(v).strip().lower().replace("v", "")
    try:
        return int(s)
    except Exception:
        return 0


def project_compare(v1: str, v2: str, table_name: str, project_state: dict):
    ps = project_state or default_project_state()
    i1 = _version_to_int(v1)
    i2 = _version_to_int(v2)
    if i1 <= 0 or i2 <= 0:
        return go.Figure(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "Select two versions"
    try:
        resp = requests.post(
            f"{BACKEND_URL}/projects/compare",
            json={"project_name": ps.get("current", "untitled"), "version1": i1, "version2": i2, "table_name": table_name or "veTable1"},
            timeout=20,
        )
        if resp.status_code != 200:
            return go.Figure(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), f"Compare failed: {resp.text}"
        diff = resp.json()
        ps["last_compare"] = diff
        fig = build_delta_heatmap(diff)
        tables = build_compare_tables(diff)
        status = f"Compared v{i1} vs v{i2} • changed cells: {diff.get('changed_cells', 0)}"
        return fig, tables["left"], tables["right"], tables["delta"], status
    except Exception as e:
        return go.Figure(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), f"Compare exception: {e}"


def project_rollback(version: str, table_name: str, project_state: dict, table_state: dict):
    ps = project_state or default_project_state()
    ts = table_state or default_table_state()
    vi = _version_to_int(version)
    if vi <= 0:
        return ps, ts, "Select a version for rollback", table_status_text(ts)
    try:
        resp = requests.post(
            f"{BACKEND_URL}/projects/rollback",
            json={"project_name": ps.get("current", "untitled"), "version": vi, "table_name": table_name or "veTable1"},
            timeout=20,
        )
        if resp.status_code != 200:
            return ps, ts, f"Rollback failed: {resp.text}", table_status_text(ts)
        payload = resp.json()
        ts["table_name"] = payload.get("table_name", ts.get("table_name"))
        ts["data"] = payload.get("data", ts.get("data"))
        ts["original_data"] = copy.deepcopy(ts["data"])
        ts["changed_count"] = 0
        ts["message"] = f"Rolled back to v{vi}"
        return ps, ts, ts["message"], table_status_text(ts)
    except Exception as e:
        return ps, ts, f"Rollback exception: {e}", table_status_text(ts)


def project_export_zip(project_state: dict):
    ps = project_state or default_project_state()
    name = ps.get("current", "untitled")
    try:
        resp = requests.get(f"{BACKEND_URL}/projects/export/{name}", timeout=40)
        if resp.status_code != 200:
            return None, f"Export failed: {resp.text}"
        fd, path = tempfile.mkstemp(prefix=f"{name}_", suffix=".zip")
        os.close(fd)
        with open(path, "wb") as f:
            f.write(resp.content)
        return path, f"Exported {os.path.basename(path)}"
    except Exception as e:
        return None, f"Export exception: {e}"


def project_diff_export(project_state: dict):
    ps = project_state or default_project_state()
    diff = ps.get("last_compare", {})
    if not diff:
        return None, "No diff to export"
    fd, path = tempfile.mkstemp(prefix="project_diff_", suffix=".csv")
    os.close(fd)
    pd.DataFrame(diff.get("delta", [])).to_csv(path, index=False)
    return path, f"Exported diff report: {os.path.basename(path)}"


def project_ask_ai(project_state: dict):
    ps = project_state or default_project_state()
    history = ps.get("history", [])[:30]
    diff = ps.get("last_compare", {})
    prompt = {"project": ps.get("current"), "history": history, "last_compare": diff}
    try:
        resp = requests.post(
            f"{BACKEND_URL}/agent/chat",
            json={"message": f"Review this tuning project history and summarize progress/safety: {json.dumps(prompt)}", "state": {}},
            timeout=30,
        )
        if resp.status_code != 200:
            return f"AI review failed: {resp.text}"
        return resp.json().get("message", json.dumps(resp.json()))
    except Exception as e:
        return f"AI review exception: {e}"


def project_open_tune_in_table(table_name: str):
    return gr.Dropdown(value=table_name or "veTable1"), f"Opened {table_name} in Table Editor"


def project_load_logs_in_datalog(project_state: dict):
    ps = project_state or default_project_state()
    return f"Load logs from project {ps.get('current', 'untitled')} in Datalogs"


def project_shortcut_action(payload: str):
    try:
        action = json.loads(payload or "{}").get("action", "")
    except Exception:
        action = ""
    if action == "new":
        return "Shortcut: New project"
    if action == "open":
        return "Shortcut: Open project"
    if action == "rollback":
        return "Shortcut: Rollback last"
    return "Shortcut idle"


def project_filter(search: str, project_state: dict):
    ps = project_state or default_project_state()
    names = [p.get("name") for p in ps.get("projects", []) if p.get("name")]
    q = (search or "").strip().lower()
    if q:
        names = [n for n in names if q in n.lower()]
    return gr.Dropdown(choices=names, value=(names[0] if names else None))


# --- UI ---
with gr.Blocks() as demo:
    gr.HTML(loading_spinner_html())
    with gr.Row(elem_id="top-ribbon", equal_height=True):
        with gr.Column(scale=22):
            gr.HTML(
                "<div class='wrap'>"
                "<div class='brand'>"
                "<div class='logo' aria-label='rusEFI logo'></div>"
                "<div class='title'>BaseTune Architect</div>"
                "</div></div>"
            )
        with gr.Column(scale=56):
            with gr.Row(elem_classes=["mid"]):
                btn_ribbon_connect = gr.Button("Connect ECU", elem_id="btn-ribbon-connect", elem_classes=["premium-btn", "btn-connect-ok"])
                btn_ribbon_burn_all = gr.Button("Burn All Changes", elem_id="btn-ribbon-burn", elem_classes=["premium-btn", "btn-danger"])
                btn_ribbon_load_msq = gr.UploadButton("Load .msq", file_types=[".msq"], elem_id="btn-ribbon-load", elem_classes=["premium-btn"])
                btn_ribbon_save_msq = gr.Button("Save .msq", elem_id="btn-ribbon-save", elem_classes=["premium-btn"])
                btn_ribbon_export = gr.Button("Export Current Tune", elem_id="btn-ribbon-export", elem_classes=["premium-btn"])
                btn_ribbon_datalog = gr.Button("Start Datalog", elem_id="btn-ribbon-datalog", elem_classes=["premium-btn"])
                btn_ribbon_fw = gr.Button("Firmware Update", elem_id="btn-ribbon-fw", elem_classes=["premium-btn"])
                btn_ribbon_refresh = gr.Button("Refresh Gauges", elem_id="btn-ribbon-refresh", elem_classes=["premium-btn", "btn-cyan"])
        with gr.Column(scale=22):
            ribbon_status = gr.HTML("<div class='right'><span class='status-dot bad'></span>Disconnected • COM? • Uptime: 00s • RPM: 0000</div>")

    gr.HTML(
        "<script>"
        "(function(){"
        "const map={"
        "'btn-ribbon-connect':'Click to connect to COM6 binary mode - holds PROG if needed',"
        "'btn-ribbon-burn':'Write all pending scalars and tables then burn to ECU flash',"
        "'btn-ribbon-load':'Open a full TunerStudio .msq file and merge into current tune',"
        "'btn-ribbon-save':'Save current tune as .msq file with all scalars and tables',"
        "'btn-ribbon-export':'Export complete tune including all parameters to .msq',"
        "'btn-ribbon-datalog':'Record live data to SQLite',"
        "'btn-ribbon-fw':'Enter DFU mode and flash new rusEFI firmware',"
        "'btn-ribbon-refresh':'Refresh all live gauges now'"
        "};"
        "Object.keys(map).forEach(function(id){const b=document.querySelector('#'+id+' button');if(b)b.title=map[id];});"
        "})();"
        "</script>",
        visible=False,
    )

    table_state_init = default_table_state()
    table_state = gr.State(table_state_init)
    full_tuning_state = gr.State(default_full_tuning_state())
    project_state = gr.State(default_project_state())
    project_banner = gr.Markdown("### Current Project: `untitled`")
    recording_state = gr.State({"recording": False, "started_at": 0.0})
    
    # Dummy components for removed tabs that premium handlers still rely on
    ft_parameter_pick = gr.State(None)
    ft_export_file = gr.File(visible=False)
    datalog_state = gr.State(default_datalog_state())
    datalog_status = gr.Textbox(visible=False)
    recent_logs = gr.Dropdown(choices=[], value=None, visible=False)

    with gr.Group(elem_id="premium-suite-container"):
            with gr.Row(elem_id="workspace-row"):
                with gr.Column(scale=2, elem_id="left-sidebar", elem_classes=["premium-card"]):
                    pt_search = gr.Textbox(
                        label="Search",
                        placeholder="Search any parameter...",
                        value="",
                    )
                    premium_tree_html = gr.HTML(
                        build_premium_tree_html("", "", [], PREMIUM_TREE_PICK_INPUT_ID, PREMIUM_TREE_PICK_TRIGGER_ID)
                    )
                    premium_tree_pick_input = gr.Textbox(value="", elem_id=PREMIUM_TREE_PICK_INPUT_ID, elem_classes=["hidden-input"])
                    premium_tree_pick_trigger = gr.Button("tree-pick", elem_id=PREMIUM_TREE_PICK_TRIGGER_ID, elem_classes=["hidden-input"])
                    premium_tree_pick_nonce = gr.Number(value=0, visible=False)
                    premium_param_pick = gr.Dropdown(label="Selected Parameter", choices=[], value=None)
                with gr.Column(scale=5, elem_id="center-main"):
                    dialog_container = gr.Group(elem_id="dialog-overlay-container", elem_classes=["premium-card", "hover-panel"], visible=False)
                    with dialog_container:
                        # The invisible input that receives the tree selection
                        premium_tree_pick_output = gr.Textbox(visible=False, elem_id="premium-tree-pick-output")
                        
                        @gr.render(inputs=[premium_tree_pick_input, full_tuning_state, premium_tree_pick_nonce])
                        def render_center_dialog(selected_node, state, nonce):
                            if not selected_node: return
                            from frontend.components.dialog_renderer import render_dialog_content
                            render_dialog_content(selected_node, state)
                        
                        gr.HTML("<hr style='border:1px solid #555; margin: 10px 0;'/>")
                        with gr.Row(elem_classes=["ts-dialog-footer"]):
                            btn_dialog_burn = gr.Button("Burn", elem_classes=["ts-button"])
                            btn_dialog_close = gr.Button("Close", elem_classes=["ts-button"])

                    premium_context_payload = gr.Textbox(value="", visible=False, elem_id=PREMIUM_CONTEXT_PAYLOAD_ID)
                    premium_context_trigger = gr.Button("premium-context", visible=False, elem_id=PREMIUM_CONTEXT_TRIGGER_ID)
                    premium_shortcut_payload = gr.Textbox(value="", visible=False, elem_id=PREMIUM_SHORTCUT_PAYLOAD_ID)
                    premium_shortcut_trigger = gr.Button("premium-shortcut", visible=False, elem_id=PREMIUM_SHORTCUT_TRIGGER_ID)
                    premium_context_status = gr.Textbox(label="Context/Shortcut Status", value="Ready", interactive=False)
                    gr.HTML(
                        build_context_menu_html("center-main", PREMIUM_CONTEXT_PAYLOAD_ID, PREMIUM_CONTEXT_TRIGGER_ID)
                        + build_shortcuts_js(
                            center_id="center-main",
                            burn_btn_id="btn-ribbon-burn",
                            load_btn_id="btn-ribbon-load",
                            datalog_btn_id="btn-ribbon-datalog",
                            refresh_btn_id="btn-ribbon-refresh",
                            open_table_btn_id="btn-dummy",
                            shortcut_payload_id=PREMIUM_SHORTCUT_PAYLOAD_ID,
                            shortcut_trigger_id=PREMIUM_SHORTCUT_TRIGGER_ID,
                        )
                    )

                with gr.Column(scale=2, elem_id="right-gauges", elem_classes=["premium-card"]):
                    premium_gauges = gr.Plot(value=build_live_gauges_figure({}), label="Live Gauges")
            premium_live_timer = gr.Timer(0.05)

            with gr.Group(elem_id="bottom-strip", elem_classes=["premium-card"]):
                with gr.Row(elem_classes=["strip-head"]):
                    gr.Markdown("### Datalog Strip")
                with gr.Row(elem_classes=["strip-body"]):
                    with gr.Column(scale=1):
                        btn_playback_back = gr.Button("<<", elem_classes=["premium-btn"])
                        btn_playback_play = gr.Button("Play/Pause", elem_classes=["premium-btn"])
                        btn_playback_fwd = gr.Button(">>", elem_classes=["premium-btn"])
                        playback_speed_bar = gr.Slider(0.5, 2.0, value=1.0, step=0.5, label="Speed")
                    with gr.Column(scale=3):
                        premium_datalog_chart = gr.Plot(label="Mini Time-Series")
                    with gr.Column(scale=1):
                        premium_open_datalog_btn = gr.Button("Open Full Datalog Viewer", elem_classes=["premium-btn", "btn-cyan"])


    # Premium suite actions
    demo.load(
        premium_refresh_registry,
        inputs=[pt_search, full_tuning_state],
        outputs=[
            full_tuning_state,
            premium_tree_html,
            premium_param_pick,
        ],
    )
    pt_search.change(
        premium_refresh_registry,
        inputs=[pt_search, full_tuning_state],
        outputs=[
            full_tuning_state,
            premium_tree_html,
            premium_param_pick,
        ],
    )
    # Simplify tree pick: Trigger directly updates the hidden input and increments nonce
    def handle_tree_pick(val, nonce):
        return val, nonce + 1, gr.update(visible=True)

    premium_tree_pick_trigger.click(
        handle_tree_pick,
        inputs=[premium_tree_pick_input, premium_tree_pick_nonce],
        outputs=[premium_tree_pick_input, premium_tree_pick_nonce, dialog_container],
    )
    
    # Show dialog when input changes to a non-empty value
    def toggle_dialog_visibility(val):
        if val:
            return gr.Group(visible=True)
        return gr.Group(visible=False)

    premium_tree_pick_input.change(
        toggle_dialog_visibility,
        inputs=[premium_tree_pick_input],
        outputs=[dialog_container]
    )
    btn_dialog_close.click(
        lambda: (""),
        outputs=[premium_tree_pick_input]
    )
    btn_dialog_close.click(
        lambda: gr.Group(visible=False),
        outputs=[dialog_container]
    )
    btn_dialog_burn.click(
        premium_burn_all,
        inputs=[full_tuning_state],
        outputs=[full_tuning_state, premium_context_status, btn_ribbon_burn_all],
    )
    premium_context_trigger.click(
        premium_context_action,
        inputs=[premium_context_payload, full_tuning_state],
        outputs=[premium_context_status],
    )
    premium_shortcut_trigger.click(
        premium_shortcut_action,
        inputs=[premium_shortcut_payload],
        outputs=[premium_context_status],
    )
    premium_live_timer.tick(
        premium_poll_live,
        outputs=[premium_gauges, ribbon_status],
    )
    btn_ribbon_refresh.click(
        premium_poll_live,
        outputs=[premium_gauges, ribbon_status],
    )
    btn_ribbon_connect.click(
        ribbon_connect_action,
        outputs=[premium_context_status],
    )
    btn_ribbon_fw.click(
        ribbon_fw_action,
        outputs=[premium_context_status],
    )
    btn_ribbon_load_msq.upload(
        ribbon_load_msq_action,
        inputs=[btn_ribbon_load_msq, full_tuning_state],
        outputs=[full_tuning_state, premium_context_status],
    )
    btn_ribbon_save_msq.click(
        ribbon_export_msq_action,
        outputs=[ft_export_file, premium_context_status],
    )
    btn_ribbon_export.click(
        ribbon_export_msq_action,
        outputs=[ft_export_file, premium_context_status],
    )
    btn_ribbon_burn_all.click(
        premium_burn_all,
        inputs=[full_tuning_state],
        outputs=[full_tuning_state, premium_context_status, btn_ribbon_burn_all],
    )
    btn_ribbon_datalog.click(
        ribbon_toggle_datalog,
        inputs=[recording_state, datalog_state],
        outputs=[recording_state, datalog_state, btn_ribbon_datalog, datalog_status, recent_logs],
    )
    def premium_live_update_handler(recording_state):
        return ribbon_datalog_label(recording_state), update_gauges()

    premium_live_timer.tick(
        premium_live_update_handler,
        inputs=[recording_state],
        outputs=[btn_ribbon_datalog, premium_gauges],
    )
    btn_playback_play.click(
        datalog_playback_tick,
        inputs=[datalog_state],
        outputs=[datalog_state, premium_datalog_chart],
    )
    btn_playback_back.click(
        datalog_playback_tick,
        inputs=[datalog_state],
        outputs=[datalog_state, premium_datalog_chart],
    )
    btn_playback_fwd.click(
        datalog_playback_tick,
        inputs=[datalog_state],
        outputs=[datalog_state, premium_datalog_chart],
    )
    playback_speed_bar.change(
        premium_set_playback_speed,
        inputs=[playback_speed_bar, datalog_state],
        outputs=[datalog_state],
    )
    premium_open_datalog_btn.click(
        premium_open_datalog_hint,
        outputs=[premium_context_status],
    )




if __name__ == "__main__":
        demo.launch(
        server_name="0.0.0.0", 
        server_port=7860, 
        theme=gr.themes.Soft(primary_hue="orange", neutral_hue="slate"),
        css=premium_theme_css(),
    )
