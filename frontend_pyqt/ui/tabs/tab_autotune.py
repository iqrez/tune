"""
Tab 5: Auto-Tune Tools
VE Autotune, Ignition Autotune, Virtual Dyno, AFR Target tools.
Uses backend endpoints: /autotune/preview, /autotune/run, /dyno/estimate
"""
import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QGridLayout, QTextEdit, QProgressBar,
    QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox,
)
from PyQt6.QtCore import Qt

from ..theme import COLOR_ACCENT


class AutoTuneTab(QWidget):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        lbl = QLabel("Auto-Tune Tools")
        lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLOR_ACCENT};")
        layout.addWidget(lbl)

        # Row of tool cards
        cards = QHBoxLayout()

        # 1. VE Autotune
        ve_box = QGroupBox("VE Autotune")
        ve_lay = QVBoxLayout(ve_box)
        ve_lay.addWidget(QLabel("Automatically adjusts VE table cells\nbased on wideband AFR feedback."))
        self.ve_target = QDoubleSpinBox()
        self.ve_target.setRange(0.7, 1.1)
        self.ve_target.setValue(1.0)
        self.ve_target.setSingleStep(0.01)
        self.ve_target.setPrefix("Target Lambda: ")
        ve_lay.addWidget(self.ve_target)
        self.ve_correction = QDoubleSpinBox()
        self.ve_correction.setRange(1, 50)
        self.ve_correction.setValue(10)
        self.ve_correction.setSuffix("% max correction")
        ve_lay.addWidget(self.ve_correction)
        self.btn_ve_start = QPushButton("Start VE Autotune")
        self.btn_ve_start.setObjectName("PrimaryButton")
        self.btn_ve_start.clicked.connect(self._start_ve_autotune)
        ve_lay.addWidget(self.btn_ve_start)
        self.ve_progress = QProgressBar()
        self.ve_progress.setValue(0)
        ve_lay.addWidget(self.ve_progress)
        ve_lay.addStretch()
        cards.addWidget(ve_box)

        # 2. Ignition Autotune
        ign_box = QGroupBox("Ignition Autotune")
        ign_lay = QVBoxLayout(ign_box)
        ign_lay.addWidget(QLabel("Optimizes ignition timing based on\nknock sensor and MBT analysis."))
        self.ign_retard = QDoubleSpinBox()
        self.ign_retard.setRange(0.5, 5.0)
        self.ign_retard.setValue(1.0)
        self.ign_retard.setSuffix("\u00b0 retard on knock")
        ign_lay.addWidget(self.ign_retard)
        self.btn_ign_start = QPushButton("Start Ign Autotune")
        self.btn_ign_start.setObjectName("PrimaryButton")
        self.btn_ign_start.clicked.connect(self._start_ign_autotune)
        ign_lay.addWidget(self.btn_ign_start)
        self.ign_progress = QProgressBar()
        self.ign_progress.setValue(0)
        ign_lay.addWidget(self.ign_progress)
        ign_lay.addStretch()
        cards.addWidget(ign_box)

        # 3. Virtual Dyno
        dyno_box = QGroupBox("Virtual Dyno")
        dyno_lay = QVBoxLayout(dyno_box)
        dyno_lay.addWidget(QLabel("Estimates power/torque from\nacceleration data and vehicle mass."))
        self.dyno_mass = QSpinBox()
        self.dyno_mass.setRange(500, 5000)
        self.dyno_mass.setValue(1400)
        self.dyno_mass.setSuffix(" kg")
        self.dyno_mass.setPrefix("Vehicle Mass: ")
        dyno_lay.addWidget(self.dyno_mass)
        self.btn_dyno = QPushButton("Run Virtual Dyno")
        self.btn_dyno.setObjectName("PrimaryButton")
        self.btn_dyno.clicked.connect(self._run_dyno)
        dyno_lay.addWidget(self.btn_dyno)
        dyno_lay.addStretch()
        cards.addWidget(dyno_box)

        layout.addLayout(cards)

        # Log output
        log_box = QGroupBox("Autotune Log")
        log_lay = QVBoxLayout(log_box)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Autotune output will appear here...")
        log_lay.addWidget(self.log_output)
        layout.addWidget(log_box)

    def _log(self, msg):
        self.log_output.append(msg)

    def _start_ve_autotune(self):
        target = self.ve_target.value()
        max_corr = self.ve_correction.value()
        self._log(f"VE Autotune started: target={target}, max_correction={max_corr}%")
        self.ve_progress.setValue(0)

        async def run():
            try:
                # Use /autotune/preview first, then /autotune/run
                result = await self.api.autotune_preview(
                    tool_name="ve",
                    target_lambda=target,
                    max_correction_pct=max_corr,
                )
                changes = result.get("changes", [])
                warnings = result.get("guardrail_warnings", [])
                self._log(f"Preview: {len(changes)} cell changes, {len(warnings)} warnings")
                for w in warnings:
                    self._log(f"  Warning: {w}")
                self.ve_progress.setValue(30)

                # Run the autotune
                result = await self.api.autotune_run(
                    tool_name="ve",
                    target_lambda=target,
                    max_correction_pct=max_corr,
                )
                if "error" in result:
                    self._log(f"VE Autotune error: {result['error']}")
                else:
                    self._log(f"VE Autotune complete: {result}")
                    self.ve_progress.setValue(100)
            except Exception as e:
                self._log(f"Error: {e}")
        asyncio.ensure_future(run())

    def _start_ign_autotune(self):
        retard = self.ign_retard.value()
        self._log(f"Ignition Autotune started: retard_on_knock={retard}\u00b0")
        self.ign_progress.setValue(0)

        async def run():
            try:
                result = await self.api.autotune_run(
                    tool_name="ignition",
                    retard_degrees=retard,
                )
                if "error" in result:
                    self._log(f"Ignition Autotune error: {result['error']}")
                else:
                    self._log(f"Ignition Autotune complete: {result}")
                    self.ign_progress.setValue(100)
            except Exception as e:
                self._log(f"Error: {e}")
        asyncio.ensure_future(run())

    def _run_dyno(self):
        mass = self.dyno_mass.value()
        self._log(f"Virtual Dyno: vehicle_mass={mass}kg")

        async def run():
            try:
                result = await self.api.dyno_estimate(mass)
                if result:
                    hp = result.get("peak_hp", "?")
                    tq = result.get("peak_torque", "?")
                    self._log(f"Estimated: {hp} HP / {tq} Nm")
                else:
                    self._log("Dyno estimate returned no data")
            except Exception as e:
                self._log(f"Error: {e}")
        asyncio.ensure_future(run())
