"""
Tab 1: Full Tuning (Honda-centric)
Left: VTEC-first tuning tree
Center: Scalar/table editor
Right: Live gauges + watch list
Bottom: collapsible datalog playback strip
"""

from __future__ import annotations

import asyncio
import math
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter

from ..components.datalog_strip import DatalogStrip
from ..components.dialog_factory import create_parameter_dialog
from ..components.editor_pane import EditorPane
from ..components.gauge_panel import GaugePanel
from ..components.tree_view import ParameterTreeView


class TuningTab(QWidget):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api

        self._params_list: List[Dict[str, Any]] = []
        self._ecu_connected = False
        self._category_fetch_token = 0

        self._watch_list: List[str] = []
        self._watch_values: Dict[str, Any] = {}
        self._watch_poll_inflight = False
        self._open_dialogs: Dict[str, QWidget] = {}

        self._build_ui()

        self._watch_timer = QTimer(self)
        self._watch_timer.timeout.connect(self._poll_watch_values)
        self._watch_timer.start(600)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.tree = ParameterTreeView()
        splitter.addWidget(self.tree)

        self.editor = EditorPane()
        splitter.addWidget(self.editor)

        self.gauges = GaugePanel()
        splitter.addWidget(self.gauges)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([360, 820, 300])

        root.addWidget(splitter, 1)

        self.strip = DatalogStrip()
        root.addWidget(self.strip, 0)

        self.tree.item_selected.connect(self._on_param_selected)
        self.tree.category_selected.connect(self._on_category_selected)
        self.tree.context_action.connect(self._on_tree_context_action)
        self.editor.param_requested.connect(self._on_param_requested)
        self.editor.btn_save_scalar.clicked.connect(self._on_save_scalar)
        self.editor.btn_save_table.clicked.connect(self._on_save_table)

    # ------------------------------------------------------------------ External API
    def load_parameters(self, params_list):
        self._params_list = list(params_list or [])
        self.tree.load_parameters(self._params_list)

    def update_live_data(self, data):
        self._ecu_connected = bool((data or {}).get("connected", False))
        self.tree.update_live_data(data)
        self.gauges.update_data(data)
        self.gauges.update_watch_from_live(self._watch_list, data or {})

        if data and data.get("rpm") is not None:
            try:
                self.strip.push_sample(float(data.get("rpm")))
            except (TypeError, ValueError):
                pass

        self.editor.update_table_hit((data or {}).get("rpm"), (data or {}).get("map_kpa"))

    def mark_preset_changes(self, changed_names):
        self.tree.mark_preset_changes(list(changed_names or []))

    def select_parameter(self, name: str):
        if not name:
            return
        self._on_param_selected("", name)

    def _param_names_set(self) -> set[str]:
        return {(p.get("name") or "").strip() for p in self._params_list if (p.get("name") or "").strip()}

    def _first_existing(self, candidates: List[str]) -> Optional[str]:
        names = self._param_names_set()
        for c in candidates:
            if c in names:
                return c
        return None

    @staticmethod
    def _read_fallback_candidates(name: str) -> List[str]:
        fallbacks = {
            "veTable1": ["veTable1", "veTable", "veTable2"],
            "veTable2": ["veTable2", "veTable", "veTable1"],
            "ignitionTable1": ["ignitionTable1", "ignitionTable", "ignitionTable2"],
            "ignitionTable2": ["ignitionTable2", "ignitionTable", "ignitionTable1"],
        }
        return list(fallbacks.get(name, [name]))

    def apply_map_switch(self, *, fuel_map: Optional[int] = None, ign_map: Optional[int] = None):
        async def run():
            if fuel_map in (1, 2):
                for key in ("veMapSwitch", "fuelMapSelect"):
                    if self._first_existing([key]):
                        await self.api.write_parameter(key, fuel_map)

                table_name = self._first_existing(
                    ["veTable1", "veTable"] if fuel_map == 1 else ["veTable2", "veTable1", "veTable"]
                ) or ("veTable1" if fuel_map == 1 else "veTable2")
                self._on_param_selected("Fuel > Fuel Maps", table_name)

            if ign_map in (1, 2):
                for key in ("ignitionMapSwitch", "sparkMapSelect"):
                    if self._first_existing([key]):
                        await self.api.write_parameter(key, ign_map)

                table_name = self._first_existing(
                    ["ignitionTable1", "ignitionTable"] if ign_map == 1 else ["ignitionTable2", "ignitionTable1", "ignitionTable"]
                ) or ("ignitionTable1" if ign_map == 1 else "ignitionTable2")
                self._on_param_selected("Ignition > Ignition Maps", table_name)

        asyncio.ensure_future(run())

    # ------------------------------------------------------------------ Selection
    def _reshape_flat(self, flat_list):
        size = len(flat_list)
        side = int(math.sqrt(size))
        if side * side == size:
            return [flat_list[i * side : (i + 1) * side] for i in range(side)]
        for r in [16, 12, 8, 6, 4]:
            if size % r == 0:
                c = size // r
                return [flat_list[i * c : (i + 1) * c] for i in range(r)]
        return [flat_list]

    def _on_param_requested(self, name: str):
        self._on_param_selected("", name)

    def _find_param_meta(self, name: str):
        for p in self._params_list:
            if (p.get("name") or "").strip() == name:
                return p
        return {}

    def _is_table_like(self, name: str, meta: Dict[str, Any], value: Any) -> bool:
        kind = (meta.get("kind") or "").lower()
        if kind == "array":
            return True
        if isinstance(value, list):
            return True
        n = (name or "").lower()
        return any(token in n for token in ("table", "map", "trim cyl", "dwell"))

    def _on_param_selected(self, category, name):
        if not name:
            return

        meta = dict(self._find_param_meta(name) or {})
        if category and not meta.get("category"):
            meta["category"] = category

        self.editor.header.setText(f"Loading: {name}...")

        async def fetch_and_show():
            value = None
            read_name = name

            for candidate in self._read_fallback_candidates(name):
                data = await self.api.read_parameter(candidate)
                if data:
                    value = data.get("value")
                    read_name = candidate
                    break

            if self._is_table_like(read_name, meta, value):
                if isinstance(value, list) and value and not isinstance(value[0], list):
                    value = self._reshape_flat(value)
                self.editor.show_table(name, value if isinstance(value, list) else [[0.0] * 8 for _ in range(8)])
            else:
                if value is None:
                    self.editor.show_placeholder(name, category=category, reason="Parameter not available in current INI map.")
                else:
                    self.editor.show_scalar(name, value)

            self._open_param_dialog(name, value if value is not None else 0, category)

        asyncio.ensure_future(fetch_and_show())

    def _open_param_dialog(self, name: str, value: Any, category: str = ""):
        existing = self._open_dialogs.get(name)
        if existing is not None:
            try:
                existing.raise_()
                existing.activateWindow()
                return
            except Exception:
                self._open_dialogs.pop(name, None)

        meta = dict(self._find_param_meta(name) or {})
        if category and not meta.get("category"):
            meta["category"] = category

        dlg = create_parameter_dialog(self.api, name=name, value=value, meta=meta, parent=self)
        dlg.setModal(False)
        dlg.show()

        self._open_dialogs[name] = dlg
        dlg.destroyed.connect(lambda *_args, key=name: self._open_dialogs.pop(key, None))

    def _on_category_selected(self, category_path: str):
        if not category_path or category_path.startswith("Live Vehicle Data"):
            return

        selected = category_path.strip()
        entries: List[Dict[str, Any]] = []

        prefix = f"{selected} > "
        for p in self._params_list:
            name = (p.get("name") or "").strip()
            if not name:
                continue
            kind = (p.get("kind") or "").strip().lower()
            normalized_parts = self.tree._normalize_path_parts(p.get("category", ""), name, kind)
            normalized = " > ".join(normalized_parts)

            if normalized == selected or normalized.startswith(prefix):
                row = dict(p)
                row["_normalized_category"] = normalized
                entries.append(row)

        self.editor.show_category(selected, entries)

        self._category_fetch_token += 1
        token = self._category_fetch_token
        asyncio.ensure_future(self._populate_category_values(entries, token))

    def _format_browser_value(self, value, kind: str = ""):
        if value is None:
            return "--"
        kind_l = (kind or "").lower()
        if isinstance(value, list):
            if value and isinstance(value[0], list):
                rows = len(value)
                cols = len(value[0]) if value[0] else 0
                return f"[table {rows}x{cols}]"
            return f"[array {len(value)}]"
        if kind_l == "bits":
            try:
                ival = int(float(value))
            except (TypeError, ValueError):
                return str(value)
            if ival in (0, 1):
                return "Off" if ival == 0 else "On"
            return str(ival)
        if isinstance(value, bool):
            return "On" if value else "Off"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            if abs(value) >= 1000:
                return f"{value:.0f}"
            if abs(value) >= 10:
                return f"{value:.2f}"
            return f"{value:.3f}"
        return str(value)

    async def _populate_category_values(self, entries, token: int):
        if token != self._category_fetch_token or not entries:
            return

        if not self._ecu_connected:
            self.editor.set_browser_status("ECU disconnected. Metadata shown; connect to load live values.")
            return

        candidates = []
        seen = set()
        for entry in entries:
            name = (entry.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            kind = (entry.get("kind") or "").lower()
            if kind == "array":
                self.editor.set_browser_value(name, "[table]")
                continue
            candidates.append((name, kind))
            self.editor.set_browser_value(name, "...")

        candidates = candidates[:40]
        if not candidates:
            return

        self.editor.set_browser_status(f"Loading {len(candidates)} values from ECU...")
        sem = asyncio.Semaphore(4)
        loaded = 0

        async def read_one(param_name: str, kind: str):
            nonlocal loaded
            if token != self._category_fetch_token:
                return
            async with sem:
                data = await self.api.read_parameter(param_name)
            if token != self._category_fetch_token:
                return

            if not data:
                self.editor.set_browser_value(param_name, "--")
            else:
                self.editor.set_browser_value(param_name, self._format_browser_value(data.get("value"), kind))

            loaded += 1
            if loaded % 8 == 0 or loaded == len(candidates):
                self.editor.set_browser_status(f"Loaded {loaded}/{len(candidates)} values")

        await asyncio.gather(*(read_one(name, kind) for name, kind in candidates))

    # ------------------------------------------------------------------ Watch list
    def _watch_name_is_live(self, name: str) -> bool:
        slug = "".join(ch for ch in str(name).lower() if ch.isalnum())
        return slug in {
            "rpm", "map", "mapkpa", "afr", "iat", "ect", "ignitionadvance", "advance", "knock", "knockcount", "injectorduty", "duty", "voltage", "tps"
        }

    def _set_watch_list(self):
        self.gauges.set_watch_list(self._watch_list)
        self.gauges.update_watch_values(self._watch_values)

    def _poll_watch_values(self):
        if self._watch_poll_inflight or not self._watch_list or not self._ecu_connected:
            return

        non_live = [n for n in self._watch_list if not self._watch_name_is_live(n)]
        if not non_live:
            return

        self._watch_poll_inflight = True

        async def run():
            try:
                for name in non_live[:12]:
                    data = await self.api.read_parameter(name)
                    if not data:
                        continue
                    value = data.get("value")
                    self._watch_values[name] = self._format_browser_value(value)
                self.gauges.update_watch_values(self._watch_values)
            finally:
                self._watch_poll_inflight = False

        asyncio.ensure_future(run())

    # ------------------------------------------------------------------ Context actions
    def _on_tree_context_action(self, action_id: str, name: str):
        if not name:
            return
        meta = self._find_param_meta(name)
        kind = (meta.get("kind") or "").lower()

        if action_id == "edit_value":
            self._on_param_selected("", name)
            return

        if action_id == "add_watch":
            if name not in self._watch_list:
                self._watch_list.append(name)
            self._set_watch_list()
            self.editor.header.setText(f"Watch added: {name}")
            return

        if action_id == "remove_watch":
            self._watch_list = [n for n in self._watch_list if n != name]
            self._watch_values.pop(name, None)
            self._set_watch_list()
            self.editor.header.setText(f"Watch removed: {name}")
            return

        if action_id == "help":
            units = meta.get("units", "")
            rng = f"{meta.get('min', '-') } .. {meta.get('max', '-')}"
            cat = meta.get("category", "Unknown")
            self.editor.header.setText(f"Help: {name} | Category: {cat} | Units: {units} | Range: {rng}")
            return

        if action_id == "compare_msq":
            self.editor.header.setText(f"Compare with .msq queued for {name}")
            return

        if action_id == "view_3d":
            if kind != "array":
                self.editor.header.setText(f"3D view is only available for table parameters ({name})")
                return

            async def load_table_then_show():
                data = await self.api.read_parameter(name)
                if not data:
                    self.editor.header.setText(f"Read failed: {name}")
                    return
                value = data.get("value")
                if value and isinstance(value, list) and not isinstance(value[0], list):
                    value = self._reshape_flat(value)
                self.editor.show_table(name, value or [])
                self.editor.param_tabs.setCurrentIndex(1)
                self.editor.on_view_3d()

            asyncio.ensure_future(load_table_then_show())
            return

        if action_id in ("copy_value", "write_to_ecu", "paste_value", "reset_default", "burn_now"):
            async def do_action():
                if action_id == "burn_now":
                    ok = await self.api.burn()
                    self.editor.header.setText("Burn successful" if ok else "Burn failed")
                    return

                if action_id == "paste_value":
                    from PyQt6.QtWidgets import QApplication

                    txt = QApplication.clipboard().text().strip()
                    try:
                        pasted = float(txt)
                    except ValueError:
                        self.editor.header.setText(f"Clipboard is not numeric: {txt[:40]}")
                        return
                    ok = await self.api.write_parameter(name, pasted)
                    self.editor.header.setText(f"Pasted {pasted} to {name}" if ok else f"Paste write failed: {name}")
                    return

                read = await self.api.read_parameter(name)
                if not read:
                    self.editor.header.setText(f"Read failed: {name}")
                    return
                value = read.get("value")

                if action_id == "copy_value":
                    from PyQt6.QtWidgets import QApplication

                    QApplication.clipboard().setText(str(value))
                    self.editor.header.setText(f"Copied {name} value")
                    return

                if action_id == "write_to_ecu":
                    ok = await self.api.write_parameter(name, value)
                    self.editor.header.setText(f"Wrote {name}" if ok else f"Write failed: {name}")
                    return

                if action_id == "reset_default":
                    if kind == "array":
                        self.editor.header.setText(f"Reset default unavailable for table {name}")
                        return
                    default = meta.get("min") if meta.get("min") is not None else 0.0
                    ok = await self.api.write_parameter(name, default)
                    self.editor.header.setText(f"Reset {name} to {default}" if ok else f"Reset failed: {name}")
                    return

            asyncio.ensure_future(do_action())

    # ------------------------------------------------------------------ Save actions
    def _on_save_scalar(self):
        name = self.editor._current_param_name
        if not name:
            return
        raw = self.editor.scalar_input.text().strip()
        try:
            value = float(raw)
        except ValueError:
            self.editor.header.setText("Value must be numeric")
            return

        async def save():
            ok = await self.api.write_parameter(name, value)
            self.editor.header.setText(f"Written: {name} = {value}" if ok else f"Write failed: {name}")

        asyncio.ensure_future(save())

    def _on_save_table(self):
        name = self.editor._current_param_name
        if not name:
            return
        data = self.editor.table_editor.get_table_data()

        async def save():
            ok = await self.api.write_parameter(name, data)
            self.editor.header.setText(f"Table {name} written" if ok else f"Write failed: {name}")

        asyncio.ensure_future(save())
