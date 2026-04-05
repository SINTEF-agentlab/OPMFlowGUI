"""Middle panel displaying simulation runs for the currently selected case.

Shows each run as a card-like widget with run ID, status, progress bar,
MPI process count, notes and delete/notes buttons.  Provides a "New Run"
button for launching additional simulations.
"""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from opm_flow_gui.core.case_manager import Case, RunStatus, SimulationRun
import opm_flow_gui.gui.styles as _styles


def _format_elapsed(started_at: str, finished_at: str | None = None) -> str:
    """Return a human-readable elapsed-time string between two ISO timestamps.

    If *finished_at* is ``None`` the elapsed time up to *now* is returned.
    Both timestamps are treated as local/naive time; any trailing timezone
    offset is stripped before parsing.
    """
    try:
        # Strip optional timezone suffix (e.g. "+00:00" or "Z") so that
        # parsing is always timezone-naive and consistent with datetime.now().
        def _strip_tz(ts: str) -> str:
            for sep in ("+", "Z"):
                idx = ts.find(sep, 10)  # avoid matching sign in time portion
                if idx != -1:
                    ts = ts[:idx]
            return ts[:26]

        fmt_s = "%Y-%m-%dT%H:%M:%S.%f" if "." in started_at else "%Y-%m-%dT%H:%M:%S"
        start = datetime.strptime(_strip_tz(started_at), fmt_s)
        if finished_at:
            fmt_e = "%Y-%m-%dT%H:%M:%S.%f" if "." in finished_at else "%Y-%m-%dT%H:%M:%S"
            end = datetime.strptime(_strip_tz(finished_at), fmt_e)
        else:
            end = datetime.now()
        delta = int((end - start).total_seconds())
        hours, remainder = divmod(max(delta, 0), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes:02d}m {seconds:02d}s"
        if minutes:
            return f"{minutes}m {seconds:02d}s"
        return f"{seconds}s"
    except Exception:  # noqa: BLE001
        return "unknown"


