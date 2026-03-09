import json
import html
from typing import Any, Dict, List, Tuple

TABLE_LIMITS: Dict[str, Tuple[float, float]] = {
    "veTable1": (0.0, 255.0),
    "ignitionTable1": (-10.0, 60.0),
    "boostTable1": (0.0, 300.0),
    "lambdaTable1": (0.6, 1.4),
}

TABLE_RISK: Dict[str, Tuple[float, float]] = {
    "veTable1": (210.0, 235.0),
    "ignitionTable1": (45.0, 55.0),
    "boostTable1": (220.0, 270.0),
    "lambdaTable1": (0.75, 1.25),
}


def _default_matrix(rows: int = 16, cols: int = 16, value: float = 0.0) -> List[List[float]]:
    return [[value for _ in range(cols)] for _ in range(rows)]


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def parse_editor_payload(payload: str) -> Dict[str, Any]:
    if not payload:
        return {}
    try:
        data = json.loads(payload)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def build_table_editor_html(
    table_name: str,
    data: List[List[float]],
    rpm_axis: List[float],
    map_axis: List[float],
    payload_elem_id: str,
    change_button_id: str,
    save_button_id: str,
    connected: bool,
    message: str = "",
    min_allowed: float = 0.0,
    max_allowed: float = 255.0,
    risk_low: float = 210.0,
    risk_high: float = 235.0,
) -> str:
    # Use limits from global if defaults provided
    if table_name in TABLE_LIMITS:
        min_allowed, max_allowed = TABLE_LIMITS[table_name]
    if table_name in TABLE_RISK:
        risk_low, risk_high = TABLE_RISK[table_name]

    state_json = json.dumps(
        {
            "tableName": table_name,
            "data": data,
            "originalData": data,
            "rpmAxis": rpm_axis,
            "mapAxis": map_axis,
            "minAllowed": min_allowed,
            "maxAllowed": max_allowed,
            "riskLow": risk_low,
            "riskHigh": risk_high,
            "connected": connected,
            "maxUndo": 50,
            "pasteLimit": 1024,
            "payloadId": payload_elem_id,
            "changeButtonId": change_button_id,
            "saveButtonId": save_button_id,
        }
    )

    overlay = ""
    if not connected:
        overlay = '<div id="editor-overlay">ECU Disconnected - Table Read Only</div>'

    html_safe_state = html.escape(state_json)
    content = f"""
<div id="table-editor-root" class="tunerstudio-theme" data-state='{html_safe_state}'>
  <style>
    .tunerstudio-theme {{
      --bg-deep: #0f172a;
      --bg-panel: #1e293b;
      --border-color: #334155;
      --text-main: #e2e8f0;
      --text-muted: #94a3b8;
      --accent-orange: #f97316;
      --cell-safe: #059669;
      --cell-risk: #b45309;
      --cell-danger: #991b1b;
      --selection-border: #38bdf8;
      background: var(--bg-deep);
      color: var(--text-main);
      padding: 12px;
      border-radius: 8px;
      font-family: 'Inter', system-ui, sans-serif;
      position: relative;
      min-height: 480px;
      display: flex;
      flex-direction: column;
    }}
    #editor-toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 12px;
      font-size: 0.9rem;
      flex-shrink: 0;
    }}
    #editor-shell {{
      overflow: auto;
      flex: 1;
      max-height: 500px;
    }}
    #editor-grid {{
      border-collapse: collapse;
      width: 100%;
      user-select: none;
    }}
    #editor-grid th {{
      background: var(--bg-panel);
      color: var(--text-muted);
      padding: 6px;
      border: 1px solid var(--border-color);
      font-weight: 500;
      font-size: 0.75rem;
    }}
    #editor-grid th.row-label {{ text-align: right; min-width: 60px; }}
    #editor-grid td {{
      border: 1px solid var(--border-color);
      padding: 4px 8px;
      text-align: center;
      cursor: cell;
      min-width: 45px;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      font-size: 0.85rem;
      transition: background 0.1s;
    }}
    #editor-grid td.safe {{ background: rgba(5, 150, 105, 0.15); color: #34d399; }}
    #editor-grid td.risk {{ background: rgba(180, 83, 9, 0.25); color: #fbbf24; }}
    #editor-grid td.danger {{ background: rgba(153, 27, 27, 0.35); color: #f87171; font-weight: 700; }}
    #editor-grid td.selected {{ 
      background: rgba(56, 189, 248, 0.3) !important; 
      outline: 2px solid var(--selection-border);
      outline-offset: -2px;
    }}
    #editor-overlay {{
      position: absolute;
      inset: 0;
      background: rgba(15, 23, 42, 0.75);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10;
      font-weight: 700;
      backdrop-filter: blur(2px);
      pointer-events: none;
    }}
    #editor-context {{
      position: fixed;
      display: none;
      z-index: 100;
      background: #1e293b;
      border: 1px solid #475569;
      border-radius: 6px;
      box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3);
      padding: 4px;
      min-width: 180px;
    }}
    #editor-context button {{
      width: 100%;
      text-align: left;
      padding: 8px 12px;
      border: 0;
      background: transparent;
      color: var(--text-main);
      cursor: pointer;
      border-radius: 4px;
      font-size: 0.85rem;
    }}
    #editor-context button:hover {{ background: #334155; color: var(--accent-orange); }}
    #editor-context .sep {{ height: 1px; background: #334155; margin: 4px; }}
    
    #editor-message {{ color: var(--accent-orange); font-weight: 600; }}
  </style>
  
  <div id="editor-toolbar">
    <div><strong>{table_name}</strong> <span style="color:var(--text-muted); margin-left:8px;">Range: {min_allowed}..{max_allowed}</span></div>
    <div id="editor-message">{message}</div>
    <div style="font-size: 0.75rem; color: var(--text-muted);">Ctrl+S: Save | Shift+Drag: Range Select</div>
  </div>
  <div id="editor-shell">
     <div style="padding: 20px; text-align: center; color: var(--text-muted);">Initializing table grid...</div>
  </div>
  {overlay}

  <div id="editor-context">
    <button data-action="average">Set to Average</button>
    <button data-action="interp_h">Interpolate Horizontal</button>
    <button data-action="interp_v">Interpolate Vertical</button>
    <button data-action="interp_2d">Interpolate 2D Area</button>
    <div class="sep"></div>
    <button data-action="incr_5">Increment 5%</button>
    <button data-action="decr_5">Decrement 5%</button>
    <div class="sep"></div>
    <button data-action="reset">Reset to Loaded</button>
  </div>
</div>
"""
    return content


