"""Settings / preferences dialog for OPM Flow GUI.

Allows the user to configure binary paths, the default output directory,
and the list of directories that are scanned for ``.DATA`` case files.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from opm_flow_gui.core.config import Config
from opm_flow_gui.core.wsl_utils import is_windows
from opm_flow_gui.gui.styles import (
    ACCENT,
    ACCENT_LIGHT,
    BG_SECONDARY,
    BG_TERTIARY,
    BORDER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    THEMES,
)


class SettingsDialog(QDialog):
    """Modal dialog for editing application-wide preferences."""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config

        self.setWindowTitle("Settings")
        self.setMinimumSize(700, 520)

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        # ---- header ----
        header = QLabel("\u2699  Settings")
        header.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {ACCENT_LIGHT};"
            " background: transparent; padding-bottom: 4px;"
        )
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        # ---- appearance group ----
        content_layout.addWidget(self._build_appearance_group())

        # ---- paths group ----
        content_layout.addWidget(self._build_paths_group())

        # ---- search directories group ----
        content_layout.addWidget(self._build_search_dirs_group(), 1)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # ---- button box ----
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Group builders
    # ------------------------------------------------------------------
    def _build_appearance_group(self) -> QGroupBox:
        group = QGroupBox("Appearance")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel("Theme:")
        lbl.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-weight: 600; background: transparent;"
        )
        row.addWidget(lbl)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(list(THEMES.keys()))
        self._theme_combo.setCurrentText(self._config.theme)
        self._theme_combo.setToolTip("Change the application colour theme")
        row.addWidget(self._theme_combo, 1)
        row.addStretch()

        layout.addLayout(row)
        return group

    def _build_paths_group(self) -> QGroupBox:
        group = QGroupBox("Paths")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)

        # OPM Flow binary
        self._edit_flow = self._add_path_row(
            layout,
            "OPM Flow Binary:",
            self._config.flow_binary,
            "Path to the OPM Flow executable",
            self._browse_flow_binary,
        )

        # MPI runner
        self._edit_mpirun = self._add_path_row(
            layout,
            "MPI Runner:",
            self._config.mpirun_binary,
            "Path to the MPI runner (e.g. mpirun, mpiexec)",
            self._browse_mpirun,
        )

        # ResInsight binary
        self._edit_resinsight = self._add_path_row(
            layout,
            "ResInsight Binary:",
            self._config.resinsight_binary,
            "Path to the ResInsight executable",
            self._browse_resinsight,
        )

        # Output base path
        self._edit_output = self._add_path_row(
            layout,
            "Output Base Path:",
            self._config.output_base_path,
            "Default root directory for simulation output",
            self._browse_output_path,
        )

        # WSL checkbox – only relevant on Windows
        self._chk_wsl: QCheckBox | None = None
        if is_windows():
            self._chk_wsl = QCheckBox(
                "Run OPM Flow via WSL (Windows Subsystem for Linux)"
            )
            self._chk_wsl.setChecked(self._config.use_wsl)
            self._chk_wsl.setToolTip(
                "When enabled, the flow executable is invoked through WSL.\n"
                "Output and case paths are automatically translated to WSL\n"
                "mount-point paths (/mnt/<drive>/…) before being passed to flow."
            )
            self._chk_wsl.setStyleSheet(
                f"QCheckBox {{ color: {TEXT_SECONDARY}; font-weight: 600;"
                " background: transparent; }"
            )
            layout.addWidget(self._chk_wsl)

        return group

    def _build_search_dirs_group(self) -> QGroupBox:
        group = QGroupBox("Auto-Discovery Directories")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(8)

        self._list_dirs = QListWidget()
        self._list_dirs.setAlternatingRowColors(True)
        self._list_dirs.addItems(self._config.search_directories)
        layout.addWidget(self._list_dirs, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        btn_add = QPushButton("Add Directory")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setToolTip("Add a directory to scan for .DATA files")
        btn_add.clicked.connect(self._add_search_dir)
        btn_row.addWidget(btn_add)

        btn_remove = QPushButton("Remove Selected")
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.setToolTip("Remove the selected directory from the list")
        btn_remove.setStyleSheet(
            f"QPushButton {{ background-color: {BG_TERTIARY};"
            f" color: {TEXT_PRIMARY}; border: 1px solid {BORDER}; }}"
            f" QPushButton:hover {{ background-color: {BG_SECONDARY};"
            f" border-color: {ACCENT}; }}"
        )
        btn_remove.clicked.connect(self._remove_search_dir)
        btn_row.addWidget(btn_remove)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        return group

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _add_path_row(
        self,
        parent_layout: QVBoxLayout,
        label_text: str,
        initial_value: str,
        tooltip: str,
        browse_slot: object,
    ) -> QLineEdit:
        """Create a labelled line-edit + Browse button row."""
        row = QHBoxLayout()
        row.setSpacing(6)

        label = QLabel(label_text)
        label.setFixedWidth(135)
        label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-weight: 600;"
            " background: transparent;"
        )
        row.addWidget(label)

        edit = QLineEdit(initial_value)
        edit.setToolTip(tooltip)
        row.addWidget(edit, 1)

        btn = QPushButton("Browse")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ padding: 6px 12px; border-radius: 6px;"
            f" background-color: {BG_TERTIARY}; color: {TEXT_PRIMARY};"
            f" border: 1px solid {BORDER}; }}"
            f" QPushButton:hover {{ background-color: {BG_SECONDARY};"
            f" border-color: {ACCENT}; }}"
        )
        btn.clicked.connect(browse_slot)
        row.addWidget(btn)

        parent_layout.addLayout(row)
        return edit

    # ------------------------------------------------------------------
    # Public getters
    # ------------------------------------------------------------------
    def get_config(self) -> Config:
        """Return a new :class:`Config` populated with the dialog values."""
        dirs: list[str] = []
        for i in range(self._list_dirs.count()):
            item = self._list_dirs.item(i)
            if item is not None:
                dirs.append(item.text())

        use_wsl = self._chk_wsl.isChecked() if self._chk_wsl is not None else False

        return Config(
            flow_binary=self._edit_flow.text().strip(),
            mpirun_binary=self._edit_mpirun.text().strip(),
            resinsight_binary=self._edit_resinsight.text().strip(),
            output_base_path=self._edit_output.text().strip(),
            search_directories=dirs,
            case_files=list(self._config.case_files),
            theme=self._theme_combo.currentText(),
            use_wsl=use_wsl,
        )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _browse_flow_binary(self) -> None:
        """Open a native file picker for the OPM Flow executable."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select OPM Flow Binary",
            self._edit_flow.text(),
            "All Files (*)",
        )
        if path:
            self._edit_flow.setText(path)

    def _browse_mpirun(self) -> None:
        """Open a native file picker for the MPI runner."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select MPI Runner",
            self._edit_mpirun.text(),
            "All Files (*)",
        )
        if path:
            self._edit_mpirun.setText(path)

    def _browse_resinsight(self) -> None:
        """Open a native file picker for the ResInsight executable."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select ResInsight Binary",
            self._edit_resinsight.text(),
            "All Files (*)",
        )
        if path:
            self._edit_resinsight.setText(path)

    def _browse_output_path(self) -> None:
        """Open a native folder picker for the output base directory."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Base Path",
            self._edit_output.text(),
        )
        if path:
            self._edit_output.setText(path)

    def _add_search_dir(self) -> None:
        """Open a native folder picker and append the chosen directory."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Add Search Directory",
        )
        if path and not self._list_contains(path):
            self._list_dirs.addItem(path)

    def _remove_search_dir(self) -> None:
        """Remove the currently selected directory from the list."""
        for item in self._list_dirs.selectedItems():
            self._list_dirs.takeItem(self._list_dirs.row(item))

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    def _list_contains(self, text: str) -> bool:
        """Return *True* if *text* is already present in the directory list."""
        for i in range(self._list_dirs.count()):
            item = self._list_dirs.item(i)
            if item is not None and item.text() == text:
                return True
        return False
