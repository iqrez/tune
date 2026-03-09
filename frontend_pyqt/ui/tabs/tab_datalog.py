"""
Tab 4: Datalogs
Record, playback, and analyze datalogs from ECU live data.
Uses backend endpoints: /datalog/start, /datalog/stop, /datalog/recent, /rusefi/live
"""
import asyncio
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QSplitter,
)
from PyQt6.QtCore import Qt, QTimer

from ..components.datalog_strip import DatalogStrip
from ..theme import COLOR_ACCENT


# Backend live data keys to log
_LOG_COLUMNS = ["Time", "RPM", "MAP", "AFR", "ECT", "IgnAdv", "Duty"]
_API_KEY_MAP = {
    "RPM": "rpm",
    "MAP": "map_kpa",
    "AFR": "afr",
    "ECT": "ect",
    "IgnAdv": "advance",
    "Duty": "injector_duty",
}


class DatalogTab(QWidget):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self._recording = False
        self._log_entries = []
        self._start_time = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Controls
        ctrl = QHBoxLayout()
        lbl = QLabel("Datalog Recorder")
        lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {COLOR_ACCENT};")
        ctrl.addWidget(lbl)
        ctrl.addStretch()

        self.btn_rec = QPushButton("Start Recording")
        self.btn_rec.setObjectName("PrimaryButton")
        self.btn_rec.clicked.connect(self._toggle_recording)
        ctrl.addWidget(self.btn_rec)

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.clicked.connect(self._export_csv)
        ctrl.addWidget(self.btn_export)

        self.btn_load = QPushButton("Load Log")
        self.btn_load.clicked.connect(self._load_log)
        ctrl.addWidget(self.btn_load)
        layout.addLayout(ctrl)

        # Status
        self.lbl_status = QLabel("IDLE - Not Recording")
        self.lbl_status.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self.lbl_status)

        # Splitter: table + analysis
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Log table
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(len(_LOG_COLUMNS))
        self.log_table.setHorizontalHeaderLabels(_LOG_COLUMNS)
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        splitter.addWidget(self.log_table)

        # Analysis text
        analysis_box = QGroupBox("Log Analysis")
        analysis_layout = QVBoxLayout(analysis_box)
        self.txt_analysis = QTextEdit()
        self.txt_analysis.setReadOnly(True)
        self.txt_analysis.setPlaceholderText("Record or load a datalog to see analysis here...")
        self.txt_analysis.setMaximumHeight(150)
        analysis_layout.addWidget(self.txt_analysis)
        splitter.addWidget(analysis_box)

        layout.addWidget(splitter)

        # Playback strip at bottom
        self.strip = DatalogStrip()
        layout.addWidget(self.strip)

    def _toggle_recording(self):
        if self._recording:
            self._recording = False
            self.btn_rec.setText("Start Recording")
            self.lbl_status.setText(f"Stopped - {self.log_table.rowCount()} entries captured")
            self.lbl_status.setStyleSheet("color: #888888;")
            self._run_analysis()
            asyncio.ensure_future(self.api.datalog_stop())
        else:
            self._recording = True
            self._log_entries.clear()
            self._start_time = time.time()
            self.log_table.setRowCount(0)
            self.btn_rec.setText("Stop Recording")
            self.lbl_status.setText("RECORDING...")
            self.lbl_status.setStyleSheet("color: #CF6679; font-weight: bold;")
            asyncio.ensure_future(self.api.datalog_start())
            self._poll_live()

    def _poll_live(self):
        if not self._recording:
            return

        async def fetch():
            data = await self.api.get_live_data()
            if data and self._recording and data.get("connected", False):
                elapsed = time.time() - self._start_time
                row = self.log_table.rowCount()
                self.log_table.insertRow(row)

                vals = [f"{elapsed:.2f}"]
                for col_name in _LOG_COLUMNS[1:]:
                    api_key = _API_KEY_MAP.get(col_name, "")
                    raw = data.get(api_key, 0)
                    vals.append(f"{float(raw):.1f}" if raw else "0.0")

                for c, v in enumerate(vals):
                    self.log_table.setItem(row, c, QTableWidgetItem(v))
                self._log_entries.append(vals)
                self.log_table.scrollToBottom()
                self.lbl_status.setText(f"RECORDING... ({len(self._log_entries)} entries)")

                # 10 Hz logging rate
                QTimer.singleShot(100, self._poll_live)

        asyncio.ensure_future(fetch())

    def _run_analysis(self):
        if not self._log_entries:
            return
        try:
            rpms = [float(e[1]) for e in self._log_entries]
            maps = [float(e[2]) for e in self._log_entries]
            afrs = [float(e[3]) for e in self._log_entries]
            duration = float(self._log_entries[-1][0]) - float(self._log_entries[0][0])
            lines = [
                f"Duration: {duration:.1f}s  |  Entries: {len(self._log_entries)}",
                f"RPM: min={min(rpms):.0f}  max={max(rpms):.0f}  avg={sum(rpms)/len(rpms):.0f}",
                f"MAP: min={min(maps):.0f}  max={max(maps):.0f}  avg={sum(maps)/len(maps):.0f}  kPa",
                f"AFR: min={min(afrs):.2f}  max={max(afrs):.2f}  avg={sum(afrs)/len(afrs):.2f}",
            ]
            self.txt_analysis.setText("\n".join(lines))
        except Exception as e:
            self.txt_analysis.setText(f"Analysis error: {e}")

    def _export_csv(self):
        if not self._log_entries:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Datalog", "datalog.csv", "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w") as f:
            f.write(",".join(_LOG_COLUMNS) + "\n")
            for row in self._log_entries:
                f.write(",".join(row) + "\n")
        self.lbl_status.setText(f"Exported to {path}")

    def _load_log(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Datalog", "", "CSV Files (*.csv);;All Files (*)")
        if not path:
            return
        self._log_entries.clear()
        self.log_table.setRowCount(0)
        with open(path, "r") as f:
            header = f.readline()
            for line in f:
                vals = line.strip().split(",")
                if len(vals) >= len(_LOG_COLUMNS):
                    row = self.log_table.rowCount()
                    self.log_table.insertRow(row)
                    for c, v in enumerate(vals[:len(_LOG_COLUMNS)]):
                        self.log_table.setItem(row, c, QTableWidgetItem(v))
                    self._log_entries.append(vals[:len(_LOG_COLUMNS)])
        self._run_analysis()
        self.lbl_status.setText(f"Loaded {len(self._log_entries)} entries from file")
