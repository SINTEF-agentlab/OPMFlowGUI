"""Log file viewer panel for OPM Flow PRT and DBG output files.

Provides a scrollable text view, full-text search, a step-navigation
sidebar and a warnings/notices summary panel at the bottom.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from opm_flow_gui.core.case_manager import SimulationRun

from opm_flow_gui.gui.styles import (
    ACCENT,
    BG_PRIMARY,
    BG_SECONDARY,
    BG_TERTIARY,
    BORDER,
    ERROR,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for parsing OPM Flow PRT/DBG files
# ---------------------------------------------------------------------------

# Report step header variations:
#   "Report step 1 ( 01 Jan 2024 ... )"
#   "====== Report step 1 ======"
#   "REPORT STEP 1"
_RE_STEP_HEADER = re.compile(
    r"(?:={3,}\s*)?[Rr]eport\s+[Ss]tep\s+(\d+)\s*(?:\(([^)]*)\))?",
    re.IGNORECASE,
)

# Warning/error/note lines
_RE_WARNING = re.compile(
    r"^\s*(?P<kind>Warning|Error|Note|Notice|Problem|[*]{3})\s*[:\-]?\s*(?P<msg>.+)",
    re.IGNORECASE,
)

# Time information on a step header line
_RE_DATE = re.compile(
    r"(\d{1,2}[/-]\w+[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\w+\s+\d{1,2}\s+\d{4})",
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StepInfo:
    number: int
    label: str           # e.g. "Step 1 – 01 Jan 2024"
    line_start: int      # 0-based line index in the file


@dataclass
class WarningEntry:
    step: int | None
    kind: str
    message: str
    line_number: int     # 1-based


# ---------------------------------------------------------------------------
# Syntax highlighter
# ---------------------------------------------------------------------------

class _LogHighlighter(QSyntaxHighlighter):
    """Highlights report-step headers, warnings and search matches."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._search_text: str = ""

        self._fmt_header = QTextCharFormat()
        self._fmt_header.setForeground(QColor(ACCENT))
        self._fmt_header.setFontWeight(700)

        self._fmt_warning = QTextCharFormat()
        self._fmt_warning.setForeground(QColor(WARNING))

        self._fmt_error = QTextCharFormat()
        self._fmt_error.setForeground(QColor(ERROR))

        self._fmt_search = QTextCharFormat()
        self._fmt_search.setBackground(QColor("#f59e0b"))
        self._fmt_search.setForeground(QColor("#1e1e2e"))

    def set_search(self, text: str) -> None:
        self._search_text = text
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        # Report step headers
        m = _RE_STEP_HEADER.search(text)
        if m:
            self.setFormat(0, len(text), self._fmt_header)
            return

        # Warnings / errors
        w = _RE_WARNING.match(text)
        if w:
            kind = w.group("kind").lower()
            fmt = self._fmt_error if "error" in kind else self._fmt_warning
            self.setFormat(0, len(text), fmt)

        # Search highlights (overlay on top of other formatting)
        if self._search_text:
            needle = self._search_text.lower()
            haystack = text.lower()
            start = 0
            while True:
                idx = haystack.find(needle, start)
                if idx == -1:
                    break
                self.setFormat(idx, len(self._search_text), self._fmt_search)
                start = idx + len(self._search_text)


# ---------------------------------------------------------------------------
# Log parser
# ---------------------------------------------------------------------------

def _parse_log(content: str) -> tuple[list[StepInfo], list[WarningEntry]]:
    """Parse *content* into steps and warnings.

    Returns a tuple of (steps, warnings).
    """
    steps: list[StepInfo] = []
    warnings: list[WarningEntry] = []
    current_step: int | None = None

    for lineno, line in enumerate(content.splitlines()):
        m = _RE_STEP_HEADER.search(line)
        if m:
            num = int(m.group(1))
            date_str = ""
            if m.group(2):
                date_str = m.group(2).strip()
            else:
                dm = _RE_DATE.search(line)
                if dm:
                    date_str = dm.group(1)
            label = f"Step {num}"
            if date_str:
                label += f"  {date_str}"
            steps.append(StepInfo(number=num, label=label, line_start=lineno))
            current_step = num
            continue

        w = _RE_WARNING.match(line)
        if w:
            kind = w.group("kind")
            msg = w.group("msg").strip()
            warnings.append(
                WarningEntry(
                    step=current_step,
                    kind=kind,
                    message=msg,
                    line_number=lineno + 1,
                )
            )

    return steps, warnings