class RunItemWidget(QWidget):
    """Card-like widget representing a single simulation run."""

    delete_clicked = Signal(str)   # run_id
    stop_clicked = Signal(str)     # run_id
    notes_saved = Signal(str)      # run_id (notes already written to run object)

    def __init__(self, run: SimulationRun, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._run_id = run.run_id
        self._run = run

        # ---- outer card layout ----
        card = QVBoxLayout(self)
        card.setContentsMargins(10, 8, 10, 8)
        card.setSpacing(4)

        # ---- row 1: run id + date + action buttons ----
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        short_id = run.run_id[:8]
        created = run.created_at[:19].replace("T", " ")

        # If a human-readable name was set, display it; otherwise fall back to short ID
        display_name = run.name if run.name else f"\u25b6 {short_id}"
        id_label = QLabel(display_name)
        id_label.setStyleSheet(
            f"font-weight: bold; font-size: 13px; color: {_styles.TEXT_PRIMARY};"
            " background: transparent;"
        )
        id_label.setToolTip(run.run_id)
        top_row.addWidget(id_label)

        date_label = QLabel(created)
        date_label.setStyleSheet(
            f"font-size: 11px; color: {_styles.TEXT_MUTED}; background: transparent;"
        )
        top_row.addWidget(date_label)

        top_row.addStretch()

        self._btn_notes = QPushButton("\U0001f4dd")
        self._btn_notes.setToolTip("Add/edit notes for this run")
        self._btn_notes.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_notes.setFixedHeight(22)
        self._btn_notes.setFixedWidth(28)
        self._btn_notes.setStyleSheet(
            f"QPushButton {{ padding: 2px 4px; border-radius: 3px;"
            f" background-color: transparent; color: {_styles.TEXT_MUTED};"
            f" border: 1px solid {_styles.BORDER}; font-size: 13px; }}"
            f" QPushButton:hover {{ background-color: {_styles.BG_TERTIARY};"
            f" color: {_styles.TEXT_PRIMARY}; }}"
        )
        self._btn_notes.clicked.connect(self._edit_notes)
        top_row.addWidget(self._btn_notes)

        self._btn_stop = QPushButton("Stop")
        self._btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_stop.setFixedHeight(22)
        self._btn_stop.setToolTip("Stop this running simulation")
        self._btn_stop.setStyleSheet(
            f"QPushButton {{ padding: 2px 8px; border-radius: 3px;"
            f" background-color: transparent; color: {_styles.ERROR};"
            f" border: 1px solid {_styles.ERROR}; font-size: 11px; }}"
            f" QPushButton:hover {{ background-color: {_styles.ERROR};"
            f" color: {_styles.TEXT_PRIMARY}; border-color: {_styles.ERROR}; }}"
        )
        self._btn_stop.clicked.connect(lambda: self.stop_clicked.emit(self._run_id))
        self._btn_stop.setVisible(run.status == RunStatus.RUNNING)
        top_row.addWidget(self._btn_stop)

        self._btn_delete = QPushButton("Delete")
        self._btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_delete.setFixedHeight(22)
        self._btn_delete.setStyleSheet(
            f"QPushButton {{ padding: 2px 8px; border-radius: 3px;"
            f" background-color: transparent; color: {_styles.TEXT_MUTED};"
            f" border: 1px solid {_styles.BORDER}; font-size: 11px; }}"
            f" QPushButton:hover {{ background-color: #dc2626;"
            f" color: {_styles.TEXT_PRIMARY}; border-color: #dc2626; }}"
        )
        self._btn_delete.clicked.connect(lambda: self.delete_clicked.emit(self._run_id))
        top_row.addWidget(self._btn_delete)

        card.addLayout(top_row)

        # ---- row 2: status + MPI badge ----
        info_row = QHBoxLayout()
        info_row.setSpacing(8)

        status_text = run.status.value.upper()
        status_color = _styles.get_status_color(status_text)

        self._status_label = QLabel(status_text)
        self._status_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {status_color};"
            " background: transparent;"
        )
        info_row.addWidget(self._status_label)

        mpi_label = QLabel(f"MPI: {run.mpi_processes}")
        mpi_label.setStyleSheet(
            f"font-size: 11px; color: {_styles.TEXT_SECONDARY}; background: transparent;"
        )
        info_row.addWidget(mpi_label)

        info_row.addStretch()
        card.addLayout(info_row)

        # ---- row 3: notes preview ----
        self._notes_label = QLabel(run.notes if run.notes else "")
        self._notes_label.setStyleSheet(
            f"font-size: 11px; color: {_styles.TEXT_MUTED}; background: transparent;"
            " font-style: italic;"
        )
        self._notes_label.setWordWrap(True)
        self._notes_label.setVisible(bool(run.notes))
        card.addWidget(self._notes_label)

        # ---- row 4: progress bar ----
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(int(run.progress))
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: {_styles.BG_TERTIARY};"
            f" border: none; border-radius: 3px;"
            f" min-height: 6px; max-height: 6px; }}"
            f" QProgressBar::chunk {{ background-color: {_styles.ACCENT};"
            f" border-radius: 3px; }}"
        )

        is_visible = run.status == RunStatus.RUNNING or run.progress > 0
        self._progress_bar.setVisible(is_visible)
        card.addWidget(self._progress_bar)

        self.setStyleSheet("background: transparent;")

        # Set initial rich tooltip
        self._refresh_tooltip()

    # -- public helpers for live updates --

    def set_progress(self, progress: float) -> None:
        """Update the progress bar value and ensure it is visible."""
        self._progress_bar.setValue(int(progress))
        if progress > 0:
            self._progress_bar.setVisible(True)
        self._refresh_tooltip()

    def set_status(self, status: str) -> None:
        """Update the status label text and colour."""
        upper = status.upper()
        color = _styles.get_status_color(upper)
        self._status_label.setText(upper)
        self._status_label.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {color};"
            " background: transparent;"
        )
        # Show/hide stop button and progress bar based on status
        is_running = upper == "RUNNING"
        self._btn_stop.setVisible(is_running)
        if is_running:
            self._progress_bar.setVisible(True)
        self._refresh_tooltip()

    @property
    def run_id(self) -> str:
        return self._run_id

    # -- internal --

    def _edit_notes(self) -> None:
        """Open a text input dialog to edit the run notes."""
        new_notes, ok = QInputDialog.getMultiLineText(
            self,
            "Run Notes",
            f"Notes for run {self._run_id[:8]}:",
            self._run.notes,
        )
        if ok:
            self._run.notes = new_notes
            self._notes_label.setText(new_notes)
            self._notes_label.setVisible(bool(new_notes))
            self.notes_saved.emit(self._run_id)
            self._refresh_tooltip()

    def _refresh_tooltip(self) -> None:
        """Build and set a rich HTML tooltip summarising the run."""
        run = self._run
        lines: list[str] = [
            f"<b>Run ID:</b> {run.run_id}",
            f"<b>Case:</b> {run.case_path}",
            f"<b>Output:</b> {run.output_dir}",
            f"<b>Status:</b> {run.status.value}",
            f"<b>MPI processes:</b> {run.mpi_processes}",
        ]

        if run.started_at:
            lines.append(f"<b>Started:</b> {run.started_at[:19].replace('T', ' ')}")
            if run.status == RunStatus.RUNNING:
                elapsed = _format_elapsed(run.started_at)
                lines.append(f"<b>Elapsed:</b> {elapsed}")

        if run.finished_at:
            lines.append(
                f"<b>Finished:</b> {run.finished_at[:19].replace('T', ' ')}"
            )
            if run.started_at:
                elapsed = _format_elapsed(run.started_at, run.finished_at)
                lines.append(f"<b>Duration:</b> {elapsed}")

        if run.progress > 0:
            lines.append(f"<b>Progress:</b> {run.progress:.1f}%")

        if run.flow_options:
            opts = ", ".join(f"{k}={v}" for k, v in run.flow_options.items())
            lines.append(f"<b>Options:</b> {opts}")

        if run.notes:
            lines.append(f"<b>Notes:</b> {run.notes}")

        self.setToolTip("<br>".join(lines))


