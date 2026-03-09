import copy
import json
import uuid
from typing import Any, Dict, List


DEFAULT_GAUGE_TYPES = ["Analog", "Digital", "Bar", "LED", "Histogram"]


def default_dashboard_layout() -> Dict[str, Any]:
    return {
        "name": "Untitled Dashboard",
        "background": {"color": "#0f172a", "image": ""},
        "tabs": [{"name": "Engine Vitals", "gauges": []}],
        "active_tab": 0,
        "values": {},
        "connected": False,
        "selected_gauge_id": None,
    }


def default_dashboard_state() -> Dict[str, Any]:
    return {
        "layout": default_dashboard_layout(),
        "selected_gauge": None,
        "live_preview": False,
        "status": "No dashboard loaded",
    }


def parse_dashboard_payload(payload: str) -> Dict[str, Any]:
    if not payload:
        return {}
    try:
        data = json.loads(payload)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _safe_tabs(layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    tabs = layout.get("tabs") or [{"name": "Engine Vitals", "gauges": []}]
    if not isinstance(tabs, list) or not tabs:
        tabs = [{"name": "Engine Vitals", "gauges": []}]
    return tabs[:5]


def build_dashboard_html(
    layout: Dict[str, Any],
    channels: List[str],
    payload_elem_id: str,
    trigger_button_id: str,
) -> str:
    layout = copy.deepcopy(layout or default_dashboard_layout())
    layout["tabs"] = _safe_tabs(layout)
    channels = channels or ["RPM", "AFR", "MAP_kPa", "IAT_C", "ECT_C", "KnockCount", "InjectorDuty_pct", "TPS", "batteryV"]

    initial = {
        "layout": layout,
        "channels": channels,
    }

    state_json = json.dumps(initial)
    payload_id = json.dumps(payload_elem_id)
    trigger_id = json.dumps(trigger_button_id)

    return f"""
<div id="dash-root" class="dash-root">
  <style>
    .dash-root {{ height:80vh; border:1px solid #334155; border-radius:10px; overflow:hidden; background:#0f172a; color:#e2e8f0; font-family:Consolas, monospace; }}
    .dash-shell {{ display:grid; grid-template-columns:220px 1fr; height:100%; }}
    .dash-palette {{ border-right:1px solid #334155; background:#111827; padding:8px; overflow:auto; }}
    .dash-item {{ user-select:none; border:1px solid #475569; border-radius:8px; padding:8px; margin:6px 0; cursor:grab; background:#1f2937; }}
    .dash-item:hover {{ border-color:#60a5fa; }}
    .dash-main {{ position:relative; display:flex; flex-direction:column; height:100%; }}
    .dash-tabs {{ display:flex; gap:6px; padding:8px; border-bottom:1px solid #334155; background:#0b1220; }}
    .dash-tab {{ border:1px solid #475569; padding:6px 10px; border-radius:8px; cursor:pointer; }}
    .dash-tab.active {{ border-color:#38bdf8; color:#38bdf8; }}
    .dash-canvas {{ position:relative; flex:1; overflow:auto; background-size:cover; background-position:center; min-height:300px; }}
    .gauge {{ position:absolute; min-width:120px; min-height:90px; border:1px solid #64748b; border-radius:10px; background:rgba(15,23,42,0.88); resize:both; overflow:hidden; }}
    .gauge.selected {{ outline:2px solid #38bdf8; }}
    .g-head {{ display:flex; justify-content:space-between; align-items:center; background:#1f2937; padding:4px 6px; cursor:move; font-size:11px; }}
    .g-del {{ cursor:pointer; color:#f87171; font-weight:700; }}
    .g-body {{ padding:6px; height:calc(100% - 26px); display:flex; flex-direction:column; justify-content:center; align-items:center; }}
    .g-value {{ font-size:24px; font-weight:700; }}
    .g-type {{ font-size:11px; opacity:0.8; }}
    .alarm {{ animation:flash 0.6s infinite; border-color:#ef4444 !important; }}
    @keyframes flash {{ 0%{{background:rgba(127,29,29,0.9)}} 50%{{background:rgba(239,68,68,0.9)}} 100%{{background:rgba(127,29,29,0.9)}} }}
    @media (max-width: 860px) {{
      .dash-shell {{ grid-template-columns:1fr; }}
      .dash-palette {{ max-height:140px; border-right:none; border-bottom:1px solid #334155; }}
      .gauge {{ width:46% !important; left:auto !important; position:relative; margin:8px; display:inline-block; }}
    }}
  </style>
  <div class="dash-shell">
    <div class="dash-palette" id="dash-palette"></div>
    <div class="dash-main">
      <div class="dash-tabs" id="dash-tabs"></div>
      <div class="dash-canvas" id="dash-canvas"></div>
    </div>
  </div>
</div>
<script>
(function() {{
  const payloadId = {payload_id};
  const triggerId = {trigger_id};
  const initial = {state_json};

  let layout = initial.layout;
  const channels = initial.channels;
  let activeTab = Number(layout.active_tab || 0);
  let selectedGaugeId = layout.selected_gauge_id || null;
  let drag = null;

  const root = document.getElementById('dash-root');
  const palette = document.getElementById('dash-palette');
  const tabs = document.getElementById('dash-tabs');
  const canvas = document.getElementById('dash-canvas');

  function getPayloadBox() {{
    return document.querySelector(`#${{payloadId}} textarea`) || document.querySelector(`#${{payloadId}} input`);
  }}

  function fireChange(action, extra) {{
    layout.active_tab = activeTab;
    layout.selected_gauge_id = selectedGaugeId;
    const box = getPayloadBox();
    const btn = document.querySelector(`#${{triggerId}} button`);
    if (!box || !btn) return;
    box.value = JSON.stringify({{ action, layout, selected_gauge_id: selectedGaugeId, ...(extra || {{}}) }});
    box.dispatchEvent(new Event('input', {{ bubbles:true }}));
    btn.click();
  }}

  function tabList() {{
    if (!Array.isArray(layout.tabs) || !layout.tabs.length) layout.tabs = [{{ name:'Engine Vitals', gauges:[] }}];
    return layout.tabs.slice(0, 5);
  }}

  function currentTab() {{
    const tabs = tabList();
    activeTab = Math.max(0, Math.min(activeTab, tabs.length - 1));
    return tabs[activeTab];
  }}

  function gaugeValue(g) {{
    const v = Number((layout.values || {{}})[g.channel] ?? 0);
    return Number.isFinite(v) ? v : 0;
  }}

  function gaugeAlarm(g, value) {{
    if (g.channel === 'KnockCount' && value > 0) return true;
    if (g.channel === 'InjectorDuty_pct' && value > 85) return true;
    if (g.alarm && Number.isFinite(Number(g.alarm)) && value > Number(g.alarm)) return true;
    return false;
  }}

  function renderPalette() {{
    const items = ['Analog', 'Digital', 'Bar', 'LED', 'Histogram'];
    palette.innerHTML = '<div style="font-weight:700;margin-bottom:8px">Gauge Palette</div>';
    items.forEach((name) => {{
      const el = document.createElement('div');
      el.className = 'dash-item';
      el.draggable = true;
      el.textContent = name;
      el.addEventListener('dragstart', (e) => e.dataTransfer.setData('text/gauge-type', name));
      palette.appendChild(el);
    }});
  }}

  function renderTabs() {{
    tabs.innerHTML = '';
    tabList().forEach((t, i) => {{
      const el = document.createElement('div');
      el.className = 'dash-tab' + (i === activeTab ? ' active' : '');
      el.textContent = t.name || `Tab ${{i+1}}`;
      el.onclick = () => {{ activeTab = i; render(); fireChange('switch_tab'); }};
      tabs.appendChild(el);
    }});

    const add = document.createElement('div');
    add.className = 'dash-tab';
    add.textContent = '+ Tab';
    add.onclick = () => {{
      if (layout.tabs.length >= 5) return;
      const name = prompt('Tab name', `Tab ${{layout.tabs.length + 1}}`) || `Tab ${{layout.tabs.length + 1}}`;
      layout.tabs.push({{ name, gauges: [] }});
      activeTab = layout.tabs.length - 1;
      render();
      fireChange('add_tab');
    }};
    tabs.appendChild(add);
  }}

  function gaugeHtml(g) {{
    const value = gaugeValue(g);
    const alarm = gaugeAlarm(g, value);
    const unit = g.unit || '';
    const extra = g.type === 'LED' ? (value > 0 ? 'ON' : 'OFF') : value.toFixed(2);
    return `
      <div class="gauge ${{selectedGaugeId === g.id ? 'selected' : ''}} ${{alarm ? 'alarm' : ''}}"
           data-id="${{g.id}}"
           style="left:${{g.x}}px;top:${{g.y}}px;width:${{g.w}}px;height:${{g.h}}px;transform:rotate(${{g.rot || 0}}deg)">
        <div class="g-head"><span>${{g.channel}}</span><span class="g-del">x</span></div>
        <div class="g-body">
          <div class="g-value">${{extra}} <span style="font-size:12px">${{unit}}</span></div>
          <div class="g-type">${{g.type}} • ${{layout.connected ? 'Live' : 'No Data'}}</div>
        </div>
      </div>
    `;
  }}

  function attachGaugeHandlers() {{
    const all = canvas.querySelectorAll('.gauge');
    all.forEach((node) => {{
      const id = node.getAttribute('data-id');
      const head = node.querySelector('.g-head');
      const del = node.querySelector('.g-del');

      node.addEventListener('mousedown', () => {{ selectedGaugeId = id; render(); fireChange('select_gauge'); }});

      del.addEventListener('click', (e) => {{
        e.stopPropagation();
        const tab = currentTab();
        tab.gauges = tab.gauges.filter((g) => g.id !== id);
        if (selectedGaugeId === id) selectedGaugeId = null;
        render();
        fireChange('delete_gauge');
      }});

      head.addEventListener('pointerdown', (e) => {{
        e.preventDefault();
        selectedGaugeId = id;
        const rect = node.getBoundingClientRect();
        drag = {{ id, offX: e.clientX - rect.left, offY: e.clientY - rect.top }};
      }});
    }});
  }}

  function renderCanvas() {{
    const bg = layout.background || {{ color:'#0f172a', image:'' }};
    canvas.style.backgroundColor = bg.color || '#0f172a';
    canvas.style.backgroundImage = bg.image ? `url(${{bg.image}})` : 'none';

    const tab = currentTab();
    canvas.innerHTML = (tab.gauges || []).map(gaugeHtml).join('');
    attachGaugeHandlers();
  }}

  function render() {{
    renderPalette();
    renderTabs();
    renderCanvas();
  }}

  canvas.addEventListener('dragover', (e) => e.preventDefault());
  canvas.addEventListener('drop', (e) => {{
    e.preventDefault();
    const gaugeType = e.dataTransfer.getData('text/gauge-type');
    if (!gaugeType) return;
    const rect = canvas.getBoundingClientRect();
    const g = {{
      id: 'g_' + Math.random().toString(16).slice(2),
      type: gaugeType,
      channel: channels[0] || 'RPM',
      x: Math.max(0, e.clientX - rect.left - 60),
      y: Math.max(0, e.clientY - rect.top - 40),
      w: 180,
      h: 140,
      rot: 0,
      min: 0,
      max: 100,
      unit: '',
      color: '#60a5fa',
      alarm: '',
    }};
    const tab = currentTab();
    tab.gauges = tab.gauges || [];
    tab.gauges.push(g);
    selectedGaugeId = g.id;
    render();
    fireChange('add_gauge');
  }});

  window.addEventListener('pointermove', (e) => {{
    if (!drag) return;
    const tab = currentTab();
    const gauge = (tab.gauges || []).find((g) => g.id === drag.id);
    if (!gauge) return;
    const rect = canvas.getBoundingClientRect();
    gauge.x = Math.max(0, e.clientX - rect.left - drag.offX);
    gauge.y = Math.max(0, e.clientY - rect.top - drag.offY);
    renderCanvas();
  }});

  window.addEventListener('pointerup', () => {{
    if (!drag) return;
    drag = null;
    fireChange('move_gauge');
  }});

  document.addEventListener('keydown', (e) => {{
    const tab = currentTab();
    const gauges = tab.gauges || [];
    if (e.ctrlKey && e.key.toLowerCase() === 'd' && selectedGaugeId) {{
      e.preventDefault();
      const src = gauges.find((g) => g.id === selectedGaugeId);
      if (!src) return;
      const dup = JSON.parse(JSON.stringify(src));
      dup.id = 'g_' + Math.random().toString(16).slice(2);
      dup.x += 20;
      dup.y += 20;
      gauges.push(dup);
      selectedGaugeId = dup.id;
      render();
      fireChange('duplicate_gauge');
    }}
    if (e.key === 'Delete' && selectedGaugeId) {{
      e.preventDefault();
      tab.gauges = gauges.filter((g) => g.id !== selectedGaugeId);
      selectedGaugeId = null;
      render();
      fireChange('delete_gauge');
    }}
  }});

  render();
  fireChange('init');
}})();
</script>
"""


def update_gauge_properties(layout: Dict[str, Any], gauge_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    layout = copy.deepcopy(layout or default_dashboard_layout())
    for tab in _safe_tabs(layout):
        for gauge in tab.get("gauges", []):
            if gauge.get("id") == gauge_id:
                gauge.update(updates)
                return layout
    return layout


def selected_gauge(layout: Dict[str, Any], gauge_id: str) -> Dict[str, Any]:
    if not gauge_id:
        return {}
    for tab in _safe_tabs(layout or {}):
        for gauge in tab.get("gauges", []):
            if gauge.get("id") == gauge_id:
                return copy.deepcopy(gauge)
    return {}
