from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .table_editor import TableEditor


class _BaseTunerDialog(QDialog):
    def __init__(self, api, name: str, meta: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.api = api
        self.name = name
        self.meta = dict(meta or {})

        self.setWindowTitle(f"{name} - Honda Editor")
        self.resize(980, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        title = QLabel(name)
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #FF6600;")
        root.addWidget(title)

        caution = QLabel("Caution: Verify timing and fueling before road load.")
        caution.setStyleSheet("background:#912626; color:#FFF; padding:4px 8px;")
        root.addWidget(caution)

        note = QLabel("Tip: Use a timing light and verify injector data before final burn.")
        note.setStyleSheet("background:#143A7B; color:#EAF2FF; padding:4px 8px;")
        root.addWidget(note)

        self.split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(self.split, 1)

        self.left = QWidget()
        self.left_layout = QVBoxLayout(self.left)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(8)

        self.right = QFrame()
        self.right.setObjectName("MenuDetailCard")
        self.right_layout = QVBoxLayout(self.right)
        self.right_layout.setContentsMargins(12, 10, 12, 10)
        self.right_layout.setSpacing(8)

        self.lbl_context = QLabel("")
        self.lbl_context.setWordWrap(True)
        self.right_layout.addWidget(self.lbl_context)
        self.right_layout.addStretch()

        self.split.addWidget(self.left)
        self.split.addWidget(self.right)
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)

        row = QHBoxLayout()
        row.addStretch()
        self.btn_write = QPushButton("Write to RAM")
        self.btn_write.setObjectName("PrimaryButton")
        row.addWidget(self.btn_write)

        self.btn_burn = QPushButton("Burn")
        self.btn_burn.clicked.connect(self._on_burn)
        row.addWidget(self.btn_burn)

        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        row.addWidget(self.btn_close)

        root.addLayout(row)

    async def _write_impl(self):
        raise NotImplementedError

    def _on_write(self):
        async def run():
            try:
                ok = await self._write_impl()
                if ok:
                    QMessageBox.information(self, "Write", f"{self.name} written to ECU RAM")
                else:
                    QMessageBox.warning(self, "Write", f"Write failed for {self.name}")
            except Exception as e:
                QMessageBox.critical(self, "Write Error", str(e))

        asyncio.ensure_future(run())

    def _on_burn(self):
        async def run():
            try:
                ok = await self.api.burn()
                if ok:
                    QMessageBox.information(self, "Burn", "Burn successful")
                else:
                    QMessageBox.warning(self, "Burn", "Burn failed")
            except Exception as e:
                QMessageBox.critical(self, "Burn Error", str(e))

        asyncio.ensure_future(run())


class GenericParameterDialog(_BaseTunerDialog):
    def __init__(self, api, name: str, value: Any, meta: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(api, name, meta, parent)
        self.value = value
        self.kind = "table" if isinstance(value, list) else "scalar"

        if self.kind == "table":
            self.table_editor = TableEditor()
            self.table_editor.load_table(self._coerce_table_data(value))
            self.left_layout.addWidget(self.table_editor, 1)
        else:
            form = QFormLayout()
            self.scalar_edit = QLineEdit(str(value if value is not None else 0))
            form.addRow("Value", self.scalar_edit)
            form.addRow("Units", QLabel(str(self.meta.get("units", "-"))))
            form.addRow("Range", QLabel(self._range_text()))
            card = QFrame()
            card.setLayout(form)
            self.left_layout.addWidget(card)
            self.left_layout.addStretch()

        self.lbl_context.setText(self._context_text())
        self.btn_write.clicked.connect(self._on_write)

    def _range_text(self) -> str:
        lo = self.meta.get("min", "-")
        hi = self.meta.get("max", "-")
        return f"{lo} .. {hi}"

    def _context_text(self) -> str:
        return (
            f"Type: {self.kind}\n"
            f"Category: {self.meta.get('category', '-')}\n"
            f"Units: {self.meta.get('units', '-')}\n"
            f"Range: {self._range_text()}"
        )

    @staticmethod
    def _coerce_table_data(value: Any) -> List[List[float]]:
        if not isinstance(value, list):
            return [[0.0] * 8 for _ in range(8)]
        if value and isinstance(value[0], list):
            return value
        if not value:
            return [[0.0] * 8 for _ in range(8)]

        n = len(value)
        side = int(n ** 0.5)
        cols = side if side * side == n else (16 if n % 16 == 0 else 8 if n % 8 == 0 else n)
        rows = max(1, n // cols)
        out = []
        for r in range(rows):
            start = r * cols
            out.append([float(v) for v in value[start : start + cols]])
        return out

    async def _write_impl(self):
        if self.kind == "table":
            return await self.api.write_parameter(self.name, self.table_editor.get_table_data())
        try:
            val = float(self.scalar_edit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Validation", "Value must be numeric")
            return False
        return await self.api.write_parameter(self.name, val)


class InjectorDeadTimeDialog(_BaseTunerDialog):
    def __init__(self, api, name: str, value: Any, meta: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(api, name, meta, parent)

        form = QFormLayout()
        self.scalar_deadtime = QLineEdit(str(value if value is not None else 0.85))
        form.addRow("Base Dead Time (ms)", self.scalar_deadtime)

        card = QFrame()
        card.setLayout(form)
        self.left_layout.addWidget(card)

        self.table = TableEditor()
        # Battery voltage correction style helper table
        self.table.load_table(
            [
                [1.18, 1.05, 0.95, 0.88, 0.82, 0.78],
                [1.26, 1.12, 1.00, 0.92, 0.86, 0.80],
                [1.34, 1.18, 1.06, 0.98, 0.90, 0.84],
                [1.42, 1.25, 1.12, 1.02, 0.94, 0.88],
            ]
        )
        self.left_layout.addWidget(self.table, 1)

        self.lbl_context.setText(
            "Injector dead-time helper table\n"
            "X-axis: Battery Voltage\n"
            "Y-axis: Fuel pressure bucket\n"
            "Tune with logs and wideband feedback."
        )
        self.btn_write.clicked.connect(self._on_write)

    async def _write_impl(self):
        try:
            val = float(self.scalar_deadtime.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Validation", "Dead time must be numeric")
            return False

        ok = await self.api.write_parameter("injectorDeadTime", val)
        # optional table write if backend exposes a table name
        await self.api.write_parameter("injectorDeadTimeBatteryTable", self.table.get_table_data())
        return ok


class VtecAdvancedDialog(_BaseTunerDialog):
    def __init__(self, api, name: str, value: Any, meta: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(api, name, meta, parent)

        form = QFormLayout()
        self.chk_gear = QCheckBox("Enable gear-based VTEC")
        self.chk_speed = QCheckBox("Enable speed-based VTEC")
        self.chk_tps = QCheckBox("Enable TPS gating")
        self.chk_rpm = QCheckBox("Enable RPM window")

        self.rpm_on = QSpinBox(); self.rpm_on.setRange(2000, 10000); self.rpm_on.setValue(5500)
        self.rpm_off = QSpinBox(); self.rpm_off.setRange(1500, 9800); self.rpm_off.setValue(5200)
        self.tps_min = QSpinBox(); self.tps_min.setRange(0, 100); self.tps_min.setValue(30)
        self.speed_min = QSpinBox(); self.speed_min.setRange(0, 300); self.speed_min.setValue(20)
        self.gear_min = QSpinBox(); self.gear_min.setRange(1, 6); self.gear_min.setValue(2)

        form.addRow(self.chk_gear)
        form.addRow(self.chk_speed)
        form.addRow(self.chk_tps)
        form.addRow(self.chk_rpm)
        form.addRow("VTEC On RPM", self.rpm_on)
        form.addRow("VTEC Off RPM", self.rpm_off)
        form.addRow("Min TPS %", self.tps_min)
        form.addRow("Min Speed (kph)", self.speed_min)
        form.addRow("Min Gear", self.gear_min)

        host = QFrame(); host.setLayout(form)
        self.left_layout.addWidget(host)
        self.left_layout.addStretch()

        self.lbl_context.setText(
            "Advanced Honda VTEC window\n"
            "Use hysteresis (On > Off RPM) to prevent VTEC chatter.\n"
            "Validate engagement with datalog playback."
        )

        self.btn_write.clicked.connect(self._on_write)

    async def _write_impl(self):
        writes = {
            "vtecByGearEnabled": 1 if self.chk_gear.isChecked() else 0,
            "vtecBySpeedEnabled": 1 if self.chk_speed.isChecked() else 0,
            "vtecByTpsEnabled": 1 if self.chk_tps.isChecked() else 0,
            "vtecByRpmEnabled": 1 if self.chk_rpm.isChecked() else 0,
            "vtecEngagementRPM": self.rpm_on.value(),
            "vtecDisengagementRPM": self.rpm_off.value(),
            "vtecEngagementTPS": self.tps_min.value(),
            "vtecEngagementSpeed": self.speed_min.value(),
            "vtecMinGear": self.gear_min.value(),
        }
        ok = True
        for key, val in writes.items():
            ok = bool(await self.api.write_parameter(key, val)) and ok
        return ok


class CopConfigDialog(_BaseTunerDialog):
    def __init__(self, api, name: str, value: Any, meta: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(api, name, meta, parent)

        self.chk_enable = QCheckBox("Enable Coil on Plug Mode")
        self.chk_enable.setChecked(True)
        self.left_layout.addWidget(self.chk_enable)

        grid = QGridLayout()
        self.output_boxes: Dict[int, QComboBox] = {}
        output_options = [f"IGN{n}" for n in range(1, 13)] + ["Disabled"]

        for cyl in range(1, 13):
            lbl = QLabel(f"Cylinder {cyl}")
            cmb = QComboBox()
            cmb.addItems(output_options)
            cmb.setCurrentIndex(cyl - 1)
            self.output_boxes[cyl] = cmb
            r = (cyl - 1) // 2
            c = ((cyl - 1) % 2) * 2
            grid.addWidget(lbl, r, c)
            grid.addWidget(cmb, r, c + 1)

        holder = QFrame(); holder.setLayout(grid)
        self.left_layout.addWidget(holder, 1)

        form = QFormLayout()
        self.spark_latency = QLineEdit("0.08")
        self.fixed_timing_mode = QCheckBox("Fixed Timing Mode (for timing light)")
        self.fixed_timing_deg = QSpinBox(); self.fixed_timing_deg.setRange(0, 40); self.fixed_timing_deg.setValue(16)
        self.per_coil_dwell = QLineEdit("2.5")

        form.addRow("Spark Hardware Latency (ms)", self.spark_latency)
        form.addRow(self.fixed_timing_mode)
        form.addRow("Fixed Timing (deg)", self.fixed_timing_deg)
        form.addRow("Per-Coil Dwell Base (ms)", self.per_coil_dwell)

        cfg = QFrame(); cfg.setLayout(form)
        self.left_layout.addWidget(cfg)

        self.lbl_context.setText(
            "COP setup for Honda OBD1 conversions\n"
            "1) Set fixed timing\n"
            "2) Verify crank timing with light\n"
            "3) Disable fixed timing after sync verification"
        )

        self.btn_write.clicked.connect(self._on_write)

    async def _write_impl(self):
        ok = await self.api.write_parameter("coilOnPlugMode", 1 if self.chk_enable.isChecked() else 0)

        for cyl, combo in self.output_boxes.items():
            out_name = combo.currentText()
            ok = bool(await self.api.write_parameter(f"ignitionOutput{cyl}", out_name)) and ok

        try:
            latency = float(self.spark_latency.text().strip())
            dwell = float(self.per_coil_dwell.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Validation", "Latency and dwell must be numeric")
            return False

        ok = bool(await self.api.write_parameter("sparkHardwareLatency", latency)) and ok
        ok = bool(await self.api.write_parameter("perCoilDwellBase", dwell)) and ok
        ok = bool(await self.api.write_parameter("fixedTimingMode", 1 if self.fixed_timing_mode.isChecked() else 0)) and ok
        ok = bool(await self.api.write_parameter("fixedTimingDeg", self.fixed_timing_deg.value())) and ok
        return ok


class ParameterEditorDialog(GenericParameterDialog):
    """Compatibility class; routes to generic if directly instantiated."""


def create_parameter_dialog(api, name: str, value: Any, meta: Optional[Dict[str, Any]] = None, parent=None) -> QDialog:
    lname = (name or "").lower()

    if "injectordeadtime" in lname:
        return InjectorDeadTimeDialog(api, name, value, meta=meta, parent=parent)

    if any(token in lname for token in ("vtecwindowadvanced", "advanced vtec", "vtec engagement")):
        return VtecAdvancedDialog(api, name, value, meta=meta, parent=parent)

    if any(token in lname for token in ("coilonplug", "ignitionoutput", "percoildwell", "sparkhardwarelatency", "fixedtimingmode")):
        return CopConfigDialog(api, name, value, meta=meta, parent=parent)

    return GenericParameterDialog(api, name, value, meta=meta, parent=parent)