class RunsPanel(QWidget):
    """Middle panel that lists simulation runs for the selected case."""

    run_selected = Signal(str)
    runs_multi_selected = Signal(list)     # list[str] of run_ids (≥2 selected)
    run_deleted = Signal(str, str, bool)   # (case_path, run_id, delete_from_disk)
    run_stop_requested = Signal(str)       # run_id
    new_run_requested = Signal()
    notes_changed = Signal()               # notes updated; trigger a state save

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
        self._header = QLabel("Simulation Runs")
        self._header.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {_styles.TEXT_PRIMARY};"
            f" padding: 12px 12px 8px 12px; background-color: {_styles.BG_SECONDARY};"
        )
        layout.addWidget(self._header)

        # --- new-run button ---
        self._btn_bar = QWidget()
        self._btn_bar.setStyleSheet(f"background-color: {_styles.BG_SECONDARY};")
        btn_layout = QHBoxLayout(self._btn_bar)
        btn_layout.setContentsMargins(8, 4, 8, 8)

        self._btn_new_run = QPushButton("+ New Run")
        self._btn_new_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_new_run.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed,
        )
        self._btn_new_run.setStyleSheet(
            f"QPushButton {{ padding: 8px 16px; border-radius: 6px;"
            f" background-color: {_styles.ACCENT}; color: {_styles.TEXT_PRIMARY};"
            f" font-size: 13px; font-weight: bold; border: none; }}"
            f" QPushButton:hover {{ background-color: {_styles.ACCENT_HOVER}; }}"
            f" QPushButton:disabled {{ background-color: {_styles.BG_TERTIARY};"
            f" color: {_styles.TEXT_MUTED}; }}"
        )
        self._btn_new_run.setEnabled(False)
        btn_layout.addWidget(self._btn_new_run)
        layout.addWidget(self._btn_bar)

        # --- run list ---
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._list.setStyleSheet(
            f"QListWidget {{ background-color: {_styles.BG_SECONDARY}; border: none;"
            f" outline: none; }}"
            f" QListWidget::item {{ border-bottom: 1px solid {_styles.BORDER}; }}"
            f" QListWidget::item:selected {{ background-color: {_styles.BG_TERTIARY}; }}"
            f" QListWidget::item:hover {{ background-color: {_styles.BG_TERTIARY}; }}"
        )
        layout.addWidget(self._list, 1)

        # --- empty state label ---
        self._empty_label = QLabel("Select a case to view runs")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {_styles.TEXT_MUTED}; font-size: 13px; background: transparent;"
        )
        layout.addWidget(self._empty_label, 1)

        # Initially show empty state
        self._list.setVisible(False)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_signals(self) -> None:
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
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

    def refresh_styles(self) -> None:
        """Re-apply inline stylesheets using the current active theme colours."""
        self._header.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {_styles.TEXT_PRIMARY};"
            f" padding: 12px 12px 8px 12px; background-color: {_styles.BG_SECONDARY};"
        )
        self._btn_bar.setStyleSheet(f"background-color: {_styles.BG_SECONDARY};")
        self._btn_new_run.setStyleSheet(
            f"QPushButton {{ padding: 8px 16px; border-radius: 6px;"
            f" background-color: {_styles.ACCENT}; color: {_styles.TEXT_PRIMARY};"
            f" font-size: 13px; font-weight: bold; border: none; }}"
            f" QPushButton:hover {{ background-color: {_styles.ACCENT_HOVER}; }}"
            f" QPushButton:disabled {{ background-color: {_styles.BG_TERTIARY};"
            f" color: {_styles.TEXT_MUTED}; }}"
        )
        self._list.setStyleSheet(
            f"QListWidget {{ background-color: {_styles.BG_SECONDARY}; border: none;"
            f" outline: none; }}"
            f" QListWidget::item {{ border-bottom: 1px solid {_styles.BORDER}; }}"
            f" QListWidget::item:selected {{ background-color: {_styles.BG_TERTIARY}; }}"
            f" QListWidget::item:hover {{ background-color: {_styles.BG_TERTIARY}; }}"
        )
        self._empty_label.setStyleSheet(
            f"color: {_styles.TEXT_MUTED}; font-size: 13px; background: transparent;"
        )

    # ------------------------------------------------------------------
    # Slot implementations
    # ------------------------------------------------------------------
    def _on_selection_changed(self) -> None:
        """Emit *run_selected* or *runs_multi_selected* depending on the count."""
        selected_items = self._list.selectedItems()
        if not selected_items:
            return

        run_ids = [
            item.data(Qt.ItemDataRole.UserRole)
            for item in selected_items
            if item.data(Qt.ItemDataRole.UserRole) is not None
        ]

        if len(run_ids) == 1:
            self.run_selected.emit(run_ids[0])
        else:
            self.runs_multi_selected.emit(run_ids)

    def _on_delete_clicked(self, run_id: str) -> None:
        """Ask for confirmation then emit *run_deleted* with disk-delete flag."""
        if self._current_case is None:
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Delete Run")
        msg.setText(f"Delete run <b>{run_id[:8]}</b>?")
        msg.setInformativeText(
            "Choose whether to also remove the output files from disk."
        )
        btn_gui = msg.addButton("Remove from GUI only", QMessageBox.ButtonRole.AcceptRole)
        btn_disk = msg.addButton("Remove from GUI + Disk", QMessageBox.ButtonRole.DestructiveRole)
        msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(btn_gui)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked is btn_gui:
            self.run_deleted.emit(self._current_case.data_file_path, run_id, False)
        elif clicked is btn_disk:
            self.run_deleted.emit(self._current_case.data_file_path, run_id, True)

    def _on_notes_saved(self, run_id: str) -> None:  # noqa: ARG002
        """Forward notes-saved notification; notes already written to run object."""
        self.notes_changed.emit()

    def _on_stop_clicked(self, run_id: str) -> None:
        """Forward stop request to the main window."""
        self.run_stop_requested.emit(run_id)

    # ------------------------------------------------------------------
    # Widget factory
    # ------------------------------------------------------------------
    def _create_run_widget(self, run: SimulationRun) -> RunItemWidget:
        """Create and register a :class:`RunItemWidget` for *run*."""
        widget = RunItemWidget(run, parent=self._list)
        widget.delete_clicked.connect(self._on_delete_clicked)
        widget.stop_clicked.connect(self._on_stop_clicked)
        widget.notes_saved.connect(self._on_notes_saved)
        self._run_widgets[run.run_id] = widget
        return widget
