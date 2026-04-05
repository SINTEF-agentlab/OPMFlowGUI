"""Main application window for OPM Flow GUI."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
    QWidget,
)

from opm_flow_gui.core.case_manager import (
    CaseManager,
    RunStatus,
    SimulationRun,
)
from opm_flow_gui.core.config import ConfigManager, DEFAULT_CONFIG_DIR
from opm_flow_gui.core.simulation_runner import SimulationRunner
from opm_flow_gui.gui.case_panel import CasePanel
from opm_flow_gui.gui.run_dialog import RunDialog
from opm_flow_gui.gui.runs_panel import RunsPanel
from opm_flow_gui.gui.settings_dialog import SettingsDialog
from opm_flow_gui.gui.styles import STYLESHEET
from opm_flow_gui.gui.summary_panel import SummaryPanel

logger = logging.getLogger(__name__)

_CASES_FILE = DEFAULT_CONFIG_DIR / "cases.json"


class MainWindow(QMainWindow):
    """Three-panel main window: Cases | Runs | Summary."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("OPM Flow GUI")
        self.setMinimumSize(1200, 700)
        self.setStyleSheet(STYLESHEET)

        # --- Core managers ---------------------------------------------------
        self._config_manager = ConfigManager()
        self._config_manager.load()

        self._case_manager = CaseManager()
        if _CASES_FILE.exists():
            try:
                self._case_manager.load(str(_CASES_FILE))
            except Exception:
                logger.warning("Failed to load saved cases – starting fresh.")

        config = self._config_manager.config
        self._sim_runner = SimulationRunner(
            flow_binary=config.flow_binary,
            mpirun_binary=config.mpirun_binary,
            parent=self,
        )

        # Discover cases from configured search directories
        for search_dir in config.search_directories:
            try:
                self._case_manager.discover_cases(search_dir)
            except Exception:
                logger.warning("Could not scan directory: %s", search_dir)

        # Track current selection
        self._current_case_path: str | None = None
        self._current_run_id: str | None = None

        # --- UI setup --------------------------------------------------------
        self._case_panel = CasePanel(self._case_manager)
        self._runs_panel = RunsPanel()
        self._summary_panel = SummaryPanel()
        self._summary_panel.set_resinsight_binary(config.resinsight_binary)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._case_panel)
        splitter.addWidget(self._runs_panel)
        splitter.addWidget(self._summary_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([240, 260, 700])

        container = QWidget()
        container.setLayout(_hbox(splitter))
        self.setCentralWidget(container)

        self._setup_menu_bar()
        self.statusBar().showMessage("Ready")

        # --- Signal connections ----------------------------------------------
        self._case_panel.case_selected.connect(self._on_case_selected)
        self._runs_panel.run_selected.connect(self._on_run_selected)
        self._runs_panel.new_run_requested.connect(self._on_new_run)
        self._runs_panel.run_deleted.connect(self._on_run_deleted)
        self._runs_panel.notes_changed.connect(self._save_state)

        self._sim_runner.progress_updated.connect(self._on_progress_updated)
        self._sim_runner.run_finished.connect(self._on_run_finished)
        self._sim_runner.output_received.connect(self._on_output_received)

    # --------------------------------------------------------------------- #
    # Menu bar                                                                #
    # --------------------------------------------------------------------- #

    def _setup_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        # -- File menu --------------------------------------------------------
        file_menu = menu_bar.addMenu("&File")

        add_action = QAction("&Add Case File…", self)
        add_action.setShortcut(QKeySequence("Ctrl+O"))
        add_action.triggered.connect(self._case_panel._add_case_file)
        file_menu.addAction(add_action)

        scan_action = QAction("&Scan Directory…", self)
        scan_action.setShortcut(QKeySequence("Ctrl+D"))
        scan_action.triggered.connect(self._case_panel._scan_folder)
        file_menu.addAction(scan_action)

        file_menu.addSeparator()

        settings_action = QAction("Se&ttings…", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # -- Help menu --------------------------------------------------------
        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # --------------------------------------------------------------------- #
    # Slots – Panel interaction                                               #
    # --------------------------------------------------------------------- #

    def _on_case_selected(self, case_path: str) -> None:
        self._current_case_path = case_path
        self._current_run_id = None
        case = self._case_manager.cases.get(case_path)
        self._runs_panel.set_case(case)
        self._summary_panel.set_run(None)
        if case is not None:
            self.statusBar().showMessage(f"Case: {case.name}")

    def _on_run_selected(self, run_id: str) -> None:
        self._current_run_id = run_id
        if self._current_case_path is None:
            return

        case = self._case_manager.cases.get(self._current_case_path)
        if case is None:
            return

        run = case.get_run(run_id)
        if run is None:
            return

        # Show run results (summary + log files) regardless of status;
        # completed runs also load the summary chart.
        self._summary_panel.set_run(run)
        if run.status == RunStatus.COMPLETED:
            self.statusBar().showMessage(
                f"Viewing results for run {run_id[:8]}"
            )
        else:
            self.statusBar().showMessage(
                f"Run {run_id[:8]} – {run.status.value}"
            )

    def _on_new_run(self) -> None:
        if self._current_case_path is None:
            QMessageBox.warning(
                self,
                "No Case Selected",
                "Please select a case before creating a new run.",
            )
            return

        case = self._case_manager.cases.get(self._current_case_path)
        if case is None:
            return

        config = self._config_manager.config
        output_base = (
            config.output_base_path
            if config.output_base_path
            else str(Path(case.directory) / "output")
        )

        dialog = RunDialog(case.name, output_base, parent=self)
        if dialog.exec() != RunDialog.DialogCode.Accepted:
            return

        output_dir = dialog.get_output_dir()
        if not output_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = str(
                Path(output_base) / case.name / f"run_{timestamp}"
            )

        # Ensure output directory exists
        try:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Directory Error",
                f"Could not create output directory:\n{output_dir}\n\n{exc}",
            )
            return

        run = SimulationRun(
            case_path=self._current_case_path,
            output_dir=output_dir,
            flow_options=dialog.get_options(),
            mpi_processes=dialog.get_mpi_processes(),
        )

        case.add_run(run)

        started = self._sim_runner.start_run(run)
        if started:
            run.status = RunStatus.RUNNING
            run.started_at = datetime.now().isoformat()
            self.statusBar().showMessage(
                f"Started run {run.run_id[:8]} for {case.name}"
            )
        else:
            run.status = RunStatus.FAILED
            QMessageBox.critical(
                self,
                "Launch Error",
                f"Failed to start simulation for {case.name}.\n"
                "Check that the OPM Flow binary path is correct in Settings.",
            )

        self._save_state()
        self._runs_panel.refresh()
        self._case_panel.refresh()

    def _on_run_deleted(self, case_path: str, run_id: str, delete_from_disk: bool) -> None:
        # Cancel if still running
        self._sim_runner.cancel_run(run_id)

        # Optionally delete output directory from disk
        if delete_from_disk:
            case = self._case_manager.cases.get(case_path)
            if case is not None:
                run = case.get_run(run_id)
                if run is not None and run.output_dir:
                    try:
                        shutil.rmtree(run.output_dir, ignore_errors=False)
                        logger.info("Deleted output directory: %s", run.output_dir)
                    except OSError as exc:
                        logger.warning(
                            "Could not delete output directory %s: %s",
                            run.output_dir,
                            exc,
                        )

        case = self._case_manager.cases.get(case_path)
        if case is not None:
            case.remove_run(run_id)
            self._save_state()

        if self._current_run_id == run_id:
            self._current_run_id = None
            self._summary_panel.set_run(None)

        self._runs_panel.refresh()
        self.statusBar().showMessage(f"Deleted run {run_id[:8]}")
        self._case_panel.refresh()

    # --------------------------------------------------------------------- #
    # Slots – Simulation progress                                             #
    # --------------------------------------------------------------------- #

    def _on_progress_updated(self, run_id: str, progress: float) -> None:
        # Persist progress on the run object
        if self._current_case_path is not None:
            case = self._case_manager.cases.get(self._current_case_path)
            if case is not None:
                run = case.get_run(run_id)
                if run is not None:
                    run.progress = progress

        self._runs_panel.update_run_progress(run_id, progress)

    def _on_run_finished(self, run_id: str, status: str) -> None:
        # Update the run model
        for case in self._case_manager.get_all_cases():
            run = case.get_run(run_id)
            if run is None:
                continue
            run.status = RunStatus(status)
            run.finished_at = datetime.now().isoformat()
            if status == "completed":
                run.progress = 100.0
            break

        self._runs_panel.update_run_status(run_id, status.upper())
        self._save_state()
        self.statusBar().showMessage(
            f"Run {run_id[:8]} {status}"
        )

    def _on_output_received(self, run_id: str, line: str) -> None:  # noqa: ARG002
        # Truncate long lines for the status bar
        display = line.strip()
        if len(display) > 120:
            display = display[:117] + "…"
        if display:
            self.statusBar().showMessage(display)

    # --------------------------------------------------------------------- #
    # Settings / About                                                        #
    # --------------------------------------------------------------------- #

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._config_manager.config, parent=self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return

        new_config = dialog.get_config()
        self._config_manager._config = new_config
        self._config_manager.save()

        # Update simulation runner binaries
        self._sim_runner._flow_binary = new_config.flow_binary
        self._sim_runner._mpirun_binary = new_config.mpirun_binary

        # Update ResInsight binary in summary panel
        self._summary_panel.set_resinsight_binary(new_config.resinsight_binary)

        # Re-discover cases from updated search directories
        for search_dir in new_config.search_directories:
            try:
                self._case_manager.discover_cases(search_dir)
            except Exception:
                logger.warning("Could not scan directory: %s", search_dir)

        self._case_panel.refresh()
        self._save_state()
        self.statusBar().showMessage("Settings updated")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About OPM Flow GUI",
            "<h3>OPM Flow GUI</h3>"
            "<p>A graphical interface for running and monitoring "
            "OPM Flow reservoir simulations.</p>"
            "<p>Built with PySide6 and matplotlib.</p>",
        )

    # --------------------------------------------------------------------- #
    # Persistence                                                             #
    # --------------------------------------------------------------------- #

    def _save_state(self) -> None:
        try:
            DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            self._case_manager.save(str(_CASES_FILE))
            self._config_manager.save()
        except Exception:
            logger.exception("Failed to save application state")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._save_state()
        super().closeEvent(event)


# ── Helpers ──────────────────────────────────────────────────────────────── #


def _hbox(widget: QWidget):
    """Return a zero-margin QHBoxLayout containing *widget*."""
    from PySide6.QtWidgets import QHBoxLayout

    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(widget)
    return layout
