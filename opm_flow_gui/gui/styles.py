"""Modern dark-themed Qt stylesheet for OPM Flow GUI.

Provides a cohesive, professional dark colour scheme built around a purple
accent.  All colour values are exposed as module-level constants so that
other parts of the application can reference them without hard-coding hex
strings.

Multiple named themes are available via :data:`THEMES` and
:func:`apply_theme`.
"""

import sys
from typing import NamedTuple

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
# Theme definition
# ---------------------------------------------------------------------------

class ThemeColors(NamedTuple):
    bg_primary: str
    bg_secondary: str
    bg_tertiary: str
    accent: str
    accent_hover: str
    accent_light: str
    text_primary: str
    text_secondary: str
    text_muted: str
    success: str
    warning: str
    error: str
    border: str
    selection: str


THEMES: dict[str, ThemeColors] = {
    "Dark Purple": ThemeColors(
        bg_primary="#1e1e2e",
        bg_secondary="#2a2a3c",
        bg_tertiary="#353548",
        accent="#7c3aed",
        accent_hover="#8b5cf6",
        accent_light="#a78bfa",
        text_primary="#e2e8f0",
        text_secondary="#94a3b8",
        text_muted="#64748b",
        success="#22c55e",
        warning="#f59e0b",
        error="#ef4444",
        border="#3f3f5c",
        selection="#4c1d95",
    ),
    "Dark Blue": ThemeColors(
        bg_primary="#0f172a",
        bg_secondary="#1e293b",
        bg_tertiary="#293548",
        accent="#2563eb",
        accent_hover="#3b82f6",
        accent_light="#60a5fa",
        text_primary="#e2e8f0",
        text_secondary="#94a3b8",
        text_muted="#64748b",
        success="#22c55e",
        warning="#f59e0b",
        error="#ef4444",
        border="#334155",
        selection="#1e3a8a",
    ),
    "Dark Green": ThemeColors(
        bg_primary="#0f1a0f",
        bg_secondary="#182418",
        bg_tertiary="#223022",
        accent="#16a34a",
        accent_hover="#22c55e",
        accent_light="#4ade80",
        text_primary="#e2e8f0",
        text_secondary="#94a3b8",
        text_muted="#64748b",
        success="#22c55e",
        warning="#f59e0b",
        error="#ef4444",
        border="#2d4a2d",
        selection="#14532d",
    ),
    "Dark Teal": ThemeColors(
        bg_primary="#0d1f1f",
        bg_secondary="#182c2c",
        bg_tertiary="#213838",
        accent="#0d9488",
        accent_hover="#14b8a6",
        accent_light="#2dd4bf",
        text_primary="#e2e8f0",
        text_secondary="#94a3b8",
        text_muted="#64748b",
        success="#22c55e",
        warning="#f59e0b",
        error="#ef4444",
        border="#2a4040",
        selection="#134e4a",
    ),
    "Midnight": ThemeColors(
        bg_primary="#0a0a0f",
        bg_secondary="#111118",
        bg_tertiary="#1a1a24",
        accent="#6d28d9",
        accent_hover="#7c3aed",
        accent_light="#8b5cf6",
        text_primary="#d1d5db",
        text_secondary="#6b7280",
        text_muted="#4b5563",
        success="#16a34a",
        warning="#d97706",
        error="#dc2626",
        border="#2d2d40",
        selection="#3b0764",
    ),
    "Solarized Dark": ThemeColors(
        bg_primary="#002b36",
        bg_secondary="#073642",
        bg_tertiary="#0d3d4d",
        accent="#268bd2",
        accent_hover="#2aa198",
        accent_light="#93a1a1",
        text_primary="#fdf6e3",
        text_secondary="#839496",
        text_muted="#586e75",
        success="#859900",
        warning="#b58900",
        error="#dc322f",
        border="#1a4a55",
        selection="#073642",
    ),
    "Light": ThemeColors(
        bg_primary="#f8fafc",
        bg_secondary="#f1f5f9",
        bg_tertiary="#e2e8f0",
        accent="#7c3aed",
        accent_hover="#8b5cf6",
        accent_light="#6d28d9",
        text_primary="#0f172a",
        text_secondary="#475569",
        text_muted="#94a3b8",
        success="#15803d",
        warning="#b45309",
        error="#b91c1c",
        border="#cbd5e1",
        selection="#ddd6fe",
    ),
    "Light Blue": ThemeColors(
        bg_primary="#f0f9ff",
        bg_secondary="#e0f2fe",
        bg_tertiary="#bae6fd",
        accent="#0284c7",
        accent_hover="#0369a1",
        accent_light="#0369a1",
        text_primary="#0c4a6e",
        text_secondary="#075985",
        text_muted="#7dd3fc",
        success="#15803d",
        warning="#b45309",
        error="#b91c1c",
        border="#7dd3fc",
        selection="#bae6fd",
    ),
}

