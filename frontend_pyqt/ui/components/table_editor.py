from __future__ import annotations

from typing import Iterable, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QBrush, QKeyEvent
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


class TableEditor(QTableWidget):
    data_changed = pyqtSignal(list)

    FIT_SMART = "smart"
    FIT_BOTH = "both"
    FIT_COLUMNS = "columns"
    FIT_ROWS = "rows"
    FIT_MANUAL = "manual"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ContiguousSelection)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.setAlternatingRowColors(True)

        self.horizontalHeader().setMinimumSectionSize(36)
        self.verticalHeader().setMinimumSectionSize(22)
        self.verticalHeader().setDefaultSectionSize(28)

        self._decimals = 1
        self._step = 0.1
        self._shift_multiplier = 5.0
        self._heatmap_enabled = True
        self._fit_mode = self.FIT_SMART
        self._manual_cell_px = 72
        self._x_axis: list[float] = []
        self._y_axis: list[float] = []
        self._overlay_hits: set[tuple[int, int]] = set()

        self.itemChanged.connect(self.on_cell_changed)
        self._apply_resize_mode(force=True)

    def configure_view(
        self,
        *,
        fit_mode: Optional[str] = None,
        decimals: Optional[int] = None,
        step: Optional[float] = None,
        heatmap_enabled: Optional[bool] = None,
        manual_cell_px: Optional[int] = None,
    ):
        if fit_mode:
            self._fit_mode = fit_mode
        if decimals is not None:
            self._decimals = max(0, min(4, int(decimals)))
        if step is not None:
            self._step = max(0.01, float(step))
        if heatmap_enabled is not None:
            self._heatmap_enabled = bool(heatmap_enabled)
        if manual_cell_px is not None:
            self._manual_cell_px = max(36, min(180, int(manual_cell_px)))

        self._apply_resize_mode(force=True)
        self._refresh_table_formatting()

    def set_axes(self, x_axis: Optional[Iterable[float]] = None, y_axis: Optional[Iterable[float]] = None):
        self._x_axis = list(x_axis) if x_axis else []
        self._y_axis = list(y_axis) if y_axis else []
        self._apply_axis_headers()

    def load_table(
        self,
        data: list,
        *,
        x_axis: Optional[Iterable[float]] = None,
        y_axis: Optional[Iterable[float]] = None,
    ):
        self.blockSignals(True)
        self.clearContents()
        self._overlay_hits.clear()

        if not data or not isinstance(data, list) or not isinstance(data[0], list):
            self.setRowCount(0)
            self.setColumnCount(0)
            self.blockSignals(False)
            return

        rows = len(data)
        cols = len(data[0])
        self.setRowCount(rows)
        self.setColumnCount(cols)

        self.set_axes(x_axis, y_axis)

        for r in range(rows):
            for c in range(cols):
                val = data[r][c]
                try:
                    fval = float(val)
                except (TypeError, ValueError):
                    fval = 0.0

                item = QTableWidgetItem(self._format_value(fval))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(r, c, item)
                self._apply_cell_brush(item, fval)

        self.blockSignals(False)
        self._apply_resize_mode(force=True)

    def _format_axis_value(self, value: float) -> str:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return str(value)
        if abs(num) >= 1000:
            return f"{num:.0f}"
        if abs(num) >= 100:
            return f"{num:.1f}"
        return f"{num:.2f}".rstrip("0").rstrip(".")

    def _apply_axis_headers(self):
        cols = self.columnCount()
        rows = self.rowCount()

        if cols:
            labels = []
            for i in range(cols):
                if i < len(self._x_axis):
                    labels.append(self._format_axis_value(self._x_axis[i]))
                else:
                    labels.append(str(i))
            self.setHorizontalHeaderLabels(labels)

        if rows:
            labels = []
            for i in range(rows):
                if i < len(self._y_axis):
                    labels.append(self._format_axis_value(self._y_axis[i]))
                else:
                    labels.append(str(i))
            self.setVerticalHeaderLabels(labels)

    def _format_value(self, value: float) -> str:
        return f"{float(value):.{self._decimals}f}"

    def _parse_item_float(self, item: Optional[QTableWidgetItem]) -> float:
        if not item:
            return 0.0
        try:
            return float(item.text())
        except (TypeError, ValueError):
            return 0.0

    def _overlay_color(self, base: QColor) -> QColor:
        # Blend existing cell color with orange hit marker.
        orange = QColor(255, 102, 0)
        return QColor(
            int((base.red() * 0.45) + (orange.red() * 0.55)),
            int((base.green() * 0.45) + (orange.green() * 0.55)),
            int((base.blue() * 0.45) + (orange.blue() * 0.55)),
        )

    def _apply_cell_brush(self, item: QTableWidgetItem, value: float):
        if not self._heatmap_enabled:
            base = QColor(45, 45, 45)
            fg = QColor(230, 230, 230)
        else:
            max_val = 100.0
            ratio = max(0.0, min(1.0, value / max_val))
            hue = int(240 - (240 * ratio))  # blue -> red
            base = QColor.fromHsv(hue, 180, 100)
            fg = QColor("black" if hue > 40 else "white")

        r = item.row()
        c = item.column()
        if (r, c) in self._overlay_hits:
            base = self._overlay_color(base)
            fg = QColor("black")

        item.setBackground(QBrush(base))
        item.setForeground(QBrush(fg))

    def _refresh_table_formatting(self):
        self.blockSignals(True)
        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                item = self.item(r, c)
                if not item:
                    continue
                value = self._parse_item_float(item)
                item.setText(self._format_value(value))
                self._apply_cell_brush(item, value)
        self.blockSignals(False)

    def _smart_section_size(self):
        cols = max(1, self.columnCount())
        rows = max(1, self.rowCount())
        vw = max(1, self.viewport().width())
        vh = max(1, self.viewport().height())

        col_px = max(52, min(130, int(vw / cols) - 1))
        row_px = max(24, min(56, int(vh / rows) - 1))
        return col_px, row_px

    def _apply_resize_mode(self, force: bool = False):
        h = self.horizontalHeader()
        v = self.verticalHeader()
        mode = self._fit_mode

        if mode == self.FIT_BOTH:
            h.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            v.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            return

        if mode == self.FIT_COLUMNS:
            h.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            v.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            _, row_px = self._smart_section_size()
            v.setDefaultSectionSize(row_px)
            return

        if mode == self.FIT_ROWS:
            h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            v.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            col_px, _ = self._smart_section_size()
            h.setDefaultSectionSize(col_px)
            return

        if mode == self.FIT_MANUAL:
            h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            v.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            h.setDefaultSectionSize(self._manual_cell_px)
            v.setDefaultSectionSize(max(22, int(self._manual_cell_px * 0.55)))
            return

        h.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        v.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        col_px, row_px = self._smart_section_size()
        h.setDefaultSectionSize(col_px)
        v.setDefaultSectionSize(row_px)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._fit_mode == self.FIT_SMART:
            self._apply_resize_mode(force=True)

    def apply_percent_to_selection(self, percent_delta: float):
        if not self.selectedItems():
            return
        factor = 1.0 + (float(percent_delta) / 100.0)
        self.blockSignals(True)
        for item in self.selectedItems():
            value = self._parse_item_float(item)
            item.setText(self._format_value(value * factor))
        self.blockSignals(False)
        self._refresh_table_formatting()

    def clear_overlay_hits(self):
        self._overlay_hits.clear()
        self._refresh_table_formatting()

    def set_overlay_hits(self, hits: Iterable[tuple[int, int]]):
        self._overlay_hits = {(int(r), int(c)) for r, c in hits}
        self._refresh_table_formatting()

    def push_overlay_hit(self, row: int, col: int, max_hits: int = 18):
        if row < 0 or col < 0 or row >= self.rowCount() or col >= self.columnCount():
            return
        self._overlay_hits.add((row, col))
        if len(self._overlay_hits) > max_hits:
            # trim oldest-ish by converting to list and slicing
            kept = list(self._overlay_hits)[-max_hits:]
            self._overlay_hits = set(kept)
        item = self.item(row, col)
        if item:
            self._apply_cell_brush(item, self._parse_item_float(item))

    def keyPressEvent(self, event: QKeyEvent):
        selection = self.selectedItems()
        if not selection:
            super().keyPressEvent(event)
            return

        delta = 0.0
        if event.key() == Qt.Key.Key_Plus:
            delta = self._step
        elif event.key() == Qt.Key.Key_Minus:
            delta = -self._step

        if delta != 0.0:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                delta *= self._shift_multiplier

            for item in selection:
                value = self._parse_item_float(item) + delta
                item.setText(self._format_value(value))
            return

        super().keyPressEvent(event)

    def get_table_data(self) -> list:
        rows = self.rowCount()
        cols = self.columnCount()
        data = [[0.0 for _ in range(cols)] for _ in range(rows)]
        for r in range(rows):
            for c in range(cols):
                item = self.item(r, c)
                data[r][c] = self._parse_item_float(item)
        return data

    def on_cell_changed(self, item: QTableWidgetItem):
        value = self._parse_item_float(item)
        self.blockSignals(True)
        item.setText(self._format_value(value))
        self.blockSignals(False)
        self._apply_cell_brush(item, value)
