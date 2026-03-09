from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, Dict, List

import qasync
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QStyle,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .ui.api_client import RusefiApiClient
from .ui.components.ribbon_bar import RibbonBar
from .ui.tabs.tab_autotune import AutoTuneTab
from .ui.tabs.tab_dashboard import DashboardTab
from .ui.tabs.tab_datalog import DatalogTab
from .ui.tabs.tab_firmware import FirmwareTab
from .ui.tabs.tab_pinout import PinoutTab
from .ui.tabs.tab_quick_setup import QuickSetupTab
from .ui.tabs.tab_tables import TablesTab
from .ui.tabs.tab_tuning import TuningTab
from .ui.theme import COLOR_ACCENT, COLOR_BORDER, COLOR_SURFACE, STYLESHEET


logger = logging.getLogger("BaseTuneArchitect")
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


TAB_STYLE = f"""
QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    background-color: transparent;
}}
QTabBar::tab {{
    background-color: {COLOR_SURFACE};
    color: #909090;
    padding: 8px 18px;
    border: 1px solid {COLOR_BORDER};
    border-bottom: none;
    margin-right: 2px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    background-color: #121212;
    color: {COLOR_ACCENT};
    border-bottom: 2px solid {COLOR_ACCENT};
    font-weight: 700;
}}
"""


_LOCAL_PRESETS = [
    {
        "id": "local:uaefi_honda_obd1_quick_base",
        "name": "uaEFI Honda OBD1 Quick Base Tune",
        "board": "uaEFI Honda OBD1",
        "engine_focus": "B-series / D-series / LS-VTEC ready",
        "safety_notes": [
            "Verify base timing with a timing light before revving above idle.",
            "Set injectorFlow to your real injector size before final tune.",
            "Verify trigger angle and TDC sync before road testing.",
        ],
        "warnings": [
            "Conservative startup values only. Final fueling and timing are still required.",
            "Confirm fan outputs and coolant sensor calibration before long idle sessions.",
        ],
        "values": {
            "injectorFlow": 240.0,
            "injectorDeadTime": 0.85,
            "triggerType": 4,
            "triggerAngle": 80.0,
            "rpmHardLimit": 8500.0,
            "revLimiterFuelCut": 1.0,
            "vtecEngagementRPM": 5500.0,
            "idleRpmTarget": 900.0,
            "fuelStrategy": 0.0,
            "globalFuelTrim": 0.0,
            "boostCutPressure": 300.0,
            "fanOnTemperature": 92.0,
            "fanOffTemperature": 88.0,
            "sparkDwell": 2.4,
            "knockRetard": 5.0,
            "accelerationEnrichment": 6.0,
            "wallWettingCoefficient": 0.5,
            "lambda1SensorOffset": 0.0,
        },
    },
    {
        "id": "local:ls_vtec_quick_base",
        "name": "LS VTEC Quick Base Tune",
        "board": "uaEFI Honda OBD1",
        "engine_focus": "B-series LS VTEC",
        "safety_notes": [
            "Verify base ignition timing with a timing light before driving.",
            "Set injectorFlow to your exact injector size.",
            "Confirm VTEC oil pressure and solenoid wiring.",
        ],
        "warnings": [
            "Startup values are conservative and may require warmup tuning.",
            "Do not run high boost without knock monitoring.",
        ],
        "values": {
            "injectorFlow": 440.0,
            "injectorDeadTime": 0.85,
            "triggerType": 4,
            "triggerAngle": 80.0,
            "rpmHardLimit": 8500.0,
            "revLimiterFuelCut": 1.0,
            "vtecEngagementRPM": 5400.0,
            "idleRpmTarget": 900.0,
            "globalFuelTrim": 0.0,
            "boostCutPressure": 300.0,
            "fanOnTemperature": 92.0,
            "fanOffTemperature": 88.0,
            "sparkDwell": 2.5,
            "knockRetard": 6.0,
            "accelerationEnrichment": 8.0,
            "wallWettingCoefficient": 0.5,
            "lambda1SensorOffset": 0.0,
        },
    }
]


