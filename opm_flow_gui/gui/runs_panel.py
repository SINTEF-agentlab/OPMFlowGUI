"""Middle panel displaying simulation runs for the currently selected case.

Shows each run as a card-like widget with run ID, status, progress bar,
MPI process count and a delete button.  Provides a "New Run" button for
launching additional simulations.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from opm_flow_gui.core.case_manager import Case, RunStatus, SimulationRun
from opm_flow_gui.gui.styles import (
    ACCENT,
    ACCENT_HOVER,
    BG_SECONDARY,
    BG_TERTIARY,
    BORDER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    get_status_color,
)


class RunItemWidget(QWidget):
    """Card-like widget representing a single simulation run."""

    delete_clicked = Signal(str)

    def __init__(self, run: SimulationRun, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._run_id = run.run_id

        # ---- outer card layout ----
        card = QVBoxLayout(self)
        card.setContentsMargins(10, 8, 10, 8)
        card.setSpacing(4)

        # ---- row 1: run id + date + delete button ----
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        short_id = run.run_id[:8]
        created = run.created_at[:19].replace("T", " ")

        id_label = QLabel(f"\u25b6 {short_id}")
        id_label.setStyleSheet(
            f"font-weight: bold; font-size: 13px; color: {TEXT_PRIMARY};"
            " background: transparent;"
        )
        id_label.setToolTip(run.run_id)
        top_row.addWidget(id_label)

        date_label = QLabel(created)
        date_label.setStyleSheet(
            f"font-size: 11px; color: {TEXT_MUTED}; background: transparent;"
        )
        top_row.addWidget(date_label)

        top_row.addStretch()

        self._btn_delete = QPushButton("Delete")
        self._btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_delete.setFixedHeight(22)
        self._btn_delete.setStyleSheet(
            f"QPushButton {{ padding: 2px 8px; border-radius: 3px;"
            f" background-color: transparent; color: {TEXT_MUTED};"
            f" border: 1px solid {BORDER}; font-size: 11px; }}"
            f" QPushButton:hover {{ background-color: #dc2626;"
            f" color: {TEXT_PRIMARY}; border-color: #dc2626; }}"
        )
        self._btn_delete.clicked.connect(lambda: self.delete_clicked.emit(self._run_id))
        top_row.addWidget(self._btn_delete)

        card.addLayout(top_row)

        # ---- row 2: status + MPI badge ----
        info_row = QHBoxLayout()
        info_row.setSpacing(8)

        status_text = run.status.value.upper()
        status_color = get_status_color(status_text)

        self._status_label = QLabel(status_text)
        self._status_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {status_color};"
            " background: transparent;"
        )
        info_row.addWidget(self._status_label)

        mpi_label = QLabel(f"MPI: {run.mpi_processes}")
        mpi_label.setStyleSheet(
            f"font-size: 11px; color: {TEXT_SECONDARY}; background: transparent;"
        )
        info_row.addWidget(mpi_label)

        info_row.addStretch()
        card.addLayout(info_row)

        # ---- row 3: progress bar ----
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(int(run.progress))
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: {BG_TERTIARY};"
            f" border: none; border-radius: 3px; }}"
            f" QProgressBar::chunk {{ background-color: {ACCENT};"
            f" border-radius: 3px; }}"
        )

        is_visible = run.status == RunStatus.RUNNING or run.progress > 0
        self._progress_bar.setVisible(is_visible)
        card.addWidget(self._progress_bar)

        self.setStyleSheet("background: transparent;")

    # -- public helpers for live updates --

    def set_progress(self, progress: float) -> None:
        """Update the progress bar value and ensure it is visible."""
        self._progress_bar.setValue(int(progress))
        if progress > 0:
            self._progress_bar.setVisible(True)

    def set_status(self, status: str) -> None:
        """Update the status label text and colour."""
        upper = status.upper()
        color = get_status_color(upper)
        self._status_label.setText(upper)
        self._status_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {color};"
            " background: transparent;"
        )
        # Show progress bar when running
        if upper == "RUNNING":
            self._progress_bar.setVisible(True)

    @property
    def run_id(self) -> str:
        return self._run_id


class RunsPanel(QWidget):
    """Middle panel that lists simulation runs for the selected case."""

    run_selected = Signal(str)
    run_deleted = Signal(str, str)
    new_run_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_case: Case | None = None
        self._run_widgets: dict[str, RunItemWidget] = {}
        self._setup_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- header ---
        header = QLabel("Simulation Runs")
        header.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {TEXT_PRIMARY};"
            f" padding: 12px 12px 8px 12px; background-color: {BG_SECONDARY};"
        )
        layout.addWidget(header)

        # --- new-run button ---
        btn_bar = QWidget()
        btn_bar.setStyleSheet(f"background-color: {BG_SECONDARY};")
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(8, 4, 8, 8)

        self._btn_new_run = QPushButton("+ New Run")
        self._btn_new_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_new_run.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed,
        )
        self._btn_new_run.setStyleSheet(
            f"QPushButton {{ padding: 8px 16px; border-radius: 6px;"
            f" background-color: {ACCENT}; color: {TEXT_PRIMARY};"
            f" font-size: 13px; font-weight: bold; border: none; }}"
            f" QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}"
            f" QPushButton:disabled {{ background-color: {BG_TERTIARY};"
            f" color: {TEXT_MUTED}; }}"
        )
        self._btn_new_run.setEnabled(False)
        btn_layout.addWidget(self._btn_new_run)
        layout.addWidget(btn_bar)

        # --- run list ---
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

        # --- empty state label ---
        self._empty_label = QLabel("Select a case to view runs")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 13px; background: transparent;"
        )
        layout.addWidget(self._empty_label, 1)

        # Initially show empty state
        self._list.setVisible(False)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._btn_new_run.clicked.connect(self.new_run_requested.emit)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_case(self, case: Case | None) -> None:
        """Switch the panel to display runs for *case*, or clear if ``None``."""
        self._current_case = case
        self._btn_new_run.setEnabled(case is not None)
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the run list from the current case."""
        self._list.clear()
        self._run_widgets.clear()

        if self._current_case is None or not self._current_case.runs:
            self._list.setVisible(self._current_case is not None and bool(self._current_case.runs))
            self._empty_label.setVisible(self._current_case is None or not self._current_case.runs)
            if self._current_case is not None:
                self._empty_label.setText("No runs yet \u2014 click New Run to start")
            else:
                self._empty_label.setText("Select a case to view runs")
            return

        self._list.setVisible(True)
        self._empty_label.setVisible(False)

        for run in reversed(self._current_case.runs):
            widget = self._create_run_widget(run)
            item = QListWidgetItem(self._list)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, run.run_id)
            self._list.setItemWidget(item, widget)

    def update_run_progress(self, run_id: str, progress: float) -> None:
        """Update the progress bar for *run_id* without a full refresh."""
        widget = self._run_widgets.get(run_id)
        if widget is not None:
            widget.set_progress(progress)

    def update_run_status(self, run_id: str, status: str) -> None:
        """Update the status display for *run_id* without a full refresh."""
        widget = self._run_widgets.get(run_id)
        if widget is not None:
            widget.set_status(status)

    # ------------------------------------------------------------------
    # Slot implementations
    # ------------------------------------------------------------------
    def _on_selection_changed(self) -> None:
        """Emit *run_selected* with the run-id of the newly selected row."""
        item = self._list.currentItem()
        if item is not None:
            run_id: str = item.data(Qt.ItemDataRole.UserRole)
            self.run_selected.emit(run_id)

    def _on_delete_clicked(self, run_id: str) -> None:
        """Emit *run_deleted* with the case path and run id."""
        if self._current_case is not None:
            self.run_deleted.emit(self._current_case.data_file_path, run_id)

    # ------------------------------------------------------------------
    # Widget factory
    # ------------------------------------------------------------------
    def _create_run_widget(self, run: SimulationRun) -> RunItemWidget:
        """Create and register a :class:`RunItemWidget` for *run*."""
        widget = RunItemWidget(run, parent=self._list)
        widget.delete_clicked.connect(self._on_delete_clicked)
        self._run_widgets[run.run_id] = widget
        return widget
