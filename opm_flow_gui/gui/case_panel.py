"""Left-hand panel listing simulation cases (.DATA files).

Displays each case with its name, directory path and a run-count badge.
Provides controls for adding individual files, scanning folders and removing
cases, as well as a live filter field.  Double-clicking a case opens its
directory in the system file manager.
"""

from __future__ import annotations

import base64
from pathlib import Path

from PySide6.QtCore import Qt, QByteArray, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QMouseEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from opm_flow_gui.core.case_manager import Case, CaseManager
import opm_flow_gui.gui.styles as _styles

# ---------------------------------------------------------------------------
# OPM compact logo – 28 × 28 px PNG with transparent background, embedded as
# base64 so the package ships without any separate asset file.
# ---------------------------------------------------------------------------
_OPM_LOGO_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABwAAAAcCAYAAAByDd+UAAAA6klEQVR4nM2WTRLCMAiFseMR"
    "6g08mi7qgXRRj+YN2kO4SiZSfh6Vib5dG8hXCCUQddYhYjxe7i/p/fq8ndOAGkSTBx8yYYiP"
    "GOEekCQp2g3Qgi3ztErvT9fHiEKP9jfaIL5ugYs+IpSia2Hahp5NG2Utmr0wviZlo91brVIU"
    "hkJdYAQWsR2ItumMFIEG5VEWBlSlXMs8tYCQr5tSCyY9pwO/1f8D+ZlFz7B2mqxK1fxKt3Ej"
    "9Ppo1FYFop1DsrGyUoHS3YVCI80bug/RtHowIrDTaO3KAmn6/YiRAbYmN/O3iMybqE/3Qbi7"
    "3qxcmQXOfEYQAAAAAElFTkSuQmCC"
)


def _opm_logo_pixmap(height: int = 20) -> QPixmap:
    """Return a QPixmap of the OPM logo scaled to *height* pixels."""
    raw = QByteArray(base64.b64decode(_OPM_LOGO_B64))
    pixmap = QPixmap()
    pixmap.loadFromData(raw, "PNG")
    if not pixmap.isNull():
        pixmap = pixmap.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)
    return pixmap


class _ClickableHeader(QLabel):
    """QLabel that emits a ``clicked`` signal on mouse press."""

    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mousePressEvent(event)
        self.clicked.emit()


class _CollapsedBar(QWidget):
    """Narrow vertical strip shown when the cases panel is collapsed.

    Clicking the strip emits :attr:`clicked` which the parent panel
    connects to its :attr:`~CasePanel.expand_requested` signal.
    """

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._btn = QPushButton("▶")
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setToolTip("Click to expand the Cases panel")
        self._btn.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        self._btn.setStyleSheet(
            f"QPushButton {{ background-color: {_styles.BG_TERTIARY};"
            f" color: {_styles.ACCENT}; border: none;"
            f" border-right: 3px solid {_styles.ACCENT};"
            f" border-radius: 0; font-size: 16px; font-weight: bold; }}"
            f" QPushButton:hover {{ background-color: {_styles.ACCENT}; color: #ffffff; }}"
        )
        self._btn.clicked.connect(self.clicked)
        layout.addWidget(self._btn)

    def refresh_styles(self) -> None:
        self._btn.setStyleSheet(
            f"QPushButton {{ background-color: {_styles.BG_TERTIARY};"
            f" color: {_styles.ACCENT}; border: none;"
            f" border-right: 3px solid {_styles.ACCENT};"
            f" border-radius: 0; font-size: 16px; font-weight: bold; }}"
            f" QPushButton:hover {{ background-color: {_styles.ACCENT}; color: #ffffff; }}"
        )


