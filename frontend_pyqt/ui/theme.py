# Global PyQt theme (Honda-centric dark with rusEFI orange accents)

COLOR_BACKGROUND = "#0F0F0F"
COLOR_SURFACE = "#1A1A1A"
COLOR_SURFACE_LIGHT = "#262626"
COLOR_ACCENT = "#FF6600"
COLOR_TEXT = "#E6E6E6"
COLOR_TEXT_DIM = "#9B9B9B"
COLOR_BORDER = "#3A3A3A"
COLOR_DANGER = "#CF6679"
COLOR_SUCCESS = "#03DAC6"


STYLESHEET = f"""
QMainWindow, QDialog {{
    background-color: {COLOR_BACKGROUND};
    color: {COLOR_TEXT};
    font-family: 'Segoe UI';
}}

QWidget {{
    background-color: transparent;
    color: {COLOR_TEXT};
}}

QMenuBar, QToolBar {{
    background-color: {COLOR_SURFACE};
    border-bottom: 1px solid {COLOR_BORDER};
}}

QToolBar {{
    spacing: 8px;
    padding: 4px;
}}

QMenuBar::item:selected {{
    background-color: {COLOR_ACCENT};
    color: white;
}}

QTreeWidget {{
    background-color: {COLOR_SURFACE};
    border: none;
    border-right: 1px solid {COLOR_BORDER};
    font-size: 13px;
}}

QTreeWidget::item {{
    height: 28px;
    padding-left: 8px;
}}

QTreeWidget::item:selected {{
    background-color: {COLOR_ACCENT};
    color: white;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {COLOR_SURFACE_LIGHT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {COLOR_TEXT};
}}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLOR_ACCENT};
}}

QComboBox QAbstractItemView {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    selection-background-color: {COLOR_ACCENT};
}}

QPushButton {{
    background-color: {COLOR_SURFACE_LIGHT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 6px 12px;
    min-width: 70px;
}}

QPushButton:hover {{
    border-color: {COLOR_ACCENT};
}}

QPushButton#PrimaryButton {{
    background-color: {COLOR_ACCENT};
    color: white;
    border: none;
    font-weight: 700;
}}

QPushButton#PrimaryButton:hover {{
    background-color: #E85D00;
}}

QPushButton#RibbonToggle {{
    background-color: #1F1F1F;
    color: {COLOR_TEXT_DIM};
}}

QPushButton#RibbonToggle:checked {{
    background-color: rgba(255,102,0,0.22);
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_ACCENT};
    font-weight: 700;
}}

QTableWidget {{
    background-color: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    gridline-color: {COLOR_BORDER};
    font-family: 'Consolas';
}}

QHeaderView::section {{
    background-color: {COLOR_SURFACE_LIGHT};
    border: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT_DIM};
    padding: 4px;
}}

QStatusBar {{
    background-color: {COLOR_SURFACE};
    border-top: 1px solid {COLOR_BORDER};
    color: {COLOR_TEXT_DIM};
}}

QFrame#MenuDetailCard {{
    background-color: #171717;
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
}}

QTreeWidget#MenuBrowserTree {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
}}

QFrame#GaugeCard {{
    background-color: #141414;
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
}}

QFrame#DatalogStrip {{
    background-color: #151515;
    border-top: 1px solid {COLOR_BORDER};
}}

QScrollBar:vertical {{
    background: {COLOR_BACKGROUND};
    width: 10px;
}}

QScrollBar::handle:vertical {{
    background: {COLOR_BORDER};
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLOR_ACCENT};
}}
"""
