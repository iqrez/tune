"""
Tab 6: Firmware & SD Card
Firmware info from /rusefi/live, detect ports, datalog listing.
Uses backend endpoints: /rusefi/live, /rusefi/detect_ports, /datalog/recent
"""
import asyncio
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QGridLayout, QTextEdit, QListWidget,
    QListWidgetItem, QProgressBar, QFileDialog,
)
from PyQt6.QtCore import Qt

from ..theme import COLOR_ACCENT


class FirmwareTab(QWidget):
    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        lbl = QLabel("Firmware & SD Card Management")
        lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLOR_ACCENT};")
        layout.addWidget(lbl)

        cols = QHBoxLayout()

        # Left: Firmware Info
        fw_box = QGroupBox("Firmware")
        fw_lay = QVBoxLayout(fw_box)

        info_grid = QGridLayout()
        self.lbl_sig = QLabel("--")
        self.lbl_port = QLabel("--")
        self.lbl_mode = QLabel("--")
        self.lbl_uptime = QLabel("--")
        info_grid.addWidget(QLabel("ECU Signature:"), 0, 0)
        info_grid.addWidget(self.lbl_sig, 0, 1)
        info_grid.addWidget(QLabel("Port:"), 1, 0)
        info_grid.addWidget(self.lbl_port, 1, 1)
        info_grid.addWidget(QLabel("Mode:"), 2, 0)
        info_grid.addWidget(self.lbl_mode, 2, 1)
        info_grid.addWidget(QLabel("Uptime:"), 3, 0)
        info_grid.addWidget(self.lbl_uptime, 3, 1)
        fw_lay.addLayout(info_grid)

        self.btn_refresh_fw = QPushButton("Refresh Info")
        self.btn_refresh_fw.setObjectName("PrimaryButton")
        self.btn_refresh_fw.clicked.connect(self._refresh_fw_info)
        fw_lay.addWidget(self.btn_refresh_fw)

        self.btn_detect = QPushButton("Detect Ports")
        self.btn_detect.clicked.connect(self._detect_ports)
        fw_lay.addWidget(self.btn_detect)

        self.btn_flash = QPushButton("Flash Firmware (.dfu)")
        self.btn_flash.clicked.connect(self._flash_firmware)
        fw_lay.addWidget(self.btn_flash)

        self.fw_progress = QProgressBar()
        self.fw_progress.setValue(0)
        fw_lay.addWidget(self.fw_progress)
        fw_lay.addStretch()
        cols.addWidget(fw_box)

        # Right: Recent datalogs (replaces non-existent SD card)
        sd_box = QGroupBox("Recent Datalogs")
        sd_lay = QVBoxLayout(sd_box)

        sd_ctrl = QHBoxLayout()
        self.btn_sd_refresh = QPushButton("Refresh")
        self.btn_sd_refresh.clicked.connect(self._refresh_datalogs)
        sd_ctrl.addWidget(self.btn_sd_refresh)
        self.btn_sd_export = QPushButton("Export Selected")
        self.btn_sd_export.clicked.connect(self._export_datalog)
        sd_ctrl.addWidget(self.btn_sd_export)
        sd_ctrl.addStretch()
        sd_lay.addLayout(sd_ctrl)

        self.sd_list = QListWidget()
        self.sd_list.setStyleSheet("background-color: #252525; font-family: Consolas;")
        sd_lay.addWidget(self.sd_list)

        self.lbl_sd_status = QLabel("Datalogs: Not scanned")
        self.lbl_sd_status.setStyleSheet("color: #888888; font-size: 11px;")
        sd_lay.addWidget(self.lbl_sd_status)
        cols.addWidget(sd_box)

        layout.addLayout(cols)

        # Console log
        log_box = QGroupBox("Console")
        log_lay = QVBoxLayout(log_box)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumHeight(120)
        self.console.setStyleSheet("font-family: Consolas; font-size: 11px; background-color: #1A1A1A;")
        log_lay.addWidget(self.console)
        layout.addWidget(log_box)

    def _log(self, msg):
        self.console.append(msg)

    def _refresh_fw_info(self):
        self._log("Refreshing firmware info...")

        async def fetch():
            try:
                live = await self.api.get_live_data()
                connected = live.get("connected", False)

                if not connected:
                    self.lbl_sig.setText("Not Connected")
                    self.lbl_port.setText("--")
                    self.lbl_mode.setText("--")
                    self.lbl_uptime.setText("--")
                    self._log("ECU not connected")
                    return

                # Extract firmware info from /rusefi/live response
                port = live.get("port", "--")
                console = live.get("console_mode", False)
                uptime = live.get("uptime_s")
                conn_type = live.get("connection_type", "--")

                self.lbl_port.setText(f"{port} ({conn_type})")
                self.lbl_mode.setText("Console" if console else "Binary")
                if uptime is not None:
                    mins = int(float(uptime)) // 60
                    secs = int(float(uptime)) % 60
                    self.lbl_uptime.setText(f"{mins}m {secs}s")
                else:
                    self.lbl_uptime.setText("--")

                # Try to get signature from connect response data
                # The signature is stored on the backend client, not in /live
                # So we show port info instead
                self.lbl_sig.setText(f"Connected on {port}")
                self._log(f"Firmware info refreshed: {port} ({conn_type})")
            except Exception as e:
                self._log(f"Error: {e}")
        asyncio.ensure_future(fetch())

    def _detect_ports(self):
        self._log("Detecting serial ports...")

        async def fetch():
            try:
                resp = await self.api.client.get(f"{self.api.base_url}/rusefi/detect_ports")
                if resp.status_code == 200:
                    data = resp.json()
                    ports = data.get("ports", [])
                    detection = data.get("detection", {})
                    self._log(f"Found {len(ports)} ports: {ports}")
                    if detection:
                        for k, v in detection.items():
                            self._log(f"  {k}: {v}")
                else:
                    self._log(f"Port detection failed: {resp.text}")
            except Exception as e:
                self._log(f"Error: {e}")
        asyncio.ensure_future(fetch())

    def _flash_firmware(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Firmware", "", "DFU Files (*.dfu);;BIN Files (*.bin);;All Files (*)")
        if not path:
            return
        self._log(f"Firmware flashing is a placeholder. Selected: {path}")
        self._log("Use STM32CubeProgrammer or dfu-util for actual flashing.")

    def _refresh_datalogs(self):
        self._log("Fetching recent datalogs...")
        self.sd_list.clear()

        async def fetch():
            try:
                logs = await self.api.datalog_recent()
                for log_entry in logs:
                    if isinstance(log_entry, dict):
                        name = log_entry.get("filename", str(log_entry))
                    else:
                        name = str(log_entry)
                    self.sd_list.addItem(QListWidgetItem(name))
                self.lbl_sd_status.setText(f"Datalogs: {len(logs)} found")
                self._log(f"Found {len(logs)} recent datalogs")
            except Exception as e:
                self._log(f"Datalog Error: {e}")
                self.lbl_sd_status.setText("Datalogs: Error")
        asyncio.ensure_future(fetch())

    def _export_datalog(self):
        item = self.sd_list.currentItem()
        if not item:
            return
        filename = item.text()
        save_path, _ = QFileDialog.getSaveFileName(self, "Export Datalog", filename, "CSV Files (*.csv);;All Files (*)")
        if not save_path:
            return
        self._log(f"Exporting {filename}...")

        async def fetch():
            try:
                resp = await self.api.client.get(f"{self.api.base_url}/datalog/export/{filename}")
                if resp.status_code == 200:
                    with open(save_path, "wb") as f:
                        f.write(resp.content)
                    self._log(f"Saved: {save_path}")
                else:
                    self._log(f"Export failed: {resp.text}")
            except Exception as e:
                self._log(f"Error: {e}")
        asyncio.ensure_future(fetch())
