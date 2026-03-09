from __future__ import annotations

from typing import Iterable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget


class MiniTrace(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._samples: list[float] = []
        self.setMinimumWidth(180)
        self.setMaximumWidth(260)

    def set_samples(self, samples: Iterable[float]):
        self._samples = [float(s) for s in list(samples)[-120:]]
        self.update()

    def push_sample(self, sample: float):
        self._samples.append(float(sample))
        if len(self._samples) > 120:
            self._samples = self._samples[-120:]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(24, 24, 24))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        if len(self._samples) < 2:
            p.setPen(QPen(QColor(100, 100, 100), 1))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Log")
            return

        lo = min(self._samples)
        hi = max(self._samples)
        span = max(1e-6, hi - lo)

        w = max(1, self.width() - 8)
        h = max(1, self.height() - 8)
        step = w / max(1, len(self._samples) - 1)

        p.setPen(QPen(QColor(255, 102, 0), 2))
        x_prev = 4
        y_prev = 4 + h - int(((self._samples[0] - lo) / span) * h)
        for i, sample in enumerate(self._samples[1:], start=1):
            x = 4 + int(i * step)
            y = 4 + h - int(((sample - lo) / span) * h)
            p.drawLine(x_prev, y_prev, x, y)
            x_prev, y_prev = x, y


class DatalogStrip(QFrame):
    toggled = pyqtSignal(bool)
    play_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = True
        self._playing = False
        self.setObjectName("DatalogStrip")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 4)
        root.setSpacing(6)

        top = QHBoxLayout()
        self.btn_toggle = QPushButton("Hide Playback")
        self.btn_toggle.clicked.connect(self._toggle)
        top.addWidget(self.btn_toggle)

        self.btn_rec = QPushButton("REC")
        self.btn_rec.setObjectName("PrimaryButton")
        top.addWidget(self.btn_rec)

        self.btn_play = QPushButton("Play")
        self.btn_play.clicked.connect(self._toggle_play)
        top.addWidget(self.btn_play)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        top.addWidget(self.slider, 1)

        self.lbl_time = QLabel("00:00 / 00:00")
        top.addWidget(self.lbl_time)

        self.lbl_status = QLabel("Playback Idle")
        top.addWidget(self.lbl_status)

        root.addLayout(top)

        self.trace = MiniTrace()
        self.trace.setFixedHeight(46)
        root.addWidget(self.trace)

    def _toggle(self):
        self._expanded = not self._expanded
        self.trace.setVisible(self._expanded)
        self.btn_toggle.setText("Hide Playback" if self._expanded else "Show Playback")
        self.toggled.emit(self._expanded)

    def _toggle_play(self):
        self._playing = not self._playing
        self.btn_play.setText("Pause" if self._playing else "Play")
        self.play_toggled.emit(self._playing)

    def push_sample(self, sample: float):
        self.trace.push_sample(sample)
