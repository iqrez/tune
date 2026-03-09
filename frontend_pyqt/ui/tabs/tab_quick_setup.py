from __future__ import annotations

import asyncio
from typing import Dict, List, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..theme import COLOR_ACCENT


class QuickSetupTab(QWidget):
    """Fast, task-oriented entry screen similar to SManager/Hondata quick workflow."""

    connect_requested = pyqtSignal()
    burn_requested = pyqtSignal()
    load_preset_requested = pyqtSignal()
    load_msq_requested = pyqtSignal()
    save_msq_requested = pyqtSignal()
    datalog_toggle_requested = pyqtSignal()
    open_tuning_parameter = pyqtSignal(str)

    _FIELD_ALIASES: Dict[str, List[str]] = {
        "injectorFlow": ["injectorFlow", "injector_flow", "wizardInjectorFlow"],
        "injectorDeadTime": ["injectorDeadTime", "injector_dead_time", "injectorDeadtimeMs"],
        "idleRpmTarget": ["idleRpmTarget", "acIdleRpmTarget", "cltIdleRpm"],
        "vtecEngagementRPM": ["vtecEngagementRPM", "vtecRpm"],
        "rpmHardLimit": ["rpmHardLimit", "rpmLimit"],
        "boostCutPressure": ["boostCutPressure", "boostCut"],
        "fanOnTemperature": ["fanOnTemperature", "fanOnTemp"],
        "fanOffTemperature": ["fanOffTemperature", "fanOffTemp"],
    }

    _MAP_ALIASES: Dict[str, List[str]] = {
        "veTable1": ["veTable1", "veTable", "ve1"],
        "veTable2": ["veTable2", "veTableSecondary", "veTable"],
        "ignitionTable1": ["ignitionTable1", "ignitionTable", "sparkTable1"],
        "ignitionTable2": ["ignitionTable2", "ignitionTable", "sparkTable2"],
        "afrTable1": ["afrTable1", "lambdaTable", "targetAfrBlends1_table"],
        "vtecEngagementRPM": ["vtecEngagementRPM", "vtecRpm"],
    }

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self._field_widgets: Dict[str, QDoubleSpinBox] = {}
        self._field_labels: Dict[str, QLabel] = {}
        self._field_display_names: Dict[str, str] = {}
        self._available_param_names: set[str] = set()
        self._resolved_fields: Dict[str, str] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        header_row = QHBoxLayout()
        title = QLabel("Quick Setup")
        title.setStyleSheet(f"font-size: 24px; font-weight: 700; color: {COLOR_ACCENT};")
        header_row.addWidget(title)
        header_row.addStretch()
        self.lbl_connection = QLabel("ECU: DISCONNECTED")
        self.lbl_connection.setStyleSheet("color: #CF6679; font-weight: 700;")
        header_row.addWidget(self.lbl_connection)
        root.addLayout(header_row)

        subtitle = QLabel("Simple flow: Connect ECU -> Load preset -> Verify basics -> Edit maps -> Burn")
        subtitle.setStyleSheet("color: #B0B0B0; font-size: 12px;")
        root.addWidget(subtitle)

        session_box = QGroupBox("Session Controls")
        session_row = QHBoxLayout(session_box)

        self.btn_connect = QPushButton("1) Connect ECU")
        self.btn_connect.setObjectName("PrimaryButton")
        self.btn_connect.clicked.connect(self.connect_requested.emit)
        session_row.addWidget(self.btn_connect)

        self.btn_preset = QPushButton("2) Load Honda Preset")
        self.btn_preset.clicked.connect(self.load_preset_requested.emit)
        session_row.addWidget(self.btn_preset)

        self.btn_load = QPushButton("Open Tune (.msq)")
        self.btn_load.clicked.connect(self.load_msq_requested.emit)
        session_row.addWidget(self.btn_load)

        self.btn_save = QPushButton("Save Tune (.msq)")
        self.btn_save.clicked.connect(self.save_msq_requested.emit)
        session_row.addWidget(self.btn_save)

        self.btn_log = QPushButton("Start Log")
        self.btn_log.clicked.connect(self.datalog_toggle_requested.emit)
        session_row.addWidget(self.btn_log)

        self.btn_burn = QPushButton("5) Burn to ECU")
        self.btn_burn.setObjectName("PrimaryButton")
        self.btn_burn.clicked.connect(self.burn_requested.emit)
        session_row.addWidget(self.btn_burn)

        root.addWidget(session_box)

        grid = QGridLayout()
        root.addLayout(grid, 1)

        basics_box = QGroupBox("Core Honda/Base Tune Settings")
        basics_layout = QFormLayout(basics_box)

        self._add_scalar_field(basics_layout, "Injector Size (cc/min)", "injectorFlow", 100.0, 3000.0, 1.0, 1)
        self._add_scalar_field(basics_layout, "Injector Dead Time (ms)", "injectorDeadTime", 0.1, 3.0, 0.01, 3)
        self._add_scalar_field(basics_layout, "Idle Target (RPM)", "idleRpmTarget", 500.0, 1800.0, 10.0, 0)
        self._add_scalar_field(basics_layout, "VTEC Crossover (RPM)", "vtecEngagementRPM", 3000.0, 9000.0, 50.0, 0)
        self._add_scalar_field(basics_layout, "Rev Limit (RPM)", "rpmHardLimit", 5500.0, 11000.0, 50.0, 0)
        self._add_scalar_field(basics_layout, "Boost Cut (kPa)", "boostCutPressure", 100.0, 400.0, 1.0, 1)
        self._add_scalar_field(basics_layout, "Fan ON (C)", "fanOnTemperature", 60.0, 120.0, 1.0, 0)
        self._add_scalar_field(basics_layout, "Fan OFF (C)", "fanOffTemperature", 50.0, 115.0, 1.0, 0)

        button_row = QHBoxLayout()
        self.btn_read_basics = QPushButton("3) Read Basics from ECU")
        self.btn_read_basics.clicked.connect(self._on_read_basics_clicked)
        button_row.addWidget(self.btn_read_basics)

        self.btn_write_basics = QPushButton("4) Write Basics to RAM")
        self.btn_write_basics.setObjectName("PrimaryButton")
        self.btn_write_basics.clicked.connect(self._on_write_basics_clicked)
        button_row.addWidget(self.btn_write_basics)
        button_row.addStretch()
        basics_layout.addRow("", self._wrap_layout(button_row))

        self.lbl_basics_status = QLabel("Ready")
        self.lbl_basics_status.setStyleSheet("color: #9B9B9B;")
        basics_layout.addRow("Status", self.lbl_basics_status)

        grid.addWidget(basics_box, 0, 0)

        maps_box = QGroupBox("Quick Jump to Common Maps")
        maps_layout = QVBoxLayout(maps_box)
        jump_grid = QGridLayout()

        self._add_jump_button(jump_grid, "Fuel VE Map 1", "veTable1", 0, 0)
        self._add_jump_button(jump_grid, "Fuel VE Map 2", "veTable2", 0, 1)
        self._add_jump_button(jump_grid, "Ignition Map 1", "ignitionTable1", 1, 0)
        self._add_jump_button(jump_grid, "Ignition Map 2", "ignitionTable2", 1, 1)
        self._add_jump_button(jump_grid, "AFR Target Map", "afrTable1", 2, 0)
        self._add_jump_button(jump_grid, "VTEC Setting", "vtecEngagementRPM", 2, 1)
        maps_layout.addLayout(jump_grid)

        maps_note = QLabel("Tip: use selection + quick trim (+/-2% / +/-5%) inside the map editor.")
        maps_note.setStyleSheet("color: #9B9B9B; font-size: 11px;")
        maps_layout.addWidget(maps_note)
        maps_layout.addStretch()
        grid.addWidget(maps_box, 0, 1)

        live_box = QGroupBox("Live Snapshot")
        live_layout = QGridLayout(live_box)
        self._live_labels: Dict[str, QLabel] = {}
        channels = [
            ("RPM", 0, 0),
            ("MAP (kPa)", 0, 1),
            ("AFR", 0, 2),
            ("ECT (C)", 1, 0),
            ("IAT (C)", 1, 1),
            ("TPS (%)", 1, 2),
        ]
        for name, row, col in channels:
            card = QGroupBox(name)
            card_layout = QVBoxLayout(card)
            val = QLabel("--")
            val.setStyleSheet("font-size: 20px; font-weight: 700; color: #E6E6E6;")
            card_layout.addWidget(val)
            self._live_labels[name] = val
            live_layout.addWidget(card, row, col)

        grid.addWidget(live_box, 1, 0, 1, 2)

        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        grid.setRowStretch(0, 2)
        grid.setRowStretch(1, 1)

    @staticmethod
    def _wrap_layout(layout):
        w = QWidget()
        w.setLayout(layout)
        return w

    def _add_scalar_field(
        self,
        form: QFormLayout,
        label: str,
        param: str,
        min_v: float,
        max_v: float,
        step: float,
        decimals: int,
    ):
        spin = QDoubleSpinBox()
        spin.setRange(min_v, max_v)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        if decimals == 0:
            spin.setValue((min_v + max_v) / 2.0)
        label_widget = QLabel(label)
        form.addRow(label_widget, spin)
        self._field_widgets[param] = spin
        self._field_labels[param] = label_widget
        self._field_display_names[param] = label

    def _add_jump_button(self, grid: QGridLayout, title: str, param_name: str, row: int, col: int):
        btn = QPushButton(title)
        btn.clicked.connect(lambda _checked=False, name=param_name: self._emit_resolved_jump(name))
        grid.addWidget(btn, row, col)

    @staticmethod
    def _slug(text: str) -> str:
        return "".join(ch for ch in (text or "").lower() if ch.isalnum())

    def _resolve_name(self, canonical: str, alias_map: Dict[str, List[str]]) -> Optional[str]:
        if not self._available_param_names:
            return canonical

        aliases = alias_map.get(canonical, [canonical])
        by_slug = {self._slug(n): n for n in self._available_param_names}
        for alias in aliases:
            direct = alias if alias in self._available_param_names else None
            if direct:
                return direct
            s = by_slug.get(self._slug(alias))
            if s:
                return s
        return None

    def load_parameters(self, params_list):
        self._available_param_names = {
            (p.get("name") or "").strip()
            for p in (params_list or [])
            if (p.get("name") or "").strip()
        }
        self._resolved_fields.clear()

        for canonical in self._field_widgets.keys():
            resolved = self._resolve_name(canonical, self._FIELD_ALIASES)
            if resolved:
                self._resolved_fields[canonical] = resolved
                self._field_widgets[canonical].setEnabled(True)
                self._field_widgets[canonical].setVisible(True)
                self._field_labels[canonical].setStyleSheet("")
                self._field_labels[canonical].setVisible(True)
            else:
                self._field_widgets[canonical].setEnabled(False)
                self._field_widgets[canonical].setVisible(False)
                self._field_labels[canonical].setStyleSheet("color: #777777;")
                self._field_labels[canonical].setVisible(False)

    def _emit_resolved_jump(self, canonical: str):
        resolved = self._resolve_name(canonical, self._MAP_ALIASES)
        if resolved:
            self.open_tuning_parameter.emit(resolved)
        else:
            self.lbl_basics_status.setText(f"Map not available: {canonical}")

    def set_datalog_recording(self, recording: bool):
        self.btn_log.setText("Stop Log" if recording else "Start Log")

    def update_live_data(self, data):
        connected = bool((data or {}).get("connected", False))
        if connected:
            self.lbl_connection.setText("ECU: CONNECTED")
            self.lbl_connection.setStyleSheet("color: #03DAC6; font-weight: 700;")
        else:
            self.lbl_connection.setText("ECU: DISCONNECTED")
            self.lbl_connection.setStyleSheet("color: #CF6679; font-weight: 700;")

        if not data:
            return

        values = {
            "RPM": data.get("rpm"),
            "MAP (kPa)": data.get("map_kpa"),
            "AFR": data.get("afr"),
            "ECT (C)": data.get("ect"),
            "IAT (C)": data.get("iat"),
            "TPS (%)": data.get("tps"),
        }
        for key, raw in values.items():
            lbl = self._live_labels.get(key)
            if not lbl:
                continue
            if raw is None:
                lbl.setText("--")
                continue
            try:
                number = float(raw)
                if key == "RPM":
                    lbl.setText(f"{int(number)}")
                elif key == "AFR":
                    lbl.setText(f"{number:.2f}")
                else:
                    lbl.setText(f"{number:.1f}")
            except (TypeError, ValueError):
                lbl.setText(str(raw))

    def _on_read_basics_clicked(self):
        self.lbl_basics_status.setText("Reading from ECU...")
        asyncio.ensure_future(self._read_basics())

    async def _read_basics(self):
        total = len(self._field_widgets)
        loaded = 0
        missing = 0
        missing_names: List[str] = []

        for canonical, widget in self._field_widgets.items():
            name = self._resolved_fields.get(canonical)
            if not name:
                missing += 1
                missing_names.append(self._field_display_names.get(canonical, canonical))
                continue
            data = await self.api.read_parameter(name)
            if not data:
                continue
            value = data.get("value")
            if isinstance(value, (int, float)):
                widget.setValue(float(value))
                loaded += 1

        suffix = ""
        if missing_names:
            suffix = f" | Missing: {', '.join(missing_names)}"
        self.lbl_basics_status.setText(f"Loaded {loaded}/{total} settings ({missing} unavailable){suffix}")

    def _on_write_basics_clicked(self):
        self.lbl_basics_status.setText("Writing to ECU RAM...")
        asyncio.ensure_future(self._write_basics())

    async def _write_basics(self):
        total = len(self._field_widgets)
        written = 0
        missing = 0
        missing_names: List[str] = []

        for canonical, widget in self._field_widgets.items():
            name = self._resolved_fields.get(canonical)
            if not name:
                missing += 1
                missing_names.append(self._field_display_names.get(canonical, canonical))
                continue
            ok = await self.api.write_parameter(name, float(widget.value()))
            if ok:
                written += 1

        suffix = ""
        if missing_names:
            suffix = f" Missing: {', '.join(missing_names)}."
        self.lbl_basics_status.setText(
            f"Wrote {written}/{total} settings ({missing} unavailable).{suffix} Burn to keep after reboot."
        )
