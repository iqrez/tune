from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QHeaderView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .table_3d import Table3DDialog
from .table_editor import TableEditor


class EditorPane(QWidget):
    """Center pane: scalar/table editor and compact category browser."""

    param_requested = pyqtSignal(str)

    _ROLE_BROWSER_PARAM = Qt.ItemDataRole.UserRole + 20

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 8)
        root.setSpacing(8)

        self.header = QLabel("Select a parameter to edit")
        self.header.setStyleSheet("font-size: 20px; font-weight: 700; color: #FF6600;")
        root.addWidget(self.header)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self._current_param_name = ""
        self._browser_category = ""
        self._browser_entries: List[Dict[str, Any]] = []
        self._browser_items_by_name: Dict[str, QTreeWidgetItem] = {}

        self._build_param_editor()
        self._build_category_browser()

        self.stack.setCurrentWidget(self.param_widget)

    # ------------------------------------------------------------------ Build Param Editor
    def _build_param_editor(self):
        self.param_widget = QWidget()
        layout = QVBoxLayout(self.param_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.param_tabs = QTabWidget()
        layout.addWidget(self.param_tabs, 1)

        # Value tab
        value_tab = QWidget()
        value_layout = QVBoxLayout(value_tab)
        value_layout.setContentsMargins(0, 0, 0, 0)

        self.value_stack = QStackedWidget()
        value_layout.addWidget(self.value_stack, 1)

        # Scalar view
        self.scalar_widget = QWidget()
        scalar_form = QFormLayout(self.scalar_widget)
        self.scalar_input = QLineEdit()
        scalar_form.addRow("Value", self.scalar_input)

        self.btn_save_scalar = QPushButton("Write to RAM")
        self.btn_save_scalar.setObjectName("PrimaryButton")
        scalar_form.addRow("", self.btn_save_scalar)

        self.value_stack.addWidget(self.scalar_widget)

        # Table view
        self.table_widget = QWidget()
        table_layout = QVBoxLayout(self.table_widget)
        table_layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Layout"))
        self.table_fit = QComboBox()
        self.table_fit.addItems(["Smart Fit", "Fit Both", "Fit Columns", "Fit Rows", "Manual"])
        toolbar.addWidget(self.table_fit)

        toolbar.addWidget(QLabel("Decimals"))
        self.table_decimals = QSpinBox()
        self.table_decimals.setRange(0, 4)
        self.table_decimals.setValue(1)
        toolbar.addWidget(self.table_decimals)

        self.table_heatmap = QCheckBox("Heatmap")
        self.table_heatmap.setChecked(True)
        toolbar.addWidget(self.table_heatmap)

        toolbar.addSpacing(16)
        toolbar.addWidget(QLabel("Quick Trim"))
        self.btn_trim_p5 = QPushButton("+5%")
        self.btn_trim_m5 = QPushButton("-5%")
        self.btn_trim_p2 = QPushButton("+2%")
        self.btn_trim_m2 = QPushButton("-2%")
        for b in (self.btn_trim_p5, self.btn_trim_m5, self.btn_trim_p2, self.btn_trim_m2):
            b.setObjectName("RibbonToggle")
            toolbar.addWidget(b)

        toolbar.addStretch()
        table_layout.addLayout(toolbar)

        self.table_editor = TableEditor()
        table_layout.addWidget(self.table_editor, 1)

        row = QHBoxLayout()
        self.btn_save_table = QPushButton("Write Table")
        self.btn_save_table.setObjectName("PrimaryButton")
        row.addWidget(self.btn_save_table)

        self.btn_view_3d = QPushButton("View 3D")
        row.addWidget(self.btn_view_3d)
        row.addStretch()
        table_layout.addLayout(row)

        self.value_stack.addWidget(self.table_widget)

        self.param_tabs.addTab(value_tab, "Value")

        # Graph tab
        self.graph_tab = QWidget()
        gl = QVBoxLayout(self.graph_tab)
        self.graph_summary = QLabel("Use View 3D for VE / Ignition / AFR surfaces.")
        self.graph_summary.setWordWrap(True)
        gl.addWidget(self.graph_summary)
        self.btn_graph_3d = QPushButton("Open 3D Surface")
        gl.addWidget(self.btn_graph_3d)
        gl.addStretch()
        self.param_tabs.addTab(self.graph_tab, "Graph")

        # Advanced tab
        self.advanced_tab = QWidget()
        al = QVBoxLayout(self.advanced_tab)
        self.advanced_notes = QLabel("Advanced notes and warnings appear here.")
        self.advanced_notes.setWordWrap(True)
        al.addWidget(self.advanced_notes)
        al.addStretch()
        self.param_tabs.addTab(self.advanced_tab, "Advanced")

        # Wire
        self.table_fit.currentTextChanged.connect(self._apply_table_view_config)
        self.table_decimals.valueChanged.connect(self._apply_table_view_config)
        self.table_heatmap.toggled.connect(self._apply_table_view_config)
        self.btn_view_3d.clicked.connect(self.on_view_3d)
        self.btn_graph_3d.clicked.connect(self.on_view_3d)

        self.btn_trim_p5.clicked.connect(lambda: self.table_editor.apply_percent_to_selection(5.0))
        self.btn_trim_m5.clicked.connect(lambda: self.table_editor.apply_percent_to_selection(-5.0))
        self.btn_trim_p2.clicked.connect(lambda: self.table_editor.apply_percent_to_selection(2.0))
        self.btn_trim_m2.clicked.connect(lambda: self.table_editor.apply_percent_to_selection(-2.0))

        self._apply_table_view_config()
        self.stack.addWidget(self.param_widget)

    # ------------------------------------------------------------------ Build Browser
    def _build_category_browser(self):
        self.browser_widget = QWidget()
        layout = QVBoxLayout(self.browser_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.browser_summary = QLabel("Category browser")
        self.browser_summary.setStyleSheet("color: #C0C0C0; font-size: 13px;")
        layout.addWidget(self.browser_summary)

        menu_row = QHBoxLayout()
        menu_row.addWidget(QLabel("Menu"))
        self.browser_top_combo = QComboBox()
        self.browser_top_combo.currentTextChanged.connect(self._on_browser_top_changed)
        menu_row.addWidget(self.browser_top_combo, 1)

        menu_row.addWidget(QLabel("Section"))
        self.browser_group_combo = QComboBox()
        self.browser_group_combo.currentTextChanged.connect(self._on_browser_group_changed)
        menu_row.addWidget(self.browser_group_combo, 1)

        menu_row.addWidget(QLabel("Setting"))
        self.browser_setting_combo = QComboBox()
        self.browser_setting_combo.currentTextChanged.connect(self._on_browser_setting_changed)
        menu_row.addWidget(self.browser_setting_combo, 2)

        self.btn_open_from_menu = QPushButton("Load Setting")
        self.btn_open_from_menu.setObjectName("PrimaryButton")
        self.btn_open_from_menu.clicked.connect(self._open_selected_from_combo)
        menu_row.addWidget(self.btn_open_from_menu)
        layout.addLayout(menu_row)

        self.browser_search = QLineEdit()
        self.browser_search.setPlaceholderText("Filter settings...")
        self.browser_search.textChanged.connect(self._refresh_browser_tree)
        layout.addWidget(self.browser_search)

        self.browser_tree = QTreeWidget()
        self.browser_tree.setObjectName("MenuBrowserTree")
        self.browser_tree.setColumnCount(5)
        self.browser_tree.setHeaderLabels(["Setting", "Current", "Type", "Units", "Range"])
        self.browser_tree.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.browser_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.browser_tree.header().setStretchLastSection(False)
        self.browser_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.browser_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.browser_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.browser_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.browser_tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.browser_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.browser_tree.itemDoubleClicked.connect(self._on_browser_item_activated)
        self.browser_tree.itemSelectionChanged.connect(self._on_browser_selection_changed)
        layout.addWidget(self.browser_tree, 1)

        detail = QFrame()
        detail.setObjectName("MenuDetailCard")
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(10, 6, 10, 6)
        dl.setSpacing(4)

        self.detail_name = QLabel("Choose a setting")
        self.detail_name.setStyleSheet("font-size: 16px; font-weight: 700;")
        dl.addWidget(self.detail_name)

        self.detail_meta = QLabel("")
        self.detail_meta.setWordWrap(True)
        self.detail_meta.setStyleSheet("color: #9A9A9A; font-family: Consolas;")
        dl.addWidget(self.detail_meta)

        self.btn_open_detail = QPushButton("Open Setting")
        self.btn_open_detail.setObjectName("PrimaryButton")
        self.btn_open_detail.clicked.connect(self._open_selected_from_browser)
        dl.addWidget(self.btn_open_detail, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(detail)

        self.stack.addWidget(self.browser_widget)

    # ------------------------------------------------------------------ API for tab_tuning
    def show_placeholder(self, name: str, category: str = "", reason: str = ""):
        self._current_param_name = name
        self.header.setText(f"{name}")
        self.show_scalar(name, 0)
        self.scalar_input.setPlaceholderText(reason or "Parameter currently unavailable from ECU")
        self.advanced_notes.setText(
            f"Category: {category or '-'}\n\n"
            f"{reason or 'No live ECU value returned. You can still set a starting value and write it.'}"
        )

    def show_scalar(self, name: str, value: Any):
        self._current_param_name = name
        self.header.setText(f"{name}")
        self.scalar_input.setText(str(value if value is not None else 0))
        self.value_stack.setCurrentWidget(self.scalar_widget)
        self.param_tabs.setCurrentIndex(0)
        self.graph_summary.setText("Scalar parameter. Graph preview not available.")
        self.stack.setCurrentWidget(self.param_widget)

    def show_table(self, name: str, data: List[List[float]]):
        self._current_param_name = name
        self.header.setText(f"{name}")
        self.table_editor.load_table(data or [[0.0] * 8 for _ in range(8)])
        self.value_stack.setCurrentWidget(self.table_widget)
        self.param_tabs.setCurrentIndex(0)
        self.graph_summary.setText("Table loaded. Use Quick Trim and View 3D for fast workflow.")
        self.stack.setCurrentWidget(self.param_widget)

    def show_category(
        self,
        category_path: str,
        entries: List[Dict[str, Any]],
        preferred_group: Optional[str] = None,
        group_order: Optional[List[str]] = None,
        display_title: Optional[str] = None,
    ):
        self._browser_category = category_path or ""
        self._browser_entries = [dict(e) for e in (entries or [])]
        title = display_title or category_path or "Category"
        self.header.setText(f"Menu: {title}")
        self.stack.setCurrentWidget(self.browser_widget)
        self._refresh_browser_tree()

    def set_browser_status(self, text: str):
        self.browser_summary.setText(text)

    def set_browser_value(self, name: str, value_text: str):
        for e in self._browser_entries:
            if e.get("name") == name:
                e["_current_value_display"] = value_text
                break

        item = self._browser_items_by_name.get(name)
        if item is not None:
            item.setText(1, str(value_text))
            if self.browser_tree.currentItem() == item:
                self._on_browser_selection_changed()

    def update_table_hit(self, rpm: Any, map_kpa: Any):
        if self.value_stack.currentWidget() != self.table_widget:
            return
        rows = self.table_editor.rowCount()
        cols = self.table_editor.columnCount()
        if rows <= 0 or cols <= 0:
            return
        try:
            r = float(rpm)
            m = float(map_kpa)
        except (TypeError, ValueError):
            return

        # Approximate hit position for overlays; enough for live + playback guidance.
        col = int(max(0, min(cols - 1, (r / 9000.0) * (cols - 1))))
        row = int(max(0, min(rows - 1, (m / 320.0) * (rows - 1))))
        self.table_editor.push_overlay_hit(row, col)

    # ------------------------------------------------------------------ Browser internals
    def _entry_range_text(self, entry: Dict[str, Any]) -> str:
        lo = entry.get("min")
        hi = entry.get("max")
        if lo is None and hi is None:
            return ""
        if lo is None:
            return f"<= {hi}"
        if hi is None:
            return f">= {lo}"
        return f"{lo} .. {hi}"

    def _group_name_for(self, entry: Dict[str, Any]) -> str:
        category = entry.get("_normalized_category") or entry.get("category") or "General"
        parts = [p.strip() for p in str(category).split(">") if p.strip()]
        if len(parts) >= 2:
            return parts[1]
        if len(parts) == 1:
            return parts[0]
        return "General"

    def _menu_top_name_for(self, entry: Dict[str, Any]) -> str:
        category = entry.get("_normalized_category") or entry.get("category") or "General"
        parts = [p.strip() for p in str(category).split(">") if p.strip()]
        if parts:
            return parts[0]
        return "General"

    def _refresh_browser_tree(self):
        self.browser_tree.clear()
        self._browser_items_by_name.clear()

        query = self.browser_search.text().strip().lower()
        shown = 0
        grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

        for entry in self._browser_entries:
            name = str(entry.get("name", ""))
            if not name:
                continue
            if query and query not in name.lower() and query not in str(entry.get("category", "")).lower():
                continue
            top_name = self._menu_top_name_for(entry)
            group_name = self._group_name_for(entry)
            grouped.setdefault(top_name, {}).setdefault(group_name, []).append(entry)

        # Build actual menu selectors (Menu -> Section -> Setting) for fast navigation.
        tops = sorted(grouped.keys())
        current_top = self.browser_top_combo.currentText().strip()
        top_choices = ["All Menus", *tops]
        self.browser_top_combo.blockSignals(True)
        self.browser_top_combo.clear()
        self.browser_top_combo.addItems(top_choices)
        if current_top in top_choices:
            self.browser_top_combo.setCurrentText(current_top)
        elif top_choices:
            self.browser_top_combo.setCurrentIndex(0)
        self.browser_top_combo.blockSignals(False)

        selected_top = self.browser_top_combo.currentText().strip() or "All Menus"
        sections_map: Dict[str, List[Dict[str, Any]]] = {}
        if selected_top == "All Menus":
            for top_name in tops:
                for section_name, section_entries in grouped[top_name].items():
                    sections_map.setdefault(section_name, []).extend(section_entries)
        else:
            sections_map = dict(grouped.get(selected_top, {}))

        sections = sorted(sections_map.keys())
        current_section = self.browser_group_combo.currentText().strip()
        section_choices = ["All Sections", *sections]
        self.browser_group_combo.blockSignals(True)
        self.browser_group_combo.clear()
        self.browser_group_combo.addItems(section_choices)
        if current_section in section_choices:
            self.browser_group_combo.setCurrentText(current_section)
        elif section_choices:
            self.browser_group_combo.setCurrentIndex(0)
        self.browser_group_combo.blockSignals(False)

        selected_section = self.browser_group_combo.currentText().strip() or "All Sections"
        if selected_section == "All Sections":
            display_entries = []
            for name in sections:
                display_entries.extend(sections_map[name])
        else:
            display_entries = list(sections_map.get(selected_section, []))

        display_entries = sorted(display_entries, key=lambda r: str(r.get("name", "")).lower())

        current_setting = self.browser_setting_combo.currentText().strip()
        self.browser_setting_combo.blockSignals(True)
        self.browser_setting_combo.clear()
        self.browser_setting_combo.addItems([str(e.get("name", "")) for e in display_entries if str(e.get("name", ""))])
        if current_setting:
            idx = self.browser_setting_combo.findText(current_setting)
            if idx >= 0:
                self.browser_setting_combo.setCurrentIndex(idx)
        self.browser_setting_combo.blockSignals(False)

        # Flat list view under the menu selectors (no giant nested "Additional (700)" tree).
        for entry in display_entries:
            name = str(entry.get("name", ""))
            kind = (entry.get("kind") or "scalar").lower()
            kind_txt = "table" if kind == "array" else "enum" if kind == "bits" else "scalar"
            current = str(entry.get("_current_value_display", "--"))
            units = str(entry.get("units") or "-")
            row = QTreeWidgetItem([
                name,
                current,
                kind_txt,
                units,
                self._entry_range_text(entry),
            ])
            row.setData(0, self._ROLE_BROWSER_PARAM, name)
            self.browser_tree.addTopLevelItem(row)
            self._browser_items_by_name[name] = row
            shown += 1

        if shown == 0:
            self.browser_summary.setText("No settings match this filter.")
            self.detail_name.setText("Choose a setting")
            self.detail_meta.setText("")
        else:
            context_label = f"{selected_top} / {selected_section}"
            self.browser_summary.setText(f"{shown} settings shown in {context_label}")
            active = self.browser_setting_combo.currentText().strip()
            if active:
                item = self._browser_items_by_name.get(active)
                if item is not None:
                    self.browser_tree.setCurrentItem(item)
                    self.browser_tree.scrollToItem(item)

    def _on_browser_item_activated(self, item: QTreeWidgetItem, _column: int):
        name = item.data(0, self._ROLE_BROWSER_PARAM)
        if name:
            self.param_requested.emit(str(name))

    def _selected_browser_param(self) -> Optional[str]:
        item = self.browser_tree.currentItem()
        if not item:
            return None
        name = item.data(0, self._ROLE_BROWSER_PARAM)
        return str(name) if name else None

    def _on_browser_selection_changed(self):
        name = self._selected_browser_param()
        if not name:
            return
        self.detail_name.setText(name)

        entry = None
        for e in self._browser_entries:
            if e.get("name") == name:
                entry = e
                break
        if not entry:
            self.detail_meta.setText("")
            return

        self.detail_meta.setText(
            f"Current: {entry.get('_current_value_display', '--')}\n"
            f"Type: {(entry.get('kind') or 'scalar')}\n"
            f"Units: {entry.get('units', '-')}\n"
            f"Range: {self._entry_range_text(entry)}"
        )

    def _open_selected_from_browser(self):
        name = self._selected_browser_param()
        if name:
            self.param_requested.emit(name)

    def _on_browser_group_changed(self, _text: str):
        self._refresh_browser_tree()

    def _on_browser_top_changed(self, _text: str):
        self._refresh_browser_tree()

    def _on_browser_setting_changed(self, name: str):
        name = (name or "").strip()
        if not name:
            return
        item = self._browser_items_by_name.get(name)
        if item is not None:
            self.browser_tree.setCurrentItem(item)
            self.browser_tree.scrollToItem(item)

    def _open_selected_from_combo(self):
        name = self.browser_setting_combo.currentText().strip()
        if name:
            self.param_requested.emit(name)

    # ------------------------------------------------------------------ Table view helpers
    def _apply_table_view_config(self):
        mode_map = {
            "Smart Fit": self.table_editor.FIT_SMART,
            "Fit Both": self.table_editor.FIT_BOTH,
            "Fit Columns": self.table_editor.FIT_COLUMNS,
            "Fit Rows": self.table_editor.FIT_ROWS,
            "Manual": self.table_editor.FIT_MANUAL,
        }
        self.table_editor.configure_view(
            fit_mode=mode_map.get(self.table_fit.currentText(), self.table_editor.FIT_SMART),
            decimals=self.table_decimals.value(),
            heatmap_enabled=self.table_heatmap.isChecked(),
        )

    def on_view_3d(self):
        data = self.table_editor.get_table_data()
        if not data:
            return
        dlg = Table3DDialog(self._current_param_name or "Table", data, self)
        dlg.exec()