class _ElidingLabel(QLabel):
    """QLabel that automatically elides its text when resized."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = text
        super().setText(text)

    def setText(self, text: str) -> None:  # type: ignore[override]
        self._full_text = text
        self._update_elided()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_elided()

    def _update_elided(self) -> None:
        fm = self.fontMetrics()
        available = max(self.width() - 4, 1)
        elided = fm.elidedText(self._full_text, Qt.TextElideMode.ElideMiddle, available)
        super().setText(elided)


class _CaseItemWidget(QWidget):
    """Custom widget rendered for each case row in the list."""

    def __init__(self, case: Case, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        run_count = len(case.runs)

        # ---- left column: run-count badge (only when at least one run) ----
        # Placed first so it appears at the far-left edge and is always visible.
        self._badge: QLabel | None = None
        if run_count > 0:
            badge_text = f"{run_count}"
            badge = QLabel(badge_text)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"background-color: {_styles.ACCENT}; color: {_styles.TEXT_PRIMARY};"
                " border-radius: 8px; font-size: 11px; font-weight: bold;"
                " padding: 2px 6px; min-width: 18px;"
            )
            badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self._badge = badge

        # ---- right column: name + path ----
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(4)

        name_label = QLabel(case.name)
        name_label.setStyleSheet(
            f"font-weight: bold; font-size: 13px; color: {_styles.TEXT_PRIMARY};"
            " background: transparent;"
        )
        right.addWidget(name_label)

        path_label = _ElidingLabel(case.directory)
        path_label.setStyleSheet(
            f"font-size: 11px; color: {_styles.TEXT_MUTED}; background: transparent;"
        )
        path_label.setToolTip(case.directory)
        path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        right.addWidget(path_label)

        # ---- assemble ----
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 8, 8, 8)
        row.setSpacing(8)
        if self._badge is not None:
            row.addWidget(
                self._badge,
                0,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
        row.addLayout(right, 1)

        self.setStyleSheet("background: transparent;")


class CasePanel(QWidget):
    """Left panel displaying the list of loaded simulation cases."""

    # Width (pixels) the panel is shrunk to when collapsed programmatically
    COLLAPSED_WIDTH: int = 32

    case_selected = Signal(str)
    expand_requested = Signal()  # emitted when the collapsed header is clicked

    def __init__(
        self,
        case_manager: CaseManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._case_manager = case_manager
        # Allow the panel to be squeezed to the narrow collapsed bar
        self.setMinimumWidth(self.COLLAPSED_WIDTH)
        self._setup_ui()
        self._connect_signals()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # QStackedWidget lets us switch between the narrow collapsed bar
        # (index 0) and the full panel content (index 1).
        self._stacked = QStackedWidget()

        # ── index 0: narrow collapsed bar ─────────────────────────────
        self._collapsed_bar = _CollapsedBar()
        self._collapsed_bar.clicked.connect(self.expand_requested)
        self._stacked.addWidget(self._collapsed_bar)

        # ── index 1: full panel content ────────────────────────────────
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # --- header (click to expand when collapsed) ---
        header_widget = QWidget()
        header_widget.setStyleSheet(f"background-color: {_styles.BG_SECONDARY};")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(8)

        self._logo_label = QLabel()
        pixmap = _opm_logo_pixmap(20)
        if not pixmap.isNull():
            self._logo_label.setPixmap(pixmap)
        self._logo_label.setFixedSize(24, 24)
        self._logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo_label.setStyleSheet("background: transparent;")
        header_layout.addWidget(self._logo_label)

        self._header = _ClickableHeader("Cases ▶")
        self._header.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {_styles.TEXT_PRIMARY};"
            f" background-color: {_styles.BG_SECONDARY};"
        )
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setAccessibleDescription(
            "Cases panel header – click to expand the panel when it is collapsed"
        )
        self._header.clicked.connect(self.expand_requested)
        header_layout.addWidget(self._header, 1)

        content_layout.addWidget(header_widget)

        # --- search / filter ---
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter cases\u2026")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.setStyleSheet(
            f"QLineEdit {{ margin: 6px 8px; padding: 6px 10px;"
            f" border: 1px solid {_styles.BORDER}; border-radius: 6px;"
            f" background-color: {_styles.BG_TERTIARY}; color: {_styles.TEXT_PRIMARY}; }}"
        )
        content_layout.addWidget(self._filter_edit)

        # --- toolbar row ---
        self._toolbar = QWidget()
        self._toolbar.setStyleSheet(f"background-color: {_styles.BG_SECONDARY};")
        tb_layout = QHBoxLayout(self._toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(4)

        self._btn_add = self._make_button("Add")
        self._btn_add.setToolTip("Add a .DATA case file")
        self._btn_scan = self._make_button("Scan")
        self._btn_scan.setToolTip("Scan a folder for .DATA files")
        self._btn_remove = self._make_button("Remove")
        self._btn_remove.setToolTip("Remove selected case from the list")

        tb_layout.addWidget(self._btn_add)
        tb_layout.addWidget(self._btn_scan)
        tb_layout.addWidget(self._btn_remove)
        tb_layout.addStretch()

        self._hint_label = QLabel("Double-click to open folder")
        self._hint_label.setStyleSheet(
            f"font-size: 10px; color: {_styles.TEXT_MUTED}; background: transparent;"
        )
        tb_layout.addWidget(self._hint_label)

        content_layout.addWidget(self._toolbar)

        # --- case list ---
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.setStyleSheet(
            f"QListWidget {{ background-color: {_styles.BG_SECONDARY}; border: none;"
            f" outline: none; }}"
            f" QListWidget::item {{ border-bottom: 1px solid {_styles.BORDER}; }}"
            f" QListWidget::item:selected {{ background-color: {_styles.BG_TERTIARY}; }}"
            f" QListWidget::item:hover {{ background-color: {_styles.BG_TERTIARY}; }}"
        )
        content_layout.addWidget(self._list, 1)

        self._stacked.addWidget(content_widget)

        # Start with full content visible
        self._stacked.setCurrentIndex(1)
        outer.addWidget(self._stacked)

    @staticmethod
    def _make_button(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet(
            f"QPushButton {{ padding: 4px 8px; border-radius: 4px;"
            f" background-color: {_styles.BG_TERTIARY}; color: {_styles.TEXT_SECONDARY};"
            f" border: 1px solid {_styles.BORDER}; font-size: 12px; }}"
            f" QPushButton:hover {{ background-color: {_styles.ACCENT};"
            f" color: {_styles.TEXT_PRIMARY}; }}"
        )
        return btn

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """Switch between the collapsed bar and full content based on width."""
        super().resizeEvent(event)
        target = 0 if self.width() <= self.COLLAPSED_WIDTH + 10 else 1
        if self._stacked.currentIndex() != target:
            self._stacked.setCurrentIndex(target)

    def refresh_styles(self) -> None:
        """Re-apply inline stylesheets using the current active theme colours."""
        self._collapsed_bar.refresh_styles()

        # Header widget background
        header_widget = self._header.parentWidget()
        if header_widget is not None:
            header_widget.setStyleSheet(f"background-color: {_styles.BG_SECONDARY};")
        self._header.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {_styles.TEXT_PRIMARY};"
            f" background-color: {_styles.BG_SECONDARY};"
        )
        self._filter_edit.setStyleSheet(
            f"QLineEdit {{ margin: 6px 8px; padding: 6px 10px;"
            f" border: 1px solid {_styles.BORDER}; border-radius: 6px;"
            f" background-color: {_styles.BG_TERTIARY}; color: {_styles.TEXT_PRIMARY}; }}"
        )
        self._toolbar.setStyleSheet(f"background-color: {_styles.BG_SECONDARY};")
        for btn in (self._btn_add, self._btn_scan, self._btn_remove):
            btn.setStyleSheet(
                f"QPushButton {{ padding: 4px 8px; border-radius: 4px;"
                f" background-color: {_styles.BG_TERTIARY}; color: {_styles.TEXT_SECONDARY};"
                f" border: 1px solid {_styles.BORDER}; font-size: 12px; }}"
                f" QPushButton:hover {{ background-color: {_styles.ACCENT};"
                f" color: {_styles.TEXT_PRIMARY}; }}"
            )
        self._hint_label.setStyleSheet(
            f"font-size: 10px; color: {_styles.TEXT_MUTED}; background: transparent;"
        )
        self._list.setStyleSheet(
            f"QListWidget {{ background-color: {_styles.BG_SECONDARY}; border: none;"
            f" outline: none; }}"
            f" QListWidget::item {{ border-bottom: 1px solid {_styles.BORDER}; }}"
            f" QListWidget::item:selected {{ background-color: {_styles.BG_TERTIARY}; }}"
            f" QListWidget::item:hover {{ background-color: {_styles.BG_TERTIARY}; }}"
        )

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self._btn_add.clicked.connect(self._add_case_file)
        self._btn_scan.clicked.connect(self._scan_folder)
        self._btn_remove.clicked.connect(self._remove_selected)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._filter_edit.textChanged.connect(self._filter_cases)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Rebuild the list widget from the current case manager state."""
        # Preserve the currently selected case path so we can re-select after rebuild.
        current_item = self._list.currentItem()
        selected_path: str | None = (
            current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        )

        self._list.clear()
        for case in self._case_manager.get_all_cases():
            widget = self._create_case_widget(case)
            item = QListWidgetItem(self._list)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, case.data_file_path)
            self._list.setItemWidget(item, widget)

        # Re-apply active filter
        self._filter_cases(self._filter_edit.text())

        # Restore the previous selection without emitting a spurious signal.
        if selected_path is not None:
            for idx in range(self._list.count()):
                item = self._list.item(idx)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == selected_path:
                    self._list.blockSignals(True)
                    self._list.setCurrentItem(item)
                    self._list.blockSignals(False)
                    break

    # ------------------------------------------------------------------
    # Slot implementations
    # ------------------------------------------------------------------
    def _add_case_file(self) -> None:
        """Open a file dialog for selecting a .DATA file."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select .DATA File",
            "",
            "OPM DATA Files (*.DATA);;All Files (*)",
        )
        if path:
            self._case_manager.add_case(path)
            self.refresh()

    def _scan_folder(self) -> None:
        """Open a folder dialog, then discover all .DATA files inside."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Scan",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if directory:
            self._case_manager.discover_cases(directory)
            self.refresh()

    def _remove_selected(self) -> None:
        """Remove the currently selected case from the manager and list."""
        item = self._list.currentItem()
        if item is None:
            return
        data_path: str = item.data(Qt.ItemDataRole.UserRole)
        self._case_manager.remove_case(data_path)
        self.refresh()

    def _on_selection_changed(self) -> None:
        """Emit *case_selected* with the data-file path of the new selection."""
        item = self._list.currentItem()
        if item is not None:
            data_path: str = item.data(Qt.ItemDataRole.UserRole)
            self.case_selected.emit(data_path)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Open the case's directory in the system file manager."""
        data_path: str = item.data(Qt.ItemDataRole.UserRole)
        directory = str(Path(data_path).parent)
        QDesktopServices.openUrl(QUrl.fromLocalFile(directory))

    def _filter_cases(self, text: str) -> None:
        """Show only items whose case name contains *text* (case-insensitive)."""
        needle = text.lower()
        for idx in range(self._list.count()):
            item = self._list.item(idx)
            data_path: str = item.data(Qt.ItemDataRole.UserRole)
            case_name = Path(data_path).stem.lower()
            item.setHidden(needle not in case_name)

    # ------------------------------------------------------------------
    # Widget factory
    # ------------------------------------------------------------------
    def _create_case_widget(self, case: Case) -> QWidget:
        """Return a custom widget for a single case list entry."""
        return _CaseItemWidget(case, parent=self._list)