# ---------------------------------------------------------------------------
# Log viewer panel
# ---------------------------------------------------------------------------

class LogViewerPanel(QWidget):
    """Panel for viewing, searching and navigating PRT/DBG log files."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_run: SimulationRun | None = None
        self._steps: list[StepInfo] = []
        self._warnings: list[WarningEntry] = []
        self._content: str = ""
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)

        self._setup_ui()
        self._connect_signals()
        self._show_empty_state()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- toolbar ---
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background-color: {BG_SECONDARY};")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(8, 6, 8, 6)
        tb.setSpacing(8)

        file_label = QLabel("File:")
        file_label.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        tb.addWidget(file_label)

        self._file_combo = QComboBox()
        self._file_combo.setMinimumWidth(200)
        self._file_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        tb.addWidget(self._file_combo)

        tb.addWidget(_separator())

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search log\u2026")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setMinimumWidth(180)
        self._search_edit.setStyleSheet(
            f"QLineEdit {{ padding: 4px 8px; border: 1px solid {BORDER};"
            f" border-radius: 4px; background-color: {BG_TERTIARY};"
            f" color: {TEXT_PRIMARY}; }}"
        )
        tb.addWidget(self._search_edit)

        self._btn_prev = self._make_nav_button("\u2191")
        self._btn_prev.setToolTip("Previous match")
        self._btn_next = self._make_nav_button("\u2193")
        self._btn_next.setToolTip("Next match")
        tb.addWidget(self._btn_prev)
        tb.addWidget(self._btn_next)

        self._match_label = QLabel("")
        self._match_label.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent; font-size: 11px;")
        tb.addWidget(self._match_label)

        tb.addStretch()

        self._btn_reload = self._make_toolbar_button("Reload")
        self._btn_reload.setToolTip("Reload the log file from disk")
        tb.addWidget(self._btn_reload)

        root.addWidget(toolbar)

        # --- main area: step list + text view ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setHandleWidth(3)

        # Left: step list
        step_pane = QWidget()
        step_layout = QVBoxLayout(step_pane)
        step_layout.setContentsMargins(0, 0, 0, 0)
        step_layout.setSpacing(0)

        steps_header = QLabel("Report Steps")
        steps_header.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {TEXT_PRIMARY};"
            f" padding: 6px 8px; background-color: {BG_SECONDARY};"
        )
        step_layout.addWidget(steps_header)

        self._step_list = QListWidget()
        self._step_list.setStyleSheet(
            f"QListWidget {{ background-color: {BG_SECONDARY}; border: none;"
            f" outline: none; font-size: 11px; }}"
            f" QListWidget::item {{ padding: 4px 8px;"
            f" border-bottom: 1px solid {BORDER}; }}"
            f" QListWidget::item:selected {{ background-color: {BG_TERTIARY}; }}"
            f" QListWidget::item:hover {{ background-color: {BG_TERTIARY}; }}"
        )
        step_layout.addWidget(self._step_list, 1)
        main_splitter.addWidget(step_pane)

        # Right: text view
        self._text_view = QPlainTextEdit()
        self._text_view.setReadOnly(True)
        self._text_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._text_view.setFont(_monospace_font())
        self._text_view.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {BG_PRIMARY};"
            f" color: {TEXT_PRIMARY}; border: none;"
            f" selection-background-color: {ACCENT}; }}"
        )
        self._highlighter = _LogHighlighter(self._text_view.document())
        main_splitter.addWidget(self._text_view)

        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 4)
        main_splitter.setSizes([160, 640])

        # --- bottom: warnings panel ---
        bottom_splitter = QSplitter(Qt.Orientation.Vertical)
        bottom_splitter.setHandleWidth(4)
        bottom_splitter.addWidget(main_splitter)

        warn_pane = QWidget()
        warn_layout = QVBoxLayout(warn_pane)
        warn_layout.setContentsMargins(0, 0, 0, 0)
        warn_layout.setSpacing(0)

        warn_header = QLabel("Warnings & Notices")
        warn_header.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {WARNING};"
            f" padding: 4px 8px; background-color: {BG_SECONDARY};"
        )
        warn_layout.addWidget(warn_header)

        self._warn_list = QListWidget()
        self._warn_list.setStyleSheet(
            f"QListWidget {{ background-color: {BG_SECONDARY}; border: none;"
            f" outline: none; font-size: 11px; }}"
            f" QListWidget::item {{ padding: 3px 8px;"
            f" border-bottom: 1px solid {BORDER}; }}"
            f" QListWidget::item:selected {{ background-color: {BG_TERTIARY}; }}"
            f" QListWidget::item:hover {{ background-color: {BG_TERTIARY}; }}"
        )
        warn_layout.addWidget(self._warn_list, 1)
        bottom_splitter.addWidget(warn_pane)

        bottom_splitter.setStretchFactor(0, 3)
        bottom_splitter.setStretchFactor(1, 1)
        bottom_splitter.setSizes([500, 150])

        root.addWidget(bottom_splitter, 1)

        # --- empty state ---
        self._empty_label = QLabel("Select a run to view log files")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 14px; background: transparent;"
        )
        root.addWidget(self._empty_label, 1)

        self._main_widget = bottom_splitter

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_toolbar_button(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ padding: 4px 10px; border-radius: 4px;"
            f" background-color: {BG_TERTIARY}; color: {TEXT_SECONDARY};"
            f" border: 1px solid {BORDER}; font-size: 12px; }}"
            f" QPushButton:hover {{ background-color: {ACCENT};"
            f" color: {TEXT_PRIMARY}; }}"
        )
        return btn

    @staticmethod
    def _make_nav_button(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedWidth(26)
        btn.setStyleSheet(
            f"QPushButton {{ padding: 2px 4px; border-radius: 4px;"
            f" background-color: {BG_TERTIARY}; color: {TEXT_SECONDARY};"
            f" border: 1px solid {BORDER}; font-size: 12px; }}"
            f" QPushButton:hover {{ background-color: {ACCENT};"
            f" color: {TEXT_PRIMARY}; }}"
        )
        return btn

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._file_combo.currentIndexChanged.connect(self._on_file_changed)
        self._step_list.currentRowChanged.connect(self._on_step_selected)
        self._warn_list.currentRowChanged.connect(self._on_warning_selected)
        self._search_edit.textChanged.connect(self._on_search_text_changed)
        self._search_timer.timeout.connect(self._apply_search)
        self._btn_prev.clicked.connect(self._find_prev)
        self._btn_next.clicked.connect(self._find_next)
        self._btn_reload.clicked.connect(self._reload_current_file)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_run(self, run: SimulationRun | None) -> None:
        """Load log files for *run*, or clear the panel when ``None``."""
        self._current_run = run
        self._file_combo.blockSignals(True)
        self._file_combo.clear()
        self._file_combo.blockSignals(False)
        self._steps.clear()
        self._warnings.clear()
        self._content = ""
        self._text_view.clear()
        self._step_list.clear()
        self._warn_list.clear()

        if run is None:
            self._show_empty_state()
            return

        out_dir = Path(run.output_dir)
        log_files: list[Path] = []

        for suffix in ("*.PRT", "*.DBG", "*.prt", "*.dbg"):
            log_files.extend(sorted(out_dir.glob(suffix)))

        # De-duplicate (case-insensitive on Windows)
        seen: set[str] = set()
        unique: list[Path] = []
        for p in log_files:
            key = str(p).lower()
            if key not in seen:
                seen.add(key)
                unique.append(p)
        log_files = unique

        if not log_files:
            self._show_empty_state()
            self._empty_label.setText(
                "No PRT or DBG files found in the output directory"
            )
            return

        self._main_widget.setVisible(True)
        self._empty_label.setVisible(False)

        self._file_combo.blockSignals(True)
        for p in log_files:
            self._file_combo.addItem(p.name, userData=str(p))
        self._file_combo.blockSignals(False)

        self._load_file(str(log_files[0]))

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------

    def _on_file_changed(self, index: int) -> None:
        path = self._file_combo.itemData(index)
        if path:
            self._load_file(path)

    def _reload_current_file(self) -> None:
        path = self._file_combo.currentData()
        if path:
            self._load_file(path)

    def _load_file(self, path: str) -> None:
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Could not read log file %s: %s", path, exc)
            self._text_view.setPlainText(f"Error reading file:\n{exc}")
            return

        self._content = content
        self._text_view.setPlainText(content)

        self._steps, self._warnings = _parse_log(content)
        self._populate_steps()
        self._populate_warnings()
        self._apply_search()

    # ------------------------------------------------------------------
    # Step navigation
    # ------------------------------------------------------------------

    def _populate_steps(self) -> None:
        self._step_list.clear()
        for step in self._steps:
            item = QListWidgetItem(step.label)
            item.setData(Qt.ItemDataRole.UserRole, step.line_start)
            self._step_list.addItem(item)

    def _on_step_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._steps):
            return
        line = self._steps[row].line_start
        self._scroll_to_line(line)

    def _scroll_to_line(self, line: int) -> None:
        block = self._text_view.document().findBlockByLineNumber(line)
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        self._text_view.setTextCursor(cursor)
        self._text_view.centerCursor()

    # ------------------------------------------------------------------
    # Warning navigation
    # ------------------------------------------------------------------

    def _populate_warnings(self) -> None:
        self._warn_list.clear()
        for entry in self._warnings:
            step_str = f"[Step {entry.step}] " if entry.step is not None else ""
            text = f"{step_str}{entry.kind}: {entry.message}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry.line_number - 1)
            if entry.kind.lower() in ("error", "***"):
                item.setForeground(QColor(ERROR))
            else:
                item.setForeground(QColor(WARNING))
            self._warn_list.addItem(item)

        if not self._warnings:
            item = QListWidgetItem("No warnings or errors detected")
            item.setForeground(QColor(TEXT_MUTED))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._warn_list.addItem(item)

    def _on_warning_selected(self, row: int) -> None:
        item = self._warn_list.item(row)
        if item is None:
            return
        line = item.data(Qt.ItemDataRole.UserRole)
        if line is not None:
            self._scroll_to_line(line)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_text_changed(self, _text: str) -> None:
        self._search_timer.start()

    def _apply_search(self) -> None:
        needle = self._search_edit.text()
        self._highlighter.set_search(needle)
        if needle:
            count = self._content.lower().count(needle.lower())
            self._match_label.setText(f"{count} match{'es' if count != 1 else ''}")
        else:
            self._match_label.setText("")

    def _find_next(self) -> None:
        needle = self._search_edit.text()
        if not needle:
            return
        flags = QTextDocument.FindFlag(0)
        if not self._text_view.find(needle, flags):
            # Wrap around
            cursor = self._text_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self._text_view.setTextCursor(cursor)
            self._text_view.find(needle, flags)

    def _find_prev(self) -> None:
        needle = self._search_edit.text()
        if not needle:
            return
        flags = QTextDocument.FindFlag.FindBackward
        if not self._text_view.find(needle, flags):
            cursor = self._text_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._text_view.setTextCursor(cursor)
            self._text_view.find(needle, flags)

    # ------------------------------------------------------------------
    # Empty state
    # ------------------------------------------------------------------

    def _show_empty_state(self) -> None:
        self._main_widget.setVisible(False)
        self._empty_label.setVisible(True)
        self._empty_label.setText("Select a run to view log files")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _separator() -> QWidget:
    sep = QWidget()
    sep.setFixedWidth(1)
    sep.setFixedHeight(20)
    sep.setStyleSheet(f"background-color: {BORDER};")
    return sep


def _monospace_font():
    """Return a platform-appropriate monospace QFont for log display."""
    from PySide6.QtGui import QFont
    import sys
    if sys.platform == "darwin":
        font = QFont("Menlo", 11)
    elif sys.platform == "win32":
        font = QFont("Consolas", 10)
    else:
        font = QFont("Monospace", 10)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font
