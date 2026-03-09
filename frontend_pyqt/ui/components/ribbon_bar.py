from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QPushButton, QSizePolicy, QToolBar, QWidget


class RibbonBar(QToolBar):
    connect_clicked = pyqtSignal()
    burn_clicked = pyqtSignal()
    save_clicked = pyqtSignal()
    load_clicked = pyqtSignal()
    preset_clicked = pyqtSignal()
    datalog_clicked = pyqtSignal()
    firmware_clicked = pyqtSignal()
    fuel_map_selected = pyqtSignal(int)
    ign_map_selected = pyqtSignal(int)
    ai_chat_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(False)
        self.setFloatable(False)
        self._build_ui()

    def _build_ui(self):
        self.btn_connect = self._btn("ECU Connect", primary=True)
        self.btn_connect.clicked.connect(self.connect_clicked.emit)
        self.addWidget(self.btn_connect)

        self.btn_burn = self._btn("Burn to ECU")
        self.btn_burn.clicked.connect(self.burn_clicked.emit)
        self.addWidget(self.btn_burn)

        self.btn_preset = self._btn("Honda Presets", primary=True)
        self.btn_preset.clicked.connect(self.preset_clicked.emit)
        self.addWidget(self.btn_preset)

        self.btn_load = self._btn("Open Tune")
        self.btn_load.clicked.connect(self.load_clicked.emit)
        self.addWidget(self.btn_load)

        self.btn_save = self._btn("Save Tune")
        self.btn_save.clicked.connect(self.save_clicked.emit)
        self.addWidget(self.btn_save)

        self.addSeparator()

        self._fuel_group = QButtonGroup(self)
        self._fuel_group.setExclusive(True)
        self.btn_fuel_map_1 = self._btn("VE Map 1", checkable=True)
        self.btn_fuel_map_2 = self._btn("VE Map 2", checkable=True)
        self._fuel_group.addButton(self.btn_fuel_map_1, 1)
        self._fuel_group.addButton(self.btn_fuel_map_2, 2)
        self.btn_fuel_map_1.setChecked(True)
        self._fuel_group.idClicked.connect(self.fuel_map_selected.emit)
        self.addWidget(self.btn_fuel_map_1)
        self.addWidget(self.btn_fuel_map_2)

        self._ign_group = QButtonGroup(self)
        self._ign_group.setExclusive(True)
        self.btn_ign_map_1 = self._btn("Ign Map 1", checkable=True)
        self.btn_ign_map_2 = self._btn("Ign Map 2", checkable=True)
        self._ign_group.addButton(self.btn_ign_map_1, 1)
        self._ign_group.addButton(self.btn_ign_map_2, 2)
        self.btn_ign_map_1.setChecked(True)
        self._ign_group.idClicked.connect(self.ign_map_selected.emit)
        self.addWidget(self.btn_ign_map_1)
        self.addWidget(self.btn_ign_map_2)

        self.addSeparator()

        self.btn_datalog = self._btn("Start Log")
        self.btn_datalog.clicked.connect(self.datalog_clicked.emit)
        self.addWidget(self.btn_datalog)

        self.btn_firmware = self._btn("Firmware")
        self.btn_firmware.clicked.connect(self.firmware_clicked.emit)
        self.addWidget(self.btn_firmware)

        self.btn_ai = self._btn("AI Advisor", checkable=True)
        self.btn_ai.toggled.connect(self.ai_chat_toggled.emit)
        self.addWidget(self.btn_ai)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

    def _btn(self, text: str, primary: bool = False, checkable: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(checkable)
        if primary:
            btn.setObjectName("PrimaryButton")
        elif checkable:
            btn.setObjectName("RibbonToggle")
        return btn
