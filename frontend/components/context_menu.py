from __future__ import annotations

import html


MENU_ITEMS = [
    ("Edit Value", "edit_value"),
    ("Write to ECU Now", "write_now"),
    ("Burn to Flash", "burn"),
    ("Copy Value", "copy"),
    ("Paste Value", "paste"),
    ("Reset to Default", "reset"),
    ("Compare with .msq", "compare_msq"),
    ("Add to Watch List", "watch"),
    ("Undo Last Change", "undo"),
    ("Redo", "redo"),
    ("View in 3D (for tables only)", "view_3d"),
    ("Help (opens tooltip with description)", "help"),
]


def build_context_menu_html(target_id: str, payload_id: str, trigger_id: str, menu_id: str = "premium-context-menu") -> str:
    lis = []
    for label, action in MENU_ITEMS:
        lis.append(
            f"<button class='pcm-item' data-action='{html.escape(action)}' type='button'>{html.escape(label)}</button>"
        )
    return f"""
<style>
#{menu_id} {{
  position: fixed;
  display: none;
  min-width: 260px;
  z-index: 3000;
  background: #1A1A1A;
  border: 1px solid #3A3A3A;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.6);
  padding: 6px;
}}
#{menu_id} .pcm-item {{
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 6px;
  background: #1A1A1A;
  color: #E0E0E0;
  padding: 6px 10px;
  margin: 2px 0;
  font-size: 12px;
}}
#{menu_id} .pcm-item:hover {{
  filter: brightness(1.08);
  border: 2px solid #FF6600;
}}
</style>
<div id="{menu_id}">
  {''.join(lis)}
</div>
<script>
(function() {{
  const menu = document.getElementById('{menu_id}');
  if (!menu || menu.dataset.bound === '1') return;
  menu.dataset.bound = '1';

  function hideMenu() {{
    menu.style.display = 'none';
  }}

  function emitAction(action) {{
    const input = document.querySelector('#{payload_id} textarea, #{payload_id} input');
    const trigger = document.querySelector('#{trigger_id} button');
    if (!input || !trigger) return;
    input.value = JSON.stringify({{ action, ts: Date.now() }});
    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
    trigger.click();
  }}

  document.addEventListener('contextmenu', function(ev) {{
    const root = document.getElementById('{target_id}');
    if (!root) return;
    if (!root.contains(ev.target)) return;
    ev.preventDefault();
    menu.style.display = 'block';
    menu.style.left = Math.min(ev.clientX, window.innerWidth - 280) + 'px';
    menu.style.top = Math.min(ev.clientY, window.innerHeight - 360) + 'px';
  }}, true);

  document.addEventListener('click', function(ev) {{
    if (!menu.contains(ev.target)) hideMenu();
  }});

  menu.addEventListener('click', function(ev) {{
    const btn = ev.target.closest('.pcm-item');
    if (!btn) return;
    const action = btn.getAttribute('data-action') || '';
    hideMenu();
    emitAction(action);
  }});

  document.addEventListener('keydown', function(ev) {{
    if (ev.key === 'Escape') hideMenu();
  }});
}})();
</script>
"""


def build_shortcuts_js(
    center_id: str,
    burn_btn_id: str,
    load_btn_id: str,
    datalog_btn_id: str,
    refresh_btn_id: str,
    open_table_btn_id: str,
    shortcut_payload_id: str,
    shortcut_trigger_id: str,
) -> str:
    return f"""
<script>
(function() {{
  if (window.__premiumShortcutsBound) return;
  window.__premiumShortcutsBound = true;

  function clickButton(id) {{
    const btn = document.querySelector('#' + id + ' button');
    if (btn) btn.click();
  }}

  function emitShortcut(action) {{
    const input = document.querySelector('#{shortcut_payload_id} textarea, #{shortcut_payload_id} input');
    const trigger = document.querySelector('#{shortcut_trigger_id} button');
    if (!input || !trigger) return;
    input.value = JSON.stringify({{ action, ts: Date.now() }});
    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
    trigger.click();
  }}

  document.addEventListener('keydown', function(ev) {{
    const key = (ev.key || '').toLowerCase();
    const center = document.getElementById('{center_id}');
    const centerFocused = center && (center.contains(document.activeElement) || document.activeElement === document.body);

    if (ev.ctrlKey && !ev.shiftKey && key === 's') {{
      ev.preventDefault();
      clickButton('{burn_btn_id}');
      return;
    }}
    if (ev.ctrlKey && !ev.shiftKey && key === 'l') {{
      ev.preventDefault();
      clickButton('{load_btn_id}');
      return;
    }}
    if (ev.ctrlKey && !ev.shiftKey && key === 'z') {{
      ev.preventDefault();
      emitShortcut('undo');
      return;
    }}
    if (ev.ctrlKey && !ev.shiftKey && key === 'y') {{
      ev.preventDefault();
      emitShortcut('redo');
      return;
    }}
    if (ev.code === 'Space' && centerFocused) {{
      ev.preventDefault();
      clickButton('{datalog_btn_id}');
      return;
    }}
    if (key === 'f5') {{
      ev.preventDefault();
      clickButton('{refresh_btn_id}');
      return;
    }}
    if (ev.ctrlKey && ev.shiftKey && key === 't') {{
      ev.preventDefault();
      clickButton('{open_table_btn_id}');
      return;
    }}
    if (key === 'escape') {{
      emitShortcut('escape');
      return;
    }}
  }});
}})();
</script>
"""