class PresetLoadDialog(QDialog):
    def __init__(self, presets: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.presets = list(presets or [])
        self.setWindowTitle("Load Honda Preset")
        self.resize(640, 460)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.cmb_preset = QComboBox()
        for p in self.presets:
            label = f"{p.get('name', 'Preset')}  [{p.get('board', 'Board')}]"
            self.cmb_preset.addItem(label, p.get("id"))
        form.addRow("Preset", self.cmb_preset)

        self.inj_override = QLineEdit()
        self.inj_override.setPlaceholderText("Optional injectorFlow override (cc/min)")
        form.addRow("Injector Override", self.inj_override)

        self.chk_burn = QCheckBox("Burn after apply")
        form.addRow("", self.chk_burn)

        layout.addLayout(form)

        layout.addWidget(QLabel("Safety Notes / Warnings"))
        self.notes = QPlainTextEdit()
        self.notes.setReadOnly(True)
        layout.addWidget(self.notes, 1)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.cmb_preset.currentIndexChanged.connect(self._refresh_notes)
        self._set_default_honda()
        self._refresh_notes()

    def _set_default_honda(self):
        for i, p in enumerate(self.presets):
            text = (p.get("name", "") + " " + p.get("board", "") + " " + p.get("engine_focus", "")).lower()
            if "honda" in text and "obd1" in text:
                self.cmb_preset.setCurrentIndex(i)
                return

    def _refresh_notes(self):
        idx = self.cmb_preset.currentIndex()
        if idx < 0 or idx >= len(self.presets):
            self.notes.setPlainText("")
            return

        p = self.presets[idx]
        lines = [
            f"Name: {p.get('name', '-')}",
            f"Board: {p.get('board', '-')}",
            f"Engine Focus: {p.get('engine_focus', '-')}",
            "",
            "Safety Notes:",
        ]
        for n in p.get("safety_notes", []):
            lines.append(f"- {n}")
        lines.append("")
        lines.append("Warnings:")
        for w in p.get("warnings", []):
            lines.append(f"- {w}")

        self.notes.setPlainText("\n".join(lines))

    def selection(self) -> Dict[str, Any]:
        idx = self.cmb_preset.currentIndex()
        if idx < 0 or idx >= len(self.presets):
            return {}
        preset = self.presets[idx]

        overrides: Dict[str, Any] = {}
        raw = self.inj_override.text().strip()
        if raw:
            try:
                overrides["injectorFlow"] = float(raw)
            except ValueError:
                pass

        return {
            "preset_id": preset.get("id"),
            "preset_name": preset.get("name"),
            "burn_after": bool(self.chk_burn.isChecked()),
            "overrides": overrides,
            "preset_obj": preset,
        }


class BaseTuneMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("MASTER HONDA TUNER - uaEFI / OBD1")
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMenuButton))
        self.resize(1460, 930)

        self.api = RusefiApiClient()
        self._connected = False
        self._live_poll_inflight = False
        self._params_load_inflight = False
        self._datalog_recording = False
        self._connect_inflight = False

        self._build_ui()
        self._apply_theme()
        self._wire_signals()
        self._setup_shortcuts()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_live_data)
        self.timer.start(50)

        QTimer.singleShot(300, self.load_parameters)

    # ------------------------------------------------------------------ Build UI
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        self.ribbon = RibbonBar(self)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.ribbon)

        self._setup_menu_bar()

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(TAB_STYLE)

        self.tab_quick_setup = QuickSetupTab(self.api)
        self.tab_tuning = TuningTab(self.api)
        self.tab_tables = TablesTab(self.api)
        self.tab_dashboard = DashboardTab(self.api)
        self.tab_datalog = DatalogTab(self.api)
        self.tab_autotune = AutoTuneTab(self.api)
        self.tab_firmware = FirmwareTab(self.api)
        self.tab_pinout = PinoutTab(self.api)

        self.tabs.addTab(self.tab_quick_setup, "Quick Setup")
        self.tabs.addTab(self.tab_tuning, "Tuning Workspace")
        self.tabs.addTab(self.tab_tables, "Map Tables")
        self.tabs.addTab(self.tab_dashboard, "Live Dashboard")
        self.tabs.addTab(self.tab_datalog, "Datalog Recorder")
        self.tabs.addTab(self.tab_autotune, "Auto-Tune Tools")
        self.tabs.addTab(self.tab_pinout, "Pinout")
        self.tabs.addTab(self.tab_firmware, "Firmware & SD Card")
        self.tabs.setCurrentIndex(0)

        root.addWidget(self.tabs)

        self.statusBar().showMessage("Ready - Backend: Disconnected")

    def _setup_menu_bar(self):
        menu = self.menuBar()

        ecu_menu = menu.addMenu("ECU")
        act_connect = QAction("Connect ECU", self)
        act_connect.triggered.connect(self.on_connect_clicked)
        ecu_menu.addAction(act_connect)

        act_burn = QAction("Burn All Changes", self)
        act_burn.triggered.connect(self.on_burn_clicked)
        ecu_menu.addAction(act_burn)

        act_preset = QAction("Load Preset", self)
        act_preset.triggered.connect(self.on_load_preset_clicked)
        ecu_menu.addAction(act_preset)

        file_menu = menu.addMenu("File")
        act_load = QAction("Load .msq", self)
        act_load.triggered.connect(self.on_load_msq)
        file_menu.addAction(act_load)

        act_save = QAction("Save .msq", self)
        act_save.triggered.connect(self.on_save_msq)
        file_menu.addAction(act_save)

    def _wire_signals(self):
        self.ribbon.connect_clicked.connect(self.on_connect_clicked)
        self.ribbon.burn_clicked.connect(self.on_burn_clicked)
        self.ribbon.load_clicked.connect(self.on_load_msq)
        self.ribbon.save_clicked.connect(self.on_save_msq)
        self.ribbon.preset_clicked.connect(self.on_load_preset_clicked)

        self.ribbon.datalog_clicked.connect(self.on_start_datalog_clicked)
        self.ribbon.firmware_clicked.connect(lambda: self.tabs.setCurrentWidget(self.tab_firmware))
        self.ribbon.ai_chat_toggled.connect(self.on_ai_chat_toggled)
        self.ribbon.fuel_map_selected.connect(lambda idx: self.tab_tuning.apply_map_switch(fuel_map=idx))
        self.ribbon.ign_map_selected.connect(lambda idx: self.tab_tuning.apply_map_switch(ign_map=idx))

        self.tab_quick_setup.connect_requested.connect(self.on_connect_clicked)
        self.tab_quick_setup.burn_requested.connect(self.on_burn_clicked)
        self.tab_quick_setup.load_preset_requested.connect(self.on_load_preset_clicked)
        self.tab_quick_setup.load_msq_requested.connect(self.on_load_msq)
        self.tab_quick_setup.save_msq_requested.connect(self.on_save_msq)
        self.tab_quick_setup.datalog_toggle_requested.connect(self.on_start_datalog_clicked)
        self.tab_quick_setup.open_tuning_parameter.connect(self.on_quick_open_parameter)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.on_burn_clicked)
        QShortcut(QKeySequence("Space"), self, activated=self.on_start_datalog_clicked)

    def _apply_theme(self):
        self.setStyleSheet(STYLESHEET)

    # ------------------------------------------------------------------ Presets
    def _merge_presets(self, presets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = list(presets or [])
        existing_ids = {p.get("id") for p in out}
        existing_names = {(p.get("name") or "").lower() for p in out}

        for lp in _LOCAL_PRESETS:
            if lp["id"] not in existing_ids and lp["name"].lower() not in existing_names:
                out.append(lp)

        # Ensure these two are prominent if available.
        out.sort(key=lambda p: (0 if "honda obd1" in (p.get("name", "").lower() + " " + p.get("board", "").lower()) else 1,
                                0 if "ls vtec" in p.get("name", "").lower() else 1,
                                p.get("name", "")))
        return out

    async def _apply_local_preset(self, preset: Dict[str, Any], overrides: Dict[str, Any], burn_after: bool) -> Dict[str, Any]:
        values = dict(preset.get("values") or {})
        values.update(overrides or {})

        changed = []
        errors = []
        for name, value in values.items():
            before = None
            read = await self.api.read_parameter(name)
            if read:
                before = read.get("value")
            ok = await self.api.write_parameter(name, value)
            if ok:
                changed.append({"parameter": name, "before": before, "after": value})
            else:
                errors.append({"parameter": name, "reason": "write_failed"})

        if burn_after:
            await self.api.burn()

        return {
            "status": "ok",
            "preset_name": preset.get("name"),
            "changed": changed,
            "skipped": [],
            "errors": errors,
            "warnings": preset.get("warnings", []),
            "safety_notes": preset.get("safety_notes", []),
        }

    # ------------------------------------------------------------------ Slots
    def on_connect_clicked(self):
        if self._connect_inflight:
            return
        self._connect_inflight = True
        self.statusBar().showMessage("Connecting to ECU (COM5 -> COM6 -> auto)...")
        self.ribbon.btn_connect.setEnabled(False)

        async def do_connect():
            try:
                success = await self.api.connect("COM5")
                if success:
                    live = await self.api.get_live_data()
                    port = live.get("port", "Unknown Port")
                    mode = "Binary" if not live.get("console_mode") else "Console"
                    self.statusBar().showMessage(f"Connected to rusEFI on {port} ({mode})")
                    self._connected = True
                    self.load_parameters()
                else:
                    err = self.api.last_connect_error or "Unknown connection error."
                    self.statusBar().showMessage(f"Connection failed: {err}")
            except Exception as e:
                self.statusBar().showMessage(f"Connection error: {e}")
            finally:
                self._connect_inflight = False
                self.ribbon.btn_connect.setEnabled(True)

        asyncio.ensure_future(do_connect())

    def on_burn_clicked(self):
        async def do_burn():
            success = await self.api.burn()
            self.statusBar().showMessage("Burn successful" if success else "Burn failed")

        asyncio.ensure_future(do_burn())

    def on_load_msq(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load MSQ Tune File", "", "MSQ Files (*.msq);;All Files (*)")
        if not path:
            return

        async def do_load():
            try:
                with open(path, "rb") as f:
                    data = f.read()
                result = await self.api.import_msq(data)
                self.statusBar().showMessage(
                    f"MSQ loaded: {result.get('applied', 0)}/{result.get('total', 0)} parameters"
                )
                self.load_parameters()
            except Exception as e:
                self.statusBar().showMessage(f"MSQ load error: {e}")

        asyncio.ensure_future(do_load())

    def on_save_msq(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save MSQ Tune File", "tune.msq", "MSQ Files (*.msq);;All Files (*)")
        if not path:
            return

        async def do_save():
            try:
                data = await self.api.export_msq()
                with open(path, "wb") as f:
                    f.write(data)
                self.statusBar().showMessage(f"MSQ saved: {path}")
            except Exception as e:
                self.statusBar().showMessage(f"MSQ save error: {e}")

        asyncio.ensure_future(do_save())

    def on_start_datalog_clicked(self):
        async def toggle():
            if not self._datalog_recording:
                await self.api.datalog_start()
                self._datalog_recording = True
                self.ribbon.btn_datalog.setText("Stop Log")
                self.tab_quick_setup.set_datalog_recording(True)
                self.tabs.setCurrentWidget(self.tab_datalog)
                self.statusBar().showMessage("Datalog started")
            else:
                await self.api.datalog_stop()
                self._datalog_recording = False
                self.ribbon.btn_datalog.setText("Start Log")
                self.tab_quick_setup.set_datalog_recording(False)
                self.statusBar().showMessage("Datalog stopped")

        asyncio.ensure_future(toggle())

    def on_quick_open_parameter(self, name: str):
        if not name:
            return
        self.tabs.setCurrentWidget(self.tab_tuning)
        self.tab_tuning.select_parameter(name)

    def on_ai_chat_toggled(self, enabled: bool):
        self.statusBar().showMessage("AI Chat enabled" if enabled else "AI Chat disabled")

    def on_load_preset_clicked(self):
        async def fetch_presets():
            backend_presets = await self.api.get_presets()
            presets = self._merge_presets(backend_presets)
            QTimer.singleShot(0, lambda p=presets: self._open_preset_dialog(p))

        asyncio.ensure_future(fetch_presets())

    def _open_preset_dialog(self, presets: List[Dict[str, Any]]):
        if not presets:
            self.timer.stop()
            try:
                QMessageBox.warning(self, "Presets", "No presets available.")
            finally:
                self.timer.start(50)
            return

        dlg = PresetLoadDialog(presets, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected = dlg.selection()
        preset_id = selected.get("preset_id")
        if not preset_id:
            return

        self.statusBar().showMessage(f"Applying preset: {selected.get('preset_name')}...")
        asyncio.ensure_future(self._apply_selected_preset(selected))

    async def _apply_selected_preset(self, selected: Dict[str, Any]):
        preset_id = selected.get("preset_id")
        if str(preset_id).startswith("local:"):
            result = await self._apply_local_preset(
                selected.get("preset_obj") or {},
                selected.get("overrides") or {},
                bool(selected.get("burn_after", False)),
            )
        else:
            result = await self.api.apply_preset(
                preset_name=str(preset_id),
                burn_after=bool(selected.get("burn_after", False)),
                overrides=selected.get("overrides") or None,
            )

        if result.get("status") == "error":
            self.timer.stop()
            try:
                QMessageBox.critical(self, "Preset Apply", str(result.get("detail", "Preset apply failed.")))
            finally:
                self.timer.start(50)
            return

        changed = result.get("changed", []) or []
        changed_names = [c.get("parameter") for c in changed if c.get("parameter")]

        self.load_parameters()
        QTimer.singleShot(700, lambda names=changed_names: self.tab_tuning.mark_preset_changes(names))

        lines = [
            f"Preset: {result.get('preset_name', selected.get('preset_name'))}",
            f"Applied: {len(changed)} parameter(s)",
            f"Errors: {len(result.get('errors', []) or [])}",
            "",
            "Safety Warnings:",
        ]
        for note in result.get("safety_notes", []):
            lines.append(f"- {note}")
        for warn in result.get("warnings", []):
            lines.append(f"- {warn}")

        if changed:
            lines.append("")
            lines.append("Changed Parameters:")
            for c in changed[:45]:
                lines.append(f"- {c.get('parameter')}: {c.get('before')} -> {c.get('after')}")
            if len(changed) > 45:
                lines.append(f"- ... and {len(changed) - 45} more")

        self.timer.stop()
        try:
            QMessageBox.information(self, "Preset Applied", "\n".join(lines))
        finally:
            self.timer.start(50)
        self.statusBar().showMessage(f"Preset applied: {result.get('preset_name', selected.get('preset_name'))}")

    def load_parameters(self):
        if self._params_load_inflight:
            return
        self._params_load_inflight = True

        async def fetch():
            try:
                params = await self.api.get_parameters()
                if params:
                    self.tab_quick_setup.load_parameters(params)
                    self.tab_tuning.load_parameters(params)
                    self.statusBar().showMessage(f"Loaded {len(params)} tuning parameters")
            finally:
                self._params_load_inflight = False

        asyncio.ensure_future(fetch())

    def update_live_data(self):
        if self._live_poll_inflight or self._connect_inflight:
            return
        self._live_poll_inflight = True

        async def fetch():
            try:
                data = await self.api.get_live_data()
                if data:
                    self.tab_quick_setup.update_live_data(data)
                    self.tab_dashboard.update_data(data)
                    self.tab_tuning.update_live_data(data)

                    live_connected = bool(data.get("connected", False))
                    if live_connected and not self._connected:
                        port = data.get("port", "Unknown Port")
                        mode = "Binary" if not data.get("console_mode") else "Console"
                        self.statusBar().showMessage(f"Connected to rusEFI on {port} ({mode})")
                        self._connected = True
                    elif not live_connected and self._connected:
                        self.statusBar().showMessage("Ready - Backend: Disconnected")
                        self._connected = False
            finally:
                self._live_poll_inflight = False

        asyncio.ensure_future(fetch())

    def closeEvent(self, event):
        self.timer.stop()
        asyncio.ensure_future(self.api.close())
        super().closeEvent(event)


# Entry

def main():
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = BaseTuneMainWindow()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