DEFAULT_THEME: str = "Dark Purple"

# Active theme colours (module-level constants, set by apply_theme / _set_active_theme)
_active: ThemeColors = THEMES[DEFAULT_THEME]

# ---------------------------------------------------------------------------
# Colour palette (module-level constants – kept for backward compatibility
# and convenience; updated whenever the active theme changes)
# ---------------------------------------------------------------------------
BG_PRIMARY: str = _active.bg_primary
BG_SECONDARY: str = _active.bg_secondary
BG_TERTIARY: str = _active.bg_tertiary
ACCENT: str = _active.accent
ACCENT_HOVER: str = _active.accent_hover
ACCENT_LIGHT: str = _active.accent_light
TEXT_PRIMARY: str = _active.text_primary
TEXT_SECONDARY: str = _active.text_secondary
TEXT_MUTED: str = _active.text_muted
SUCCESS: str = _active.success
WARNING: str = _active.warning
ERROR: str = _active.error
BORDER: str = _active.border
SELECTION: str = _active.selection

# ---------------------------------------------------------------------------
# Stylesheet builder
# ---------------------------------------------------------------------------

def build_stylesheet(c: ThemeColors) -> str:
    """Build and return a complete QSS stylesheet for the given theme colours."""
    return f"""
/* ===== Global ===== */
QMainWindow,
QWidget {{
    background-color: {c.bg_primary};
    color: {c.text_primary};
    font-family: {_FONT_FAMILY};
    font-size: {_FONT_SIZE};
}}

QDialog {{
    background-color: {c.bg_primary};
    color: {c.text_primary};
}}

/* ===== Labels ===== */
QLabel {{
    color: {c.text_primary};
    background-color: transparent;
}}

QLabel[secondary="true"] {{
    color: {c.text_secondary};
}}

QLabel[muted="true"] {{
    color: {c.text_muted};
}}

/* ===== Push Buttons ===== */
QPushButton {{
    background-color: {c.accent};
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {c.accent_hover};
}}

QPushButton:pressed {{
    background-color: {c.accent_light};
}}

QPushButton:disabled {{
    background-color: {c.bg_tertiary};
    color: {c.text_muted};
}}

QPushButton[flat="true"] {{
    background-color: transparent;
    color: {c.accent_light};
    border: none;
    padding: 6px 12px;
}}

QPushButton[flat="true"]:hover {{
    background-color: {c.selection};
    color: {c.accent_hover};
}}

QPushButton[flat="true"]:pressed {{
    background-color: {c.selection};
}}

/* ===== Tree / List / Table Widgets ===== */
QTreeWidget,
QListWidget,
QTableWidget {{
    background-color: {c.bg_secondary};
    alternate-background-color: {c.bg_tertiary};
    color: {c.text_primary};
    border: 1px solid {c.border};
    border-radius: 6px;
    padding: 4px;
    selection-background-color: {c.selection};
    selection-color: {c.text_primary};
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
    background-color: {c.selection};
}}

QTreeWidget::item:selected,
QListWidget::item:selected,
QTableWidget::item:selected {{
    background-color: {c.selection};
    color: {c.text_primary};
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
    background-color: {c.bg_tertiary};
    color: {c.text_secondary};
    padding: 8px 12px;
    border: none;
    border-bottom: 2px solid {c.border};
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
}}

QHeaderView::section:hover {{
    background-color: {c.bg_secondary};
    color: {c.text_primary};
}}

/* ===== Input Fields ===== */
QLineEdit,
QSpinBox,
QDoubleSpinBox,
QComboBox {{
    background-color: {c.bg_secondary};
    color: {c.text_primary};
    border: 1px solid {c.border};
    border-radius: 6px;
    padding: 8px 12px;
    min-height: 18px;
    selection-background-color: {c.selection};
    selection-color: {c.text_primary};
}}

QLineEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QComboBox:focus {{
    border: 1px solid {c.accent};
}}

QLineEdit:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled,
QComboBox:disabled {{
    background-color: {c.bg_tertiary};
    color: {c.text_muted};
}}

QLineEdit::placeholder {{
    color: {c.text_muted};
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {c.text_secondary};
    margin-right: 8px;
}}

QComboBox QAbstractItemView {{
    background-color: {c.bg_secondary};
    color: {c.text_primary};
    border: 1px solid {c.border};
    border-radius: 6px;
    selection-background-color: {c.selection};
    selection-color: {c.text_primary};
    padding: 4px;
}}

QSpinBox::up-button,
QDoubleSpinBox::up-button {{
    background-color: transparent;
    border: none;
    border-left: 1px solid {c.border};
    padding: 2px 6px;
}}

QSpinBox::down-button,
QDoubleSpinBox::down-button {{
    background-color: transparent;
    border: none;
    border-left: 1px solid {c.border};
    padding: 2px 6px;
}}

QSpinBox::up-arrow,
QDoubleSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {c.text_secondary};
}}

QSpinBox::down-arrow,
QDoubleSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {c.text_secondary};
}}

/* ===== Progress Bar ===== */
QProgressBar {{
    background-color: {c.bg_secondary};
    border: 1px solid {c.border};
    border-radius: 8px;
    text-align: center;
    color: {c.text_primary};
    font-weight: 600;
}}

QProgressBar::chunk {{
    background-color: {c.accent};
    border-radius: 7px;
}}

/* ===== Scroll Bars ===== */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {c.border};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {c.text_muted};
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
    background-color: {c.border};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {c.text_muted};
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
    background-color: {c.bg_secondary};
    border: 1px solid {c.border};
    border-radius: 8px;
    margin-top: 22px;
    padding: 20px 12px 12px 12px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 12px;
    color: {c.accent_light};
    font-size: 13px;
    background-color: {c.bg_secondary};
    border-radius: 4px;
}}

/* ===== Tabs ===== */
QTabWidget::pane {{
    background-color: {c.bg_primary};
    border: 1px solid {c.border};
    border-top: none;
    border-radius: 0 0 8px 8px;
}}

QTabBar {{
    background-color: transparent;
}}

QTabBar::tab {{
    background-color: {c.bg_tertiary};
    color: {c.text_secondary};
    padding: 10px 20px;
    border: 1px solid {c.border};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: 500;
}}

QTabBar::tab:selected {{
    background-color: {c.bg_primary};
    color: {c.accent_light};
    border-bottom: 2px solid {c.accent};
}}

QTabBar::tab:hover:!selected {{
    background-color: {c.bg_secondary};
    color: {c.text_primary};
}}

/* ===== Splitter ===== */
QSplitter::handle {{
    background-color: {c.border};
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
    background-color: {c.accent};
}}

/* ===== Tooltips ===== */
QToolTip {{
    background-color: {c.bg_tertiary};
    color: {c.text_primary};
    border: 1px solid {c.border};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ===== Menu Bar & Menus ===== */
QMenuBar {{
    background-color: {c.bg_secondary};
    color: {c.text_primary};
    border-bottom: 1px solid {c.border};
    padding: 2px 0;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 6px 12px;
    border-radius: 4px;
    margin: 2px;
}}

QMenuBar::item:selected {{
    background-color: {c.bg_tertiary};
    color: {c.accent_light};
}}

QMenu {{
    background-color: {c.bg_secondary};
    color: {c.text_primary};
    border: 1px solid {c.border};
    border-radius: 8px;
    padding: 6px;
}}

QMenu::item {{
    padding: 8px 32px 8px 16px;
    border-radius: 4px;
    margin: 2px 4px;
}}

QMenu::item:selected {{
    background-color: {c.selection};
    color: {c.text_primary};
}}

QMenu::separator {{
    height: 1px;
    background-color: {c.border};
    margin: 4px 8px;
}}

QMenu::indicator {{
    width: 16px;
    height: 16px;
    margin-left: 6px;
}}

/* ===== Check Box ===== */
QCheckBox {{
    color: {c.text_primary};
    spacing: 8px;
    background-color: transparent;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {c.border};
    border-radius: 4px;
    background-color: {c.bg_secondary};
}}

QCheckBox::indicator:hover {{
    border-color: {c.accent};
}}

QCheckBox::indicator:checked {{
    background-color: {c.accent};
    border-color: {c.accent};
    image: none;
}}

QCheckBox::indicator:checked:hover {{
    background-color: {c.accent_hover};
    border-color: {c.accent_hover};
}}

QCheckBox::indicator:disabled {{
    background-color: {c.bg_tertiary};
    border-color: {c.bg_tertiary};
}}

/* ===== Radio Button ===== */
QRadioButton {{
    color: {c.text_primary};
    spacing: 8px;
    background-color: transparent;
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {c.border};
    border-radius: 11px;
    background-color: {c.bg_secondary};
}}

QRadioButton::indicator:hover {{
    border-color: {c.accent};
}}

QRadioButton::indicator:checked {{
    background-color: {c.accent};
    border-color: {c.accent};
}}

QRadioButton::indicator:checked:hover {{
    background-color: {c.accent_hover};
    border-color: {c.accent_hover};
}}

QRadioButton::indicator:disabled {{
    background-color: {c.bg_tertiary};
    border-color: {c.bg_tertiary};
}}
"""


