from __future__ import annotations

from typing import Any, Dict, Iterable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QConicalGradient, QFont, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


# Map backend live payload fields -> visual names
_LIVE_KEY_MAP = {
    "rpm": "RPM",
    "map_kpa": "MAP",
    "afr": "AFR",
    "iat": "IAT",
    "ect": "ECT",
    "advance": "IgnAdv",
    "knock_count": "Knock",
    "injector_duty": "Duty",
    "voltage": "Voltage",
    "tps": "TPS",
}

# Common watch parameter name aliases -> live key
_WATCH_TO_LIVE = {
    "rpm": "rpm",
    "map": "map_kpa",
    "map_kpa": "map_kpa",
    "afr": "afr",
    "iat": "iat",
    "ect": "ect",
    "ignitionadvance": "advance",
    "advance": "advance",
    "knock": "knock_count",
    "knockcount": "knock_count",
    "injectorduty": "injector_duty",
    "duty": "injector_duty",
    "voltage": "voltage",
    "tps": "tps",
}


class GaugeWidget(QWidget):
    def __init__(self, label, unit, min_val=0, max_val=8000, parent=None):
        super().__init__(parent)
        self.label = label
        self.unit = unit
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.value = 0.0
        self.setMinimumSize(118, 118)

    def set_value(self, val):
        try:
            v = float(val)
        except (TypeError, ValueError):
            v = 0.0
        self.value = max(self.min_val, min(self.max_val, v))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        size = min(w, h) - 12
        cx, cy = w // 2, h // 2

        grad = QConicalGradient(cx, cy, 90)
        grad.setColorAt(0.0, QColor(38, 38, 38))
        grad.setColorAt(1.0, QColor(18, 18, 18))
        p.setBrush(grad)
        p.setPen(QPen(QColor(70, 70, 70), 2))
        p.drawEllipse(cx - size // 2, cy - size // 2, size, size)

        # Arc
        p.setPen(QPen(QColor(255, 102, 0), 4, cap=Qt.PenCapStyle.RoundCap))
        sweep = 270.0 * ((self.value - self.min_val) / max(1e-9, (self.max_val - self.min_val)))
        p.drawArc(cx - size // 2 + 8, cy - size // 2 + 8, size - 16, size - 16, 225 * 16, int(-sweep * 16))

        # Text
        p.setPen(QColor(146, 146, 146))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(self.rect().adjusted(0, 8, 0, 0), Qt.AlignmentFlag.AlignHCenter, self.label)

        p.setPen(QColor(245, 245, 245))
        p.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        txt = f"{self.value:.0f}" if self.max_val >= 500 else f"{self.value:.1f}"
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, txt)

        p.setPen(QColor(170, 170, 170))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(self.rect().adjusted(0, 0, 0, -18), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, self.unit)


class GaugePanel(QWidget):
    """Right-side panel with live gauges + watch list."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.gauge_card = QFrame()
        self.gauge_card.setObjectName("GaugeCard")
        gauge_layout = QGridLayout(self.gauge_card)
        gauge_layout.setContentsMargins(4, 4, 4, 4)
        gauge_layout.setSpacing(8)

        configs = [
            ("RPM", "RPM", 0, 10000),
            ("MAP", "kPa", 0, 320),
            ("AFR", "lambda", 0.5, 1.5),
            ("IgnAdv", "deg", -10, 60),
            ("IAT", "C", -40, 140),
            ("ECT", "C", -40, 140),
            ("Knock", "count", 0, 100),
            ("Duty", "%", 0, 100),
            ("Voltage", "V", 0, 18),
            ("TPS", "%", 0, 100),
        ]
        self.gauges: Dict[str, GaugeWidget] = {}
        for idx, (name, unit, lo, hi) in enumerate(configs):
            g = GaugeWidget(name, unit, lo, hi)
            self.gauges[name] = g
            r, c = divmod(idx, 2)
            gauge_layout.addWidget(g, r, c)

        root.addWidget(self.gauge_card, 2)

        watch_header = QLabel("Watch List")
        watch_header.setStyleSheet("font-size: 13px; color: #FF6600; font-weight: 700;")
        root.addWidget(watch_header)

        self.watch_table = QTableWidget(0, 2)
        self.watch_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.watch_table.horizontalHeader().setStretchLastSection(True)
        self.watch_table.verticalHeader().setVisible(False)
        self.watch_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.watch_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.watch_table.setAlternatingRowColors(True)
        self.watch_table.setMinimumHeight(180)
        root.addWidget(self.watch_table, 1)

        self._watch_rows: Dict[str, int] = {}

    def update_data(self, data: Dict[str, Any]):
        for api_key, name in _LIVE_KEY_MAP.items():
            if api_key in data and name in self.gauges:
                try:
                    self.gauges[name].set_value(float(data[api_key]))
                except (ValueError, TypeError):
                    pass

    def set_watch_list(self, names: Iterable[str]):
        ordered = [str(n) for n in names if str(n).strip()]
        self.watch_table.setRowCount(len(ordered))
        self._watch_rows.clear()
        for r, name in enumerate(ordered):
            self._watch_rows[name] = r
            self.watch_table.setItem(r, 0, QTableWidgetItem(name))
            self.watch_table.setItem(r, 1, QTableWidgetItem("--"))

    def update_watch_values(self, values: Dict[str, Any]):
        for name, value in (values or {}).items():
            row = self._watch_rows.get(name)
            if row is None:
                continue
            cell = self.watch_table.item(row, 1)
            if cell is None:
                cell = QTableWidgetItem("--")
                self.watch_table.setItem(row, 1, cell)
            cell.setText(str(value))

    def update_watch_from_live(self, watch_names: Iterable[str], live_data: Dict[str, Any]):
        values: Dict[str, Any] = {}
        for name in watch_names:
            slug = "".join(ch for ch in str(name).lower() if ch.isalnum())
            key = _WATCH_TO_LIVE.get(slug)
            if not key:
                continue
            if key in live_data:
                raw = live_data.get(key)
                try:
                    num = float(raw)
                    if key in ("rpm", "knock_count"):
                        values[name] = f"{int(num)}"
                    elif key in ("afr",):
                        values[name] = f"{num:.2f}"
                    else:
                        values[name] = f"{num:.1f}"
                except (TypeError, ValueError):
                    values[name] = str(raw)
        if values:
            self.update_watch_values(values)
