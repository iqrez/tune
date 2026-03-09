"""
Tab 3: Dashboards
Live gauge panel with configurable gauges.
Full-screen gauge dashboard for real-time ECU monitoring.
"""
import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QGroupBox, QComboBox,
)
from PyQt6.QtCore import Qt

from ..components.gauge_panel import GaugeWidget
from ..theme import COLOR_ACCENT, COLOR_SURFACE


# Map backend LiveDataResponse field names -> gauge display names
_LIVE_KEY_MAP = {
    "rpm":            "RPM",
    "map_kpa":        "MAP",
    "afr":            "AFR",
    "iat":            "IAT",
    "ect":            "ECT",
    "advance":        "IgnAdv",
    "knock_count":    "Knock",
    "injector_duty":  "Duty",
    "voltage":        "Voltage",
    "tps":            "TPS",
}


class DashboardTab(QWidget):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.gauges = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        lbl = QLabel("Live Dashboard")
        lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLOR_ACCENT};")
        header.addWidget(lbl)
        header.addStretch()

        self.lbl_status = QLabel("DISCONNECTED")
        self.lbl_status.setStyleSheet("color: #CF6679; font-weight: bold;")
        header.addWidget(self.lbl_status)
        layout.addLayout(header)

        # Primary gauges (large)
        primary = QGroupBox("Primary")
        primary_grid = QGridLayout(primary)
        primary_configs = [
            ("RPM",    "RPM",  0, 8000, 0, 0),
            ("MAP",    "kPa",  0, 300,  0, 1),
            ("AFR",    "\u03bb", 0.5, 1.5, 0, 2),
            ("IgnAdv", "\u00b0",  -10, 60,  0, 3),
        ]
        for name, unit, lo, hi, r, c in primary_configs:
            g = GaugeWidget(name, unit, lo, hi)
            g.setMinimumSize(120, 120)
            self.gauges[name] = g
            primary_grid.addWidget(g, r, c)
        layout.addWidget(primary)

        # Secondary gauges (smaller)
        secondary = QGroupBox("Secondary")
        sec_grid = QGridLayout(secondary)
        sec_configs = [
            ("IAT",   "\u00b0C",   -40, 120, 0, 0),
            ("ECT",   "\u00b0C",   -40, 120, 0, 1),
            ("Knock", "Count",  0,  100, 0, 2),
            ("Duty",  "%",      0,  100, 0, 3),
            ("Voltage", "V",    0,  18,  1, 0),
            ("TPS",   "%",      0,  100, 1, 1),
        ]
        for name, unit, lo, hi, r, c in sec_configs:
            g = GaugeWidget(name, unit, lo, hi)
            g.setMinimumSize(96, 96)
            self.gauges[name] = g
            sec_grid.addWidget(g, r, c)
        layout.addWidget(secondary)

    def update_data(self, data):
        if not data or not data.get("connected", False):
            self.lbl_status.setText("DISCONNECTED")
            self.lbl_status.setStyleSheet("color: #CF6679; font-weight: bold;")
            return

        self.lbl_status.setText("LIVE")
        self.lbl_status.setStyleSheet("color: #03DAC6; font-weight: bold;")

        # Map backend field names to gauge names
        for api_key, gauge_name in _LIVE_KEY_MAP.items():
            if api_key in data and gauge_name in self.gauges:
                try:
                    self.gauges[gauge_name].set_value(float(data[api_key]))
                except (ValueError, TypeError):
                    pass