# Default stylesheet (built from the default theme for backward compatibility)
STYLESHEET: str = build_stylesheet(THEMES[DEFAULT_THEME])

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
# Application styling helpers
# ---------------------------------------------------------------------------

def _build_palette(c: ThemeColors) -> QPalette:
    """Build a :class:`QPalette` matching the given theme colours."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(c.bg_primary))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(c.text_primary))
    palette.setColor(QPalette.ColorRole.Base, QColor(c.bg_secondary))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(c.bg_tertiary))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(c.bg_tertiary))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(c.text_primary))
    palette.setColor(QPalette.ColorRole.Text, QColor(c.text_primary))
    palette.setColor(QPalette.ColorRole.Button, QColor(c.bg_tertiary))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(c.text_primary))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(c.error))
    palette.setColor(QPalette.ColorRole.Link, QColor(c.accent_light))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(c.selection))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(c.text_primary))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(c.text_muted))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(c.text_muted),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(c.text_muted),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(c.text_muted),
    )
    return palette


def apply_style(app: QApplication) -> None:
    """Apply the default dark-purple theme stylesheet and palette to *app*."""
    apply_theme(app, DEFAULT_THEME)


def apply_theme(app: QApplication, theme_name: str) -> None:
    """Apply the named theme to *app* (stylesheet + palette + font).

    Also updates the module-level colour constants so that any code that
    re-reads them (e.g. via ``import opm_flow_gui.gui.styles as s; s.ACCENT``)
    will obtain the new values when refreshing widget stylesheets.
    """
    colors = THEMES.get(theme_name, THEMES[DEFAULT_THEME])

    # Update module-level colour constants so refresh_styles() calls can
    # pick up the new values without re-importing.
    _g = globals()
    _g["_active"] = colors
    _g["BG_PRIMARY"] = colors.bg_primary
    _g["BG_SECONDARY"] = colors.bg_secondary
    _g["BG_TERTIARY"] = colors.bg_tertiary
    _g["ACCENT"] = colors.accent
    _g["ACCENT_HOVER"] = colors.accent_hover
    _g["ACCENT_LIGHT"] = colors.accent_light
    _g["TEXT_PRIMARY"] = colors.text_primary
    _g["TEXT_SECONDARY"] = colors.text_secondary
    _g["TEXT_MUTED"] = colors.text_muted
    _g["SUCCESS"] = colors.success
    _g["WARNING"] = colors.warning
    _g["ERROR"] = colors.error
    _g["BORDER"] = colors.border
    _g["SELECTION"] = colors.selection
    _g["STYLESHEET"] = build_stylesheet(colors)
    _g["_STATUS_COLOURS"] = {
        "RUNNING": colors.accent,
        "COMPLETED": colors.success,
        "FAILED": colors.error,
        "CANCELLED": colors.warning,
        "PENDING": colors.text_muted,
    }

    if sys.platform == "darwin":
        font = QFont("Helvetica Neue", 13)
    elif sys.platform == "win32":
        font = QFont("Segoe UI", 10)
    else:
        font = app.font()
        font.setPointSize(10)
    app.setFont(font)

    app.setStyleSheet(build_stylesheet(colors))
    app.setPalette(_build_palette(colors))