def get_table_editor_js() -> str:
    """Return the JS that should be permanently present in the UI to handle table editors."""
    return """
(function() {
  console.log("Table Editor JS Loaded - v2.1");

  function initEditor(root) {
    if (root.dataset.initialized) return;
    
    // Safety check for shell
    const shell = root.querySelector("#editor-shell");
    if (!shell) return;
    
    function showUIError(msg) {
        shell.innerHTML = `<div style="padding:30px; color:#f87171; border:1px solid #991b1b; background:rgba(153,27,27,0.1); border-radius:8px; text-align:center;">
            <div style="font-weight:bold; margin-bottom:10px;">Table Editor Error</div>
            <div style="font-size:0.85rem; font-family:monospace; line-height:1.4;">${msg}</div>
        </div>`;
    }

    try {
        console.log("Initializing Table Editor root:", root);
        root.dataset.initialized = "true";
        
        const stateStr = root.dataset.state;
        if (!stateStr) throw new Error("No 'data-state' found on root element");
        
        const state = JSON.parse(stateStr);
        const ctxMenu = root.querySelector("#editor-context");
        const messageEl = root.querySelector("#editor-message");

        // Clone data to avoid mutations affecting original if needed, but here we manage it
        let matrix = JSON.parse(JSON.stringify(state.data || []));
        let original = JSON.parse(JSON.stringify(state.originalData || matrix));
        let rpmAxis = state.rpmAxis || [];
        let mapAxis = state.mapAxis || [];

        if (!Array.isArray(matrix) || matrix.length === 0) {
            showUIError("No table data rows provided. Try clicking 'Load from ECU'.");
            return;
        }

        let selection = [];
        let isSelecting = false;
        let anchor = null;
        let undoStack = [];
        let redoStack = [];

        function findGradioBox() {
           return document.querySelector(`#${state.payloadId} textarea`) || 
                  document.querySelector(`#${state.payloadId} input`);
        }

        function triggerGradio(id) {
          const btn = document.querySelector(`#${id} button`);
          if (btn) btn.click();
        }

        function updateMessage(msg) {
          if (messageEl) messageEl.textContent = msg;
          setTimeout(() => { if (messageEl.textContent === msg) messageEl.textContent = ""; }, 3000);
        }

        function emit() {
          const box = findGradioBox();
          if (!box) return;
          let changed = 0;
          let hasViolations = false, hasRisk = false;
          for(let r=0; r<matrix.length; r++) {
            for(let c=0; c<matrix[r].length; c++) {
              const v = matrix[r][c];
              if (Math.abs(v - original[r][c]) > 0.001) changed++;
              if (v < state.minAllowed || v > state.maxAllowed) hasViolations = true;
              if (v >= state.riskLow && v <= state.riskHigh) hasRisk = true;
            }
          }
          box.value = JSON.stringify({
            table_name: state.tableName,
            data: matrix,
            changed_count: changed,
            has_violations: hasViolations,
            has_risk: hasRisk,
            message: messageEl ? messageEl.textContent : ""
          });
          box.dispatchEvent(new Event("input", { bubbles: true }));
          triggerGradio(state.changeButtonId);
        }

        function pushUndo() {
          undoStack.push(JSON.stringify(matrix));
          if (undoStack.length > state.maxUndo) undoStack.shift();
          redoStack = [];
        }

        function setCellClass(td, val) {
          td.classList.remove("safe", "risk", "danger");
          if (val < state.minAllowed || val > state.maxAllowed) td.classList.add("danger");
          else if (val >= state.riskLow && val <= state.riskHigh) td.classList.add("risk");
          else td.classList.add("safe");
        }

        function calculateRect(a, b) {
          const minR = Math.min(a[0], b[0]), maxR = Math.max(a[0], b[0]);
          const minC = Math.min(a[1], b[1]), maxC = Math.max(a[1], b[1]);
          const res = [];
          for (let r = minR; r <= maxR; r++) {
            for (let c = minC; c <= maxC; c++) res.push([r, c]);
          }
          return res;
        }

        function paintSelection() {
          shell.querySelectorAll("td.selected").forEach(el => el.classList.remove("selected"));
          selection.forEach(([r, c]) => {
            const td = shell.querySelector(`td[data-row='${r}'][data-col='${c}']`);
            if (td) td.classList.add("selected");
          });
        }

        function syncGrid() {
          for(let r=0; r<matrix.length; r++) {
            for(let c=0; c<matrix[r].length; c++) {
              const td = shell.querySelector(`td[data-row='${r}'][data-col='${c}']`);
              if (td) {
                td.textContent = matrix[r][c].toString();
                setCellClass(td, matrix[r][c]);
              }
            }
          }
        }

        function makeCell(r, c, val) {
          const td = document.createElement("td");
          td.dataset.row = r; td.dataset.col = c;
          td.textContent = val.toString();
          td.contentEditable = state.connected ? "true" : "false";
          td.tabIndex = 0;
          setCellClass(td, val);
          
          td.addEventListener("mousedown", (e) => {
            if (e.button !== 0) return;
            isSelecting = true; anchor = [r, c];
            if (!e.shiftKey) selection = [[r, c]];
            else selection = calculateRect(anchor, [r, c]);
            paintSelection();
          });
          td.addEventListener("mouseover", () => {
            if (!isSelecting) return;
            selection = calculateRect(anchor, [r, c]);
            paintSelection();
          });
          td.addEventListener("input", () => {
            const v = parseFloat(td.textContent);
            if (!isNaN(v)) { 
              pushUndo();
              matrix[r][c] = v; 
              setCellClass(td, v); 
              emit(); 
            }
          });
          td.addEventListener("blur", () => { td.textContent = matrix[r][c].toString(); });
          td.addEventListener("contextmenu", (e) => {
            e.preventDefault();
            if (!selection.some(s => s[0] === r && s[1] === c)) { selection = [[r, c]]; paintSelection(); }
            if (ctxMenu) {
                ctxMenu.style.display = "block";
                const x = Math.min(e.clientX, window.innerWidth - 200);
                const y = Math.min(e.clientY, window.innerHeight - 300);
                ctxMenu.style.left = x + "px"; ctxMenu.style.top = y + "px";
            }
          });
          return td;
        }

        function render() {
          console.log("Rendering table...");
          shell.innerHTML = "";
          const table = document.createElement("table");
          table.id = "editor-grid";
          const thead = document.createElement("thead");
          const hr = document.createElement("tr");
          const corner = document.createElement("th");
          corner.innerHTML = "MAP \\\\ RPM"; 
          corner.classList.add("row-label");
          hr.appendChild(corner);
          
          rpmAxis.forEach(rpm => {
            const th = document.createElement("th"); th.textContent = rpm;
            hr.appendChild(th);
          });
          thead.appendChild(hr); table.appendChild(thead);
          
          const tbody = document.createElement("tbody");
          matrix.forEach((row, r) => {
            const tr = document.createElement("tr");
            const rable = document.createElement("th");
            rable.classList.add("row-label"); 
            rable.textContent = (mapAxis[r] !== undefined) ? mapAxis[r] : r;
            tr.appendChild(rable);
            if (Array.isArray(row)) {
                row.forEach((val, c) => { tr.appendChild(makeCell(r, c, val)); });
            }
            tbody.appendChild(tr);
          });
          table.appendChild(tbody); 
          shell.appendChild(table);
          console.log("Render completed for", state.tableName);
        }

        function applyAction(action) {
          if (!selection.length) return;
          pushUndo();
          const rows = selection.map(s => s[0]), cols = selection.map(s => s[1]);
          const minR = Math.min(...rows), maxR = Math.max(...rows);
          const minC = Math.min(...cols), maxC = Math.max(...cols);
          
          if (action === "average") {
            let sum = 0; selection.forEach(([r, c]) => sum += matrix[r][c]);
            const avg = parseFloat((sum / selection.length).toFixed(2));
            selection.forEach(([r, c]) => matrix[r][c] = avg);
          } else if (action === "interp_h") {
            for (let r = minR; r <= maxR; r++) {
              const vS = matrix[r][minC], vE = matrix[r][maxC], count = maxC - minC;
              if (count > 0) for (let c = minC; c <= maxC; c++) matrix[r][c] = parseFloat((vS + (vE - vS) * (c - minC) / count).toFixed(2));
            }
          } else if (action === "interp_v") {
            for (let c = minC; c <= maxC; c++) {
              const vS = matrix[minR][c], vE = matrix[maxR][c], count = maxR - minR;
              if (count > 0) for (let r = minR; r <= maxR; r++) matrix[r][c] = parseFloat((vS + (vE - vS) * (r - minR) / count).toFixed(2));
            }
          } else if (action === "interp_2d") {
              const v00 = matrix[minR][minC], v01 = matrix[minR][maxC], v10 = matrix[maxR][minC], v11 = matrix[maxR][maxC];
              const rC = maxR - minR, cC = maxC - minC;
              if (rC > 0 && cC > 0) for (let r = minR; r <= maxR; r++) for (let c = minC; c <= maxC; c++) {
                  const tr = (r - minR) / rC, tc = (c - minC) / cC;
                  matrix[r][c] = parseFloat(((1-tr)*(1-tc)*v00 + (1-tr)*tc*v01 + tr*(1-tc)*v10 + tr*tc*v11).toFixed(2));
              }
          } else if (action === "incr_5") { selection.forEach(([r, c]) => matrix[r][c] = parseFloat((matrix[r][c] * 1.05).toFixed(2))); }
          else if (action === "decr_5") { selection.forEach(([r, c]) => matrix[r][c] = parseFloat((matrix[r][c] * 0.95).toFixed(2))); }
          else if (action === "reset") { matrix = JSON.parse(JSON.stringify(original)); }
          
          syncGrid(); emit();
          updateMessage(`Applied ${action}`);
        }

        root.addEventListener("click", (e) => { 
          if (ctxMenu && !ctxMenu.contains(e.target)) ctxMenu.style.display = "none"; 
        });
        
        if (ctxMenu) {
            ctxMenu.querySelectorAll("button[data-action]").forEach(btn => {
              btn.addEventListener("click", () => {
                applyAction(btn.dataset.action);
                ctxMenu.style.display = "none";
              });
            });
        }

        const keyHandler = (e) => {
          if (!root.contains(document.activeElement) && document.activeElement !== document.body) return;
          if (e.ctrlKey && e.key.toLowerCase() === "z") { 
            e.preventDefault(); 
            if(undoStack.length) { 
              redoStack.push(JSON.stringify(matrix));
              matrix = JSON.parse(undoStack.pop()); 
              syncGrid(); emit(); updateMessage("Undo applied");
            }
          }
          if (e.ctrlKey && e.key.toLowerCase() === "s") { e.preventDefault(); triggerGradio(state.saveButtonId); }
        };
        root.addEventListener("keydown", keyHandler);
        document.addEventListener("mouseup", () => isSelecting = false);

        render();
        emit();
        updateMessage("Table Editor Ready");
    } catch (err) {
        console.error("Table Editor initialization error:", err);
        showUIError(err.message);
    }
  }

  // MutationObserver to catch dynamic updates
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.id === "table-editor-root") initEditor(node);
        else if (node.querySelectorAll) {
          node.querySelectorAll("#table-editor-root").forEach(initEditor);
        }
      }
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  // Periodically check for any missed nodes (safety fallback)
  setInterval(() => {
    document.querySelectorAll("#table-editor-root:not([data-initialized])").forEach(initEditor);
  }, 1000);

  // Initial scan
  document.querySelectorAll("#table-editor-root").forEach(initEditor);
})();
"""
