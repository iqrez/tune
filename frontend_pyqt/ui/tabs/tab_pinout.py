from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..theme import COLOR_ACCENT


_PIN_CHOICES: List[str] = (
    ["UNUSED"]
    + [f"A{i}" for i in range(1, 27)]
    + [f"B{i}" for i in range(1, 27)]
    + [f"D{i}" for i in range(1, 27)]
)


_BASE_HONDA_OBD1_PINOUT: List[Dict[str, str]] = [
    {"system": "Fuel", "function": "Injector Cylinder 1", "base_pin": "A1", "notes": "Common OBD1 P28 convention"},
    {"system": "Fuel", "function": "Injector Cylinder 2", "base_pin": "A3", "notes": "Common OBD1 P28 convention"},
    {"system": "Fuel", "function": "Injector Cylinder 3", "base_pin": "A5", "notes": "Common OBD1 P28 convention"},
    {"system": "Fuel", "function": "Injector Cylinder 4", "base_pin": "A7", "notes": "Common OBD1 P28 convention"},
    {"system": "Fuel", "function": "Fuel Pump Relay Control", "base_pin": "A15", "notes": "Main relay pump trigger"},
    {"system": "Ignition", "function": "Ignition Output", "base_pin": "A21", "notes": "Single-coil/ICM output path"},
    {"system": "VTEC", "function": "VTEC Solenoid Control", "base_pin": "A17", "notes": "VTEC enable output"},
    {"system": "VTEC", "function": "VTEC Pressure Switch", "base_pin": "D6", "notes": "Input, depends on harness"},
    {"system": "Trigger", "function": "CKP Positive", "base_pin": "B10", "notes": "Distributor crank input"},
    {"system": "Trigger", "function": "CKP Negative", "base_pin": "B12", "notes": "Distributor crank input"},
    {"system": "Trigger", "function": "TDC Positive", "base_pin": "B11", "notes": "Distributor top-dead-center input"},
    {"system": "Trigger", "function": "TDC Negative", "base_pin": "B13", "notes": "Distributor top-dead-center input"},
    {"system": "Trigger", "function": "CYL Positive", "base_pin": "B14", "notes": "Cylinder reference input"},
    {"system": "Trigger", "function": "CYL Negative", "base_pin": "B16", "notes": "Cylinder reference input"},
    {"system": "Sensors", "function": "TPS Signal", "base_pin": "D11", "notes": "Throttle position sensor"},
    {"system": "Sensors", "function": "MAP Signal", "base_pin": "D10", "notes": "MAP sensor signal"},
    {"system": "Sensors", "function": "ECT Signal", "base_pin": "D12", "notes": "Coolant temp signal"},
    {"system": "Sensors", "function": "IAT Signal", "base_pin": "D13", "notes": "Intake temp signal"},
    {"system": "Sensors", "function": "Primary O2 Sensor", "base_pin": "D14", "notes": "Wideband/controller dependent"},
    {"system": "Idle", "function": "Idle Valve Control", "base_pin": "A12", "notes": "IACV output path"},
    {"system": "Outputs", "function": "Radiator Fan Relay", "base_pin": "A16", "notes": "Fan relay control"},
    {"system": "Outputs", "function": "A/C Clutch Request", "base_pin": "A20", "notes": "A/C request/clutch logic"},
]

_FUNCTION_PARAM_HINTS: Dict[str, List[str]] = {
    "Injector Cylinder 1": ["injector", "1", "pin"],
    "Injector Cylinder 2": ["injector", "2", "pin"],
    "Injector Cylinder 3": ["injector", "3", "pin"],
    "Injector Cylinder 4": ["injector", "4", "pin"],
    "Fuel Pump Relay Control": ["fuel", "pump", "pin"],
    "Ignition Output": ["ignition", "pin"],
    "VTEC Solenoid Control": ["vtec", "pin"],
    "VTEC Pressure Switch": ["vtec", "switch", "pin"],
    "CKP Positive": ["ckp", "pin"],
    "CKP Negative": ["ckp", "pin"],
    "TDC Positive": ["tdc", "pin"],
    "TDC Negative": ["tdc", "pin"],
    "CYL Positive": ["cyl", "pin"],
    "CYL Negative": ["cyl", "pin"],
    "TPS Signal": ["tps", "pin"],
    "MAP Signal": ["map", "pin"],
    "ECT Signal": ["clt", "pin"],
    "IAT Signal": ["iat", "pin"],
    "Primary O2 Sensor": ["o2", "pin"],
    "Idle Valve Control": ["idle", "pin"],
    "Radiator Fan Relay": ["fan", "pin"],
    "A/C Clutch Request": ["ac", "pin"],
}


