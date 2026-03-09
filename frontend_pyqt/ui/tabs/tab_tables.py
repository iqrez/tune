"""
Tab 2: Table Editor
Dedicated tab for loading/editing/writing fuel, ignition, boost, and lambda tables.
Uses backend endpoints: POST /tables/load, POST /tables/save
Falls back to GET /parameters/read/{name} if tables/load fails.
"""
import asyncio
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QLabel, QSpinBox, QDoubleSpinBox, QCheckBox,
)
from PyQt6.QtCore import Qt

from ..components.table_editor import TableEditor
from ..components.table_3d import Table3DDialog
from ..theme import COLOR_ACCENT


KNOWN_TABLES = [
    "veTable", "ignitionTable", "boostTableOpenLoop",
    "boostTableClosedLoop", "lambdaTable",
]


class TablesTab(QWidget):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self._current_table = ""
        self._current_data = []
        self._rpm_axis = []
        self._map_axis = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Top controls
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Table:"))
        self.combo_table = QComboBox()
        self.combo_table.addItems(KNOWN_TABLES)
        self.combo_table.setMinimumWidth(200)
        ctrl.addWidget(self.combo_table)

        self.btn_load = QPushButton("Read from ECU")
        self.btn_load.setObjectName("PrimaryButton")
        self.btn_load.clicked.connect(self._on_read)
        ctrl.addWidget(self.btn_load)

        self.btn_write = QPushButton("Write to ECU")
        self.btn_write.clicked.connect(self._on_write)
        ctrl.addWidget(self.btn_write)

        self.btn_3d = QPushButton("3D View")
        self.btn_3d.clicked.connect(self._on_3d)
        ctrl.addWidget(self.btn_3d)

        ctrl.addStretch()

        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: bold;")
        ctrl.addWidget(self.lbl_info)
        layout.addLayout(ctrl)

        # View controls
        view_ctrl = QHBoxLayout()
        view_ctrl.addWidget(QLabel("Layout"))
        self.view_fit = QComboBox()
        self.view_fit.addItems(["Smart Fit", "Fit Both", "Fit Columns", "Fit Rows", "Manual"])
        view_ctrl.addWidget(self.view_fit)

        view_ctrl.addWidget(QLabel("Decimals"))
        self.view_decimals = QSpinBox()
        self.view_decimals.setRange(0, 4)
        self.view_decimals.setValue(1)
        view_ctrl.addWidget(self.view_decimals)

        view_ctrl.addWidget(QLabel("Step"))
        self.view_step = QDoubleSpinBox()
        self.view_step.setDecimals(2)
        self.view_step.setRange(0.01, 10.0)
        self.view_step.setSingleStep(0.05)
        self.view_step.setValue(0.10)
        view_ctrl.addWidget(self.view_step)

        view_ctrl.addWidget(QLabel("Cell px"))
        self.view_cell_px = QSpinBox()
        self.view_cell_px.setRange(36, 180)
        self.view_cell_px.setValue(72)
        view_ctrl.addWidget(self.view_cell_px)

        self.view_heatmap = QCheckBox("Heatmap")
        self.view_heatmap.setChecked(True)
        view_ctrl.addWidget(self.view_heatmap)
        view_ctrl.addStretch()
        layout.addLayout(view_ctrl)

        # Table editor
        self.table_editor = TableEditor()
        layout.addWidget(self.table_editor)
        self.view_fit.currentTextChanged.connect(self._apply_view_options)
        self.view_decimals.valueChanged.connect(self._apply_view_options)
        self.view_step.valueChanged.connect(self._apply_view_options)
        self.view_cell_px.valueChanged.connect(self._apply_view_options)
        self.view_heatmap.toggled.connect(self._apply_view_options)
        self._apply_view_options()

    def _apply_view_options(self):
        mode_map = {
            "Smart Fit": self.table_editor.FIT_SMART,
            "Fit Both": self.table_editor.FIT_BOTH,
            "Fit Columns": self.table_editor.FIT_COLUMNS,
            "Fit Rows": self.table_editor.FIT_ROWS,
            "Manual": self.table_editor.FIT_MANUAL,
        }
        self.table_editor.configure_view(
            fit_mode=mode_map.get(self.view_fit.currentText(), self.table_editor.FIT_SMART),
            decimals=self.view_decimals.value(),
            step=self.view_step.value(),
            heatmap_enabled=self.view_heatmap.isChecked(),
            manual_cell_px=self.view_cell_px.value(),
        )

    def _reshape_flat(self, flat_list):
        """Reshape a flat 1D list into a 2D grid."""
        size = len(flat_list)
        side = int(math.sqrt(size))
        if side * side == size:
            return [flat_list[i * side:(i + 1) * side] for i in range(side)]
        # Non-square: try common ECU shapes
        for r in [8, 16, 4]:
            if size % r == 0:
                c = size // r
                return [flat_list[i * c:(i + 1) * c] for i in range(r)]
        return [flat_list]

    def _on_read(self):
        name = self.combo_table.currentText()
        self._current_table = name
        self.lbl_info.setText(f"Reading {name}...")

        async def fetch():
            # Try the tables/load endpoint first (returns 2D data with axes)
            result = await self.api.load_table(name)
            if result and "data" in result:
                data = result["data"]
                self._rpm_axis = result.get("rpm_axis", [])
                self._map_axis = result.get("map_axis", [])
                rows = result.get("rows", 0)
                cols = result.get("cols", 0)
                self._current_data = data
                self.table_editor.load_table(data, x_axis=self._rpm_axis, y_axis=self._map_axis)
                self.lbl_info.setText(f"{name}: {rows}x{cols}")
                return

            # Fallback: read as raw parameter
            data = await self.api.read_parameter(name)
            if data and isinstance(data.get("value"), list):
                vals = data["value"]
                if vals and not isinstance(vals[0], list):
                    vals = self._reshape_flat(vals)
                self._current_data = vals
                self.table_editor.load_table(vals)
                r = len(vals)
                c = len(vals[0]) if vals else 0
                self.lbl_info.setText(f"{name}: {r}x{c}")
            else:
                self.lbl_info.setText(f"Failed to read {name}")

        asyncio.ensure_future(fetch())

    def _on_write(self):
        if not self._current_table:
            return
        data = self.table_editor.get_table_data()
        name = self._current_table
        self.lbl_info.setText(f"Writing {name}...")

        async def write():
            # Try the tables/save endpoint first
            result = await self.api.save_table(name, data)
            if result and result.get("status") == "ok":
                self.lbl_info.setText(f"{name} written to ECU")
                return
            # Fallback to parameters/write
            ok = await self.api.write_parameter(name, data)
            self.lbl_info.setText(f"{name} written" if ok else f"Write failed for {name}")

        asyncio.ensure_future(write())

    def _on_3d(self):
        data = self.table_editor.get_table_data()
        name = self._current_table or "Table"
        dlg = Table3DDialog(name, data, self)
        dlg.exec()
