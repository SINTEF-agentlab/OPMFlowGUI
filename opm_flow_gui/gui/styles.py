"""Modern dark-themed Qt stylesheet for OPM Flow GUI.

Provides a cohesive, professional dark colour scheme built around a purple
accent.  All colour values are exposed as module-level constants so that
other parts of the application can reference them without hard-coding hex
strings.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Platform-aware font stack
# ---------------------------------------------------------------------------
if sys.platform == "darwin":
    _FONT_FAMILY = '"Helvetica Neue", "Arial", sans-serif'
    _FONT_SIZE = "13pt"
elif sys.platform == "win32":
    _FONT_FAMILY = '"Segoe UI", "Arial", sans-serif'
    _FONT_SIZE = "10pt"
else:
    _FONT_FAMILY = '"Ubuntu", "Roboto", "Arial", sans-serif'
    _FONT_SIZE = "10pt"

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
BG_PRIMARY: str = "#1e1e2e"
BG_SECONDARY: str = "#2a2a3c"
BG_TERTIARY: str = "#353548"
ACCENT: str = "#7c3aed"
ACCENT_HOVER: str = "#8b5cf6"
ACCENT_LIGHT: str = "#a78bfa"
TEXT_PRIMARY: str = "#e2e8f0"
TEXT_SECONDARY: str = "#94a3b8"
TEXT_MUTED: str = "#64748b"
SUCCESS: str = "#22c55e"
WARNING: str = "#f59e0b"
ERROR: str = "#ef4444"
BORDER: str = "#3f3f5c"
SELECTION: str = "#4c1d95"

# ---------------------------------------------------------------------------
# Complete QSS stylesheet
# ---------------------------------------------------------------------------
STYLESHEET: str = f"""
/* ===== Global ===== */
QMainWindow,
QWidget {{
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
    font-family: {_FONT_FAMILY};
    font-size: {_FONT_SIZE};
}}

QDialog {{
    background-color: {BG_PRIMARY};
    color: {TEXT_PRIMARY};
}}

/* ===== Labels ===== */
QLabel {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
}}

QLabel[secondary="true"] {{
    color: {TEXT_SECONDARY};
}}

QLabel[muted="true"] {{
    color: {TEXT_MUTED};
}}

/* ===== Push Buttons ===== */
QPushButton {{
    background-color: {ACCENT};
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton:pressed {{
    background-color: {ACCENT_LIGHT};
}}

QPushButton:disabled {{
    background-color: {BG_TERTIARY};
    color: {TEXT_MUTED};
}}

QPushButton[flat="true"] {{
    background-color: transparent;
    color: {ACCENT_LIGHT};
    border: none;
    padding: 6px 12px;
}}

QPushButton[flat="true"]:hover {{
    background-color: rgba(124, 58, 237, 0.15);
    color: {ACCENT_HOVER};
}}

QPushButton[flat="true"]:pressed {{
    background-color: rgba(124, 58, 237, 0.25);
}}

/* ===== Tree / List / Table Widgets ===== */
QTreeWidget,
QListWidget,
QTableWidget {{
    background-color: {BG_SECONDARY};
    alternate-background-color: {BG_TERTIARY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px;
    selection-background-color: {SELECTION};
    selection-color: {TEXT_PRIMARY};
    outline: none;
}}

QTreeWidget::item,
QListWidget::item,
QTableWidget::item {{
    padding: 6px 8px;
    border-radius: 4px;
}}

QTreeWidget::item:hover,
QListWidget::item:hover,
QTableWidget::item:hover {{
    background-color: rgba(124, 58, 237, 0.12);
}}

QTreeWidget::item:selected,
QListWidget::item:selected,
QTableWidget::item:selected {{
    background-color: {SELECTION};
    color: {TEXT_PRIMARY};
}}

QTreeWidget::branch {{
    background-color: transparent;
}}

QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {{
    border-image: none;
    image: none;
}}

QTreeWidget::branch:open:has-children:!has-siblings,
QTreeWidget::branch:open:has-children:has-siblings {{
    border-image: none;
    image: none;
}}

/* ===== Header View ===== */
QHeaderView {{
    background-color: transparent;
}}

QHeaderView::section {{
    background-color: {BG_TERTIARY};
    color: {TEXT_SECONDARY};
    padding: 8px 12px;
    border: none;
    border-bottom: 2px solid {BORDER};
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
}}

QHeaderView::section:hover {{
    background-color: {BG_SECONDARY};
    color: {TEXT_PRIMARY};
}}

/* ===== Input Fields ===== */
QLineEdit,
QSpinBox,
QDoubleSpinBox,
QComboBox {{
    background-color: {BG_SECONDARY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    min-height: 18px;
    selection-background-color: {SELECTION};
    selection-color: {TEXT_PRIMARY};
}}

QLineEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QComboBox:focus {{
    border: 1px solid {ACCENT};
}}

QLineEdit:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled,
QComboBox:disabled {{
    background-color: {BG_TERTIARY};
    color: {TEXT_MUTED};
}}

QLineEdit::placeholder {{
    color: {TEXT_MUTED};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {TEXT_SECONDARY};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_SECONDARY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: {SELECTION};
    selection-color: {TEXT_PRIMARY};
    padding: 4px;
}}

QSpinBox::up-button,
QDoubleSpinBox::up-button {{
    background-color: transparent;
    border: none;
    border-left: 1px solid {BORDER};
    padding: 2px 6px;
}}

QSpinBox::down-button,
QDoubleSpinBox::down-button {{
    background-color: transparent;
    border: none;
    border-left: 1px solid {BORDER};
    padding: 2px 6px;
}}

QSpinBox::up-arrow,
QDoubleSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {TEXT_SECONDARY};
}}

QSpinBox::down-arrow,
QDoubleSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SECONDARY};
}}