class PinoutTab(QWidget):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self._pin_combos: Dict[int, QComboBox] = {}
        self._ecu_pin_params: Dict[str, Any] = {}
        self._known_param_names: List[str] = []
        self._build_ui()
        self._load_base_template()

    def _build_ui(self):
        root = QVBoxLayout(self)

        header = QLabel("Configurable Pinout")
        header.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {COLOR_ACCENT};")
        root.addWidget(header)

        sub = QLabel(
            "Base route is preloaded for basic Honda OBD1. Verify against your board/harness before powering outputs."
        )
        sub.setStyleSheet("color: #B0B0B0; font-size: 12px;")
        sub.setWordWrap(True)
        root.addWidget(sub)

        controls = QHBoxLayout()

        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["Honda OBD1 Base"])
        self.profile_combo.setEnabled(False)
        controls.addWidget(QLabel("Template"))
        controls.addWidget(self.profile_combo)

        self.btn_reset = QPushButton("Reset to Honda OBD1 Base")
        self.btn_reset.setObjectName("PrimaryButton")
        self.btn_reset.clicked.connect(self._load_base_template)
        controls.addWidget(self.btn_reset)

        self.btn_validate = QPushButton("Validate Routing")
        self.btn_validate.clicked.connect(self._validate_pinout)
        controls.addWidget(self.btn_validate)

        self.btn_scan = QPushButton("Read ECU Pins (Read-only)")
        self.btn_scan.clicked.connect(self._scan_ecu_pins)
        controls.addWidget(self.btn_scan)

        self.btn_compare = QPushButton("Compare with ECU")
        self.btn_compare.clicked.connect(self._compare_with_ecu)
        controls.addWidget(self.btn_compare)

        self.btn_save = QPushButton("Save Layout")
        self.btn_save.clicked.connect(self._save_layout)
        controls.addWidget(self.btn_save)

        self.btn_load = QPushButton("Load Layout")
        self.btn_load.clicked.connect(self._load_layout)
        controls.addWidget(self.btn_load)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.clicked.connect(self._export_csv)
        controls.addWidget(self.btn_export)

        controls.addStretch()
        root.addLayout(controls)

        table_group = QGroupBox("Pin Mapping")
        table_layout = QVBoxLayout(table_group)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Enabled", "System", "Function", "Base Pin", "Assigned Pin", "ECU Param", "ECU Value", "Notes"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        table_layout.addWidget(self.table)
        root.addWidget(table_group, 1)

        ecu_group = QGroupBox("ECU Pin Parameter Audit (Read-only)")
        ecu_layout = QVBoxLayout(ecu_group)
        self.ecu_table = QTableWidget(0, 2)
        self.ecu_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.ecu_table.horizontalHeader().setStretchLastSection(True)
        self.ecu_table.verticalHeader().setVisible(False)
        self.ecu_table.setMaximumHeight(220)
        ecu_layout.addWidget(self.ecu_table)
        root.addWidget(ecu_group, 0)

        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet("color: #9B9B9B;")
        root.addWidget(self.lbl_status)

    def _load_base_template(self):
        self.table.setRowCount(0)
        self._pin_combos.clear()

        for row_data in _BASE_HONDA_OBD1_PINOUT:
            row = self.table.rowCount()
            self.table.insertRow(row)

            enabled = QTableWidgetItem()
            enabled.setFlags(enabled.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            enabled.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, enabled)

            self.table.setItem(row, 1, QTableWidgetItem(row_data["system"]))
            self.table.setItem(row, 2, QTableWidgetItem(row_data["function"]))
            self.table.setItem(row, 3, QTableWidgetItem(row_data["base_pin"]))

            combo = QComboBox()
            combo.addItems(_PIN_CHOICES)
            base_pin = row_data["base_pin"]
            idx = combo.findText(base_pin)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.currentTextChanged.connect(lambda _=None, r=row: self._update_row_visuals(r))
            self._pin_combos[row] = combo
            self.table.setCellWidget(row, 4, combo)

            notes_item = QTableWidgetItem(row_data.get("notes", ""))
            self.table.setItem(row, 7, notes_item)
            self.table.setItem(row, 5, QTableWidgetItem("--"))
            self.table.setItem(row, 6, QTableWidgetItem("--"))
            self._update_row_visuals(row)

        self.table.resizeColumnsToContents()
        self.lbl_status.setText("Loaded Honda OBD1 base template")

    def _collect_rows(self) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for row in range(self.table.rowCount()):
            enabled_item = self.table.item(row, 0)
            system = self.table.item(row, 1).text() if self.table.item(row, 1) else ""
            function = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
            base_pin = self.table.item(row, 3).text() if self.table.item(row, 3) else ""
            assigned = self._pin_combos[row].currentText() if row in self._pin_combos else "UNUSED"
            ecu_param = self.table.item(row, 5).text() if self.table.item(row, 5) else "--"
            ecu_value = self.table.item(row, 6).text() if self.table.item(row, 6) else "--"
            notes = self.table.item(row, 7).text() if self.table.item(row, 7) else ""
            out.append(
                {
                    "enabled": bool(enabled_item and enabled_item.checkState() == Qt.CheckState.Checked),
                    "system": system,
                    "function": function,
                    "base_pin": base_pin,
                    "assigned_pin": assigned,
                    "ecu_param": ecu_param,
                    "ecu_value": ecu_value,
                    "notes": notes,
                }
            )
        return out

    def _apply_rows(self, rows: List[Dict[str, str]]):
        lookup = {r.get("function", ""): r for r in rows}
        for row in range(self.table.rowCount()):
            fn = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
            incoming = lookup.get(fn)
            if not incoming:
                continue

            enabled_item = self.table.item(row, 0)
            if enabled_item is not None:
                enabled_item.setCheckState(Qt.CheckState.Checked if incoming.get("enabled", True) else Qt.CheckState.Unchecked)

            combo = self._pin_combos.get(row)
            if combo is not None:
                val = str(incoming.get("assigned_pin", "UNUSED"))
                idx = combo.findText(val)
                combo.setCurrentIndex(idx if idx >= 0 else 0)

            notes_item = self.table.item(row, 7)
            if notes_item is not None:
                notes_item.setText(str(incoming.get("notes", notes_item.text())))
            self._update_row_visuals(row)

    def _validate_pinout(self):
        used_by_pin: Dict[str, List[str]] = {}
        for row in self._collect_rows():
            if not row["enabled"]:
                continue
            pin = row["assigned_pin"]
            if pin == "UNUSED":
                continue
            used_by_pin.setdefault(pin, []).append(row["function"])

        conflicts = {pin: fns for pin, fns in used_by_pin.items() if len(fns) > 1}
        if conflicts:
            first_pin = next(iter(conflicts.keys()))
            first_funcs = ", ".join(conflicts[first_pin][:3])
            self.lbl_status.setText(
                f"Conflicts found: {len(conflicts)} duplicated pin(s). Example {first_pin}: {first_funcs}"
            )
            self.lbl_status.setStyleSheet("color: #CF6679; font-weight: 700;")
        else:
            self.lbl_status.setText("Validation OK: no duplicate assigned pins among enabled routes")
            self.lbl_status.setStyleSheet("color: #03DAC6; font-weight: 700;")

    def _default_save_path(self) -> Path:
        root = Path(__file__).resolve().parents[3]
        state_dir = root / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / "pinout_honda_obd1.json"

    def _save_layout(self):
        default_path = self._default_save_path()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Pinout Layout",
            str(default_path),
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return

        payload = {
            "template": "Honda OBD1 Base",
            "rows": self._collect_rows(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        self.lbl_status.setText(f"Saved layout: {path}")
        self.lbl_status.setStyleSheet("color: #9B9B9B;")

    def _load_layout(self):
        default_path = self._default_save_path()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Pinout Layout",
            str(default_path),
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            rows = payload.get("rows", []) if isinstance(payload, dict) else []
            if not isinstance(rows, list):
                self.lbl_status.setText("Invalid layout file format")
                self.lbl_status.setStyleSheet("color: #CF6679; font-weight: 700;")
                return
            self._apply_rows(rows)
            self.lbl_status.setText(f"Loaded layout: {path}")
            self.lbl_status.setStyleSheet("color: #9B9B9B;")
        except Exception as e:
            self.lbl_status.setText(f"Load failed: {e}")
            self.lbl_status.setStyleSheet("color: #CF6679; font-weight: 700;")

    def _export_csv(self):
        default_path = self._default_save_path().with_suffix(".csv")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Pinout CSV",
            str(default_path),
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        rows = self._collect_rows()
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "enabled",
                    "system",
                    "function",
                    "base_pin",
                    "assigned_pin",
                    "ecu_param",
                    "ecu_value",
                    "notes",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
        self.lbl_status.setText(f"Exported CSV: {path}")
        self.lbl_status.setStyleSheet("color: #9B9B9B;")

    def _update_row_visuals(self, row: int):
        base_item = self.table.item(row, 3)
        base_pin = base_item.text() if base_item else "UNUSED"
        assigned = self._pin_combos[row].currentText() if row in self._pin_combos else "UNUSED"
        changed = assigned != base_pin
        tint = QColor(50, 40, 10) if changed else QColor(0, 0, 0, 0)

        for col in (1, 2, 3, 7):
            item = self.table.item(row, col)
            if item:
                item.setBackground(tint)

    async def _scan_ecu_pins_async(self):
        self.lbl_status.setText("Reading ECU pin-related parameters (read-only)...")
        self.lbl_status.setStyleSheet("color: #9B9B9B;")

        params = await self.api.get_parameters(query="pin")
        names = sorted({(p.get("name") or "").strip() for p in (params or []) if (p.get("name") or "").strip()})
        self._known_param_names = names

        self._ecu_pin_params.clear()
        self.ecu_table.setRowCount(0)

        for name in names[:180]:
            data = await self.api.read_parameter(name)
            value = data.get("value") if data else None
            self._ecu_pin_params[name] = value
            row = self.ecu_table.rowCount()
            self.ecu_table.insertRow(row)
            self.ecu_table.setItem(row, 0, QTableWidgetItem(name))
            self.ecu_table.setItem(row, 1, QTableWidgetItem(str(value)))

        self.ecu_table.resizeColumnsToContents()
        self.lbl_status.setText(f"Read {len(self._ecu_pin_params)} ECU pin parameter(s) (no changes written)")
        self.lbl_status.setStyleSheet("color: #03DAC6; font-weight: 700;")

    def _scan_ecu_pins(self):
        import asyncio

        asyncio.ensure_future(self._scan_ecu_pins_async())

    @staticmethod
    def _slug(text: str) -> str:
        return "".join(ch for ch in (text or "").lower() if ch.isalnum())

    def _best_param_for_function(self, function_name: str) -> Optional[str]:
        if not self._known_param_names:
            return None
        hints = _FUNCTION_PARAM_HINTS.get(function_name, [])
        if not hints:
            return None

        scored: List[tuple[int, str]] = []
        for name in self._known_param_names:
            sl = self._slug(name)
            score = 0
            for token in hints:
                if self._slug(token) in sl:
                    score += 1
            if score > 0:
                scored.append((score, name))

        if not scored:
            return None
        scored.sort(key=lambda x: (-x[0], x[1]))
        return scored[0][1]

    def _compare_with_ecu(self):
        if not self._ecu_pin_params:
            self.lbl_status.setText("Read ECU pins first (Compare is read-only)")
            self.lbl_status.setStyleSheet("color: #CF6679; font-weight: 700;")
            return

        matched = 0
        for row in range(self.table.rowCount()):
            function = self.table.item(row, 2).text() if self.table.item(row, 2) else ""
            param = self._best_param_for_function(function)
            param_item = self.table.item(row, 5)
            value_item = self.table.item(row, 6)

            if param_item is None:
                param_item = QTableWidgetItem("--")
                self.table.setItem(row, 5, param_item)
            if value_item is None:
                value_item = QTableWidgetItem("--")
                self.table.setItem(row, 6, value_item)

            if not param:
                param_item.setText("--")
                value_item.setText("--")
                continue

            matched += 1
            param_item.setText(param)
            value_item.setText(str(self._ecu_pin_params.get(param)))

        self.lbl_status.setText(
            f"Compare complete: mapped {matched}/{self.table.rowCount()} functions to ECU pin params (read-only)"
        )
        self.lbl_status.setStyleSheet("color: #9B9B9B;")
