"""Left-hand panel listing simulation cases (.DATA files).

Displays each case with its name, directory path and a run-count badge.
Provides controls for adding individual files, scanning folders and removing
cases, as well as a live filter field.  Double-clicking a case opens its
directory in the system file manager.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QMouseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from opm_flow_gui.core.case_manager import Case, CaseManager
from opm_flow_gui.gui.styles import (
    ACCENT,
    BG_SECONDARY,
    BG_TERTIARY,
    BORDER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class _ClickableHeader(QLabel):
    """QLabel that emits a ``clicked`` signal on mouse press."""

    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mousePressEvent(event)
        self.clicked.emit()


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

        # ---- left column: name + path ----
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(2)

        name_label = QLabel(case.name)
        name_label.setStyleSheet(
            f"font-weight: bold; font-size: 13px; color: {TEXT_PRIMARY};"
            " background: transparent;"
        )
        left.addWidget(name_label)

        path_label = _ElidingLabel(case.directory)
        path_label.setStyleSheet(
            f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;"
        )
        path_label.setToolTip(case.directory)
        path_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        left.addWidget(path_label)

        # ---- right column: run-count badge ----
        run_count = len(case.runs)
        badge_text = f"{run_count} run{'s' if run_count != 1 else ''}"
        badge = QLabel(badge_text)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background-color: {ACCENT}; color: {TEXT_PRIMARY};"
            " border-radius: 8px; font-size: 11px; font-weight: bold;"
            " padding: 2px 8px;"
        )
        badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # ---- assemble ----
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        row.addLayout(left, 1)
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.setStyleSheet("background: transparent;")


class CasePanel(QWidget):
    """Left panel displaying the list of loaded simulation cases."""

    case_selected = Signal(str)
    expand_requested = Signal()  # emitted when the collapsed header is clicked

    def __init__(
        self,
        case_manager: CaseManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._case_manager = case_manager
        self.setMinimumWidth(180)
        self._setup_ui()
        self._connect_signals()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- header (click to expand when collapsed) ---
        self._header = _ClickableHeader("Cases ▶")
        self._header.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {TEXT_PRIMARY};"
            f" padding: 12px 12px 8px 12px; background-color: {BG_SECONDARY};"
            " cursor: pointer;"
        )
        self._header.setAccessibleDescription(
            "Cases panel header – click to expand the panel when it is collapsed"
        )
        self._header.clicked.connect(self.expand_requested)
        layout.addWidget(self._header)

        # --- search / filter ---
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter cases\u2026")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.setStyleSheet(
            f"QLineEdit {{ margin: 6px 8px; padding: 6px 10px;"
            f" border: 1px solid {BORDER}; border-radius: 6px;"
            f" background-color: {BG_TERTIARY}; color: {TEXT_PRIMARY}; }}"
        )
        layout.addWidget(self._filter_edit)

        # --- toolbar row ---
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background-color: {BG_SECONDARY};")
        tb_layout = QHBoxLayout(toolbar)
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

        hint = QLabel("Double-click to open folder")
        hint.setStyleSheet(
            f"font-size: 10px; color: {TEXT_MUTED}; background: transparent;"
        )
        tb_layout.addWidget(hint)

        layout.addWidget(toolbar)

        # --- case list ---
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.setStyleSheet(
            f"QListWidget {{ background-color: {BG_SECONDARY}; border: none;"
            f" outline: none; }}"
            f" QListWidget::item {{ border-bottom: 1px solid {BORDER}; }}"
            f" QListWidget::item:selected {{ background-color: {BG_TERTIARY}; }}"
            f" QListWidget::item:hover {{ background-color: {BG_TERTIARY}; }}"
        )
        layout.addWidget(self._list, 1)

    @staticmethod
    def _make_button(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet(
            f"QPushButton {{ padding: 4px 8px; border-radius: 4px;"
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