/* ===== Progress Bar ===== */
QProgressBar {{
    background-color: {BG_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    text-align: center;
    color: {TEXT_PRIMARY};
    font-weight: 600;
}}

QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 7px;
}}

/* ===== Scroll Bars ===== */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {BORDER};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {TEXT_MUTED};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {BORDER};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {TEXT_MUTED};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* ===== Group Box ===== */
QGroupBox {{
    background-color: {BG_SECONDARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    color: {ACCENT_LIGHT};
    font-size: 13px;
}}

/* ===== Tabs ===== */
QTabWidget::pane {{
    background-color: {BG_PRIMARY};
    border: 1px solid {BORDER};
    border-top: none;
    border-radius: 0 0 8px 8px;
}}

QTabBar {{
    background-color: transparent;
}}

QTabBar::tab {{
    background-color: {BG_TERTIARY};
    color: {TEXT_SECONDARY};
    padding: 10px 20px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background-color: {BG_PRIMARY};
    color: {ACCENT_LIGHT};
    border-bottom: 2px solid {ACCENT};
}}

QTabBar::tab:hover:!selected {{
    background-color: {BG_SECONDARY};
    color: {TEXT_PRIMARY};
}}

/* ===== Splitter ===== */
QSplitter::handle {{
    background-color: {BORDER};
}}

QSplitter::handle:horizontal {{
    width: 2px;
    margin: 4px 1px;
}}

QSplitter::handle:vertical {{
    height: 2px;
    margin: 1px 4px;
}}

QSplitter::handle:hover {{
    background-color: {ACCENT};
}}

/* ===== Tooltips ===== */
QToolTip {{
    background-color: {BG_TERTIARY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ===== Menu Bar & Menus ===== */
QMenuBar {{
    background-color: {BG_SECONDARY};
    color: {TEXT_PRIMARY};
    border-bottom: 1px solid {BORDER};
    padding: 2px 0;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 6px 12px;
    border-radius: 4px;
    margin: 2px;
}}

QMenuBar::item:selected {{
    background-color: {BG_TERTIARY};
    color: {ACCENT_LIGHT};
}}

QMenu {{
    background-color: {BG_SECONDARY};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px;
}}

QMenu::item {{
    padding: 8px 32px 8px 16px;
    border-radius: 4px;
    margin: 2px 4px;
}}

QMenu::item:selected {{
    background-color: {SELECTION};
    color: {TEXT_PRIMARY};
}}

QMenu::separator {{
    height: 1px;
    background-color: {BORDER};
    margin: 4px 8px;
}}

QMenu::indicator {{
    width: 16px;
    height: 16px;
    margin-left: 6px;
}}

/* ===== Check Box ===== */
QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
    background-color: transparent;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER};
    border-radius: 4px;
    background-color: {BG_SECONDARY};
}}

QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    image: none;
}}

QCheckBox::indicator:checked:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QCheckBox::indicator:disabled {{
    background-color: {BG_TERTIARY};
    border-color: {BG_TERTIARY};
}}

/* ===== Radio Button ===== */
QRadioButton {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
    background-color: transparent;
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {BORDER};
    border-radius: 11px;
    background-color: {BG_SECONDARY};
}}

QRadioButton::indicator:hover {{
    border-color: {ACCENT};
}}

QRadioButton::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

QRadioButton::indicator:checked:hover {{
    background-color: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}

QRadioButton::indicator:disabled {{
    background-color: {BG_TERTIARY};
    border-color: {BG_TERTIARY};
}}
"""

# ---------------------------------------------------------------------------
# Status → colour mapping
# ---------------------------------------------------------------------------
_STATUS_COLOURS: dict[str, str] = {
    "RUNNING": ACCENT,
    "COMPLETED": SUCCESS,
    "FAILED": ERROR,
    "CANCELLED": WARNING,
    "PENDING": TEXT_MUTED,
}


def get_status_color(status: str) -> str:
    """Return the hex colour string for a given simulation status.

    Unknown statuses fall back to :data:`TEXT_MUTED`.
    """
    return _STATUS_COLOURS.get(status.upper(), TEXT_MUTED)


# ---------------------------------------------------------------------------
# Application styling helper
# ---------------------------------------------------------------------------

def apply_style(app: QApplication) -> None:
    """Apply the dark theme stylesheet and palette to *app*."""
    # Set a platform-appropriate system font before applying the stylesheet
    # so that the OS default metrics are respected on macOS/Linux.
    if sys.platform == "darwin":
        font = QFont("Helvetica Neue", 13)
    elif sys.platform == "win32":
        font = QFont("Segoe UI", 10)
    else:
        font = app.font()
        font.setPointSize(10)
    app.setFont(font)

    app.setStyleSheet(STYLESHEET)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG_PRIMARY))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_SECONDARY))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_TERTIARY))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_TERTIARY))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_TERTIARY))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(ERROR))
    palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT_LIGHT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(SELECTION))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_MUTED))

    # Disabled-state colours
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        QColor(TEXT_MUTED),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor(TEXT_MUTED),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(TEXT_MUTED),
    )

    app.setPalette(palette)
