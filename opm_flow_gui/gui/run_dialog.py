"""Dialog for configuring a new OPM Flow simulation run.

Presents general settings (MPI processes, output directory) on the first tab
and all available OPM Flow command-line options on the second.  Options can be
saved to / loaded from JSON for easy re-use across runs.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from opm_flow_gui.core.simulation_runner import OPM_FLOW_OPTIONS
from opm_flow_gui.gui.styles import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_LIGHT,
    BG_PRIMARY,
    BG_SECONDARY,
    BG_TERTIARY,
    BORDER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class RunDialog(QDialog):
    """Modal dialog for configuring a new simulation run."""

    def __init__(
        self,
        case_name: str,
        output_base_path: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._case_name = case_name
        self._output_base_path = output_base_path

        # Mapping of option-name → widget for the Flow Options tab
        self._option_widgets: dict[str, QWidget] = {}

        self.setWindowTitle(f"New Simulation Run - {case_name}")
        self.setMinimumSize(650, 550)

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # ---- header ----
        header = QLabel(f"\u25b6  {self._case_name}")
        header.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {ACCENT_LIGHT};"
            " background: transparent; padding-bottom: 4px;"
        )
        root.addWidget(header)

        # ---- tab widget ----
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), "General")
        self._tabs.addTab(self._build_flow_options_tab(), "Flow Options")
        root.addWidget(self._tabs, 1)

        # ---- button box ----
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------
    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        layout = QFormLayout(tab)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # MPI processes
        self._spin_mpi = QSpinBox()
        self._spin_mpi.setRange(1, 1024)
        self._spin_mpi.setValue(1)
        self._spin_mpi.setToolTip("Number of MPI processes to launch")
        mpi_label = QLabel("MPI Processes:")
        mpi_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-weight: 600; background: transparent;"
        )
        layout.addRow(mpi_label, self._spin_mpi)

        # Output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_dir = str(
            Path(self._output_base_path) / self._case_name / f"run_{timestamp}"
        )

        dir_row = QHBoxLayout()
        dir_row.setSpacing(6)
        self._edit_output_dir = QLineEdit(default_dir)
        self._edit_output_dir.setToolTip("Directory where simulation output will be written")
        dir_row.addWidget(self._edit_output_dir, 1)

        btn_browse = QPushButton("Browse")
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.setStyleSheet(
            f"QPushButton {{ padding: 8px 14px; border-radius: 6px;"
            f" background-color: {BG_TERTIARY}; color: {TEXT_PRIMARY};"
            f" border: 1px solid {BORDER}; }}"
            f" QPushButton:hover {{ background-color: {BG_SECONDARY};"
            f" border-color: {ACCENT}; }}"
        )
        btn_browse.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(btn_browse)

        dir_label = QLabel("Output Directory:")
        dir_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-weight: 600; background: transparent;"
        )
        layout.addRow(dir_label, dir_row)

        return tab

    def _build_flow_options_tab(self) -> QWidget:
        tab = QWidget()
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        # Toolbar row
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(12, 10, 12, 0)
        toolbar.setSpacing(6)

        for label, slot in (
            ("Load from JSON", self._load_json),
            ("Save to JSON", self._save_json),
            ("Reset to Defaults", self._reset_defaults),
        ):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ padding: 6px 14px; border-radius: 6px;"
                f" background-color: {BG_TERTIARY}; color: {TEXT_PRIMARY};"
                f" border: 1px solid {BORDER}; font-size: 12px; }}"
                f" QPushButton:hover {{ background-color: {BG_SECONDARY};"
                f" border-color: {ACCENT}; }}"
            )
            btn.clicked.connect(slot)
            toolbar.addWidget(btn)

        toolbar.addStretch()
        outer.addLayout(toolbar)

        # Scroll area with option widgets
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll.setWidget(self._build_option_widgets())
        outer.addWidget(scroll, 1)

        return tab

    # ------------------------------------------------------------------
    # Option-widget factory
    # ------------------------------------------------------------------
    def _build_option_widgets(self) -> QWidget:
        """Build a form widget with one row per OPM Flow option."""
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        form = QFormLayout(container)
        form.setContentsMargins(12, 10, 12, 12)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        for opt in OPM_FLOW_OPTIONS:
            name: str = opt["name"]
            opt_type: str = opt["type"]
            default: str = opt["default"]
            description: str = opt.get("description", "")
            choices: list[str] | None = opt.get("choices")

            widget: QWidget

            if opt_type == "string" and choices:
                combo = QComboBox()
                combo.addItems(choices)
                idx = combo.findText(default)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                widget = combo

            elif opt_type == "string":
                line = QLineEdit(default)
                widget = line

            elif opt_type == "bool":
                check = QCheckBox()
                check.setChecked(default.lower() == "true")
                widget = check

            elif opt_type == "int":
                spin = QSpinBox()
                spin.setRange(-999_999_999, 999_999_999)
                spin.setValue(int(default))
                widget = spin

            elif opt_type == "float":
                # Use a line edit so the user can type scientific notation freely.
                # Format the default using Python's 'g' specifier so that very
                # small/large defaults are shown in a readable scientific form
                # (e.g. 1e-06 rather than 0.000001).
                try:
                    formatted = f"{float(default):g}"
                except ValueError:
                    formatted = default
                line = QLineEdit(formatted)
                validator = QDoubleValidator()
                validator.setNotation(QDoubleValidator.Notation.ScientificNotation)
                line.setValidator(validator)
                widget = line

            else:
                # Fallback for unknown types
                line = QLineEdit(default)
                widget = line

            widget.setToolTip(description)
            widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed,
            )

            label = QLabel(name)
            label.setToolTip(description)
            label.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-weight: 600;"
                " background: transparent;"
            )

            form.addRow(label, widget)
            self._option_widgets[name] = widget

        return container

    # ------------------------------------------------------------------
    # Public getters
    # ------------------------------------------------------------------
    def get_options(self) -> dict[str, str]:
        """Return a dict of option values that differ from their defaults."""
        changed: dict[str, str] = {}

        for opt in OPM_FLOW_OPTIONS:
            name: str = opt["name"]
            default: str = opt["default"]
            opt_type: str = opt["type"]
            widget = self._option_widgets.get(name)
            if widget is None:
                continue

            value = self._read_widget_value(widget, opt_type)

            # For float options, compare numerically so that formatting
            # differences (e.g. "1e-06" vs "1e-6") are treated as equal.
            if opt_type == "float":
                try:
                    is_default = float(value) == float(default)
                except ValueError:
                    is_default = False
            else:
                is_default = value == default

            if not is_default:
                changed[name] = value

        return changed

    def get_mpi_processes(self) -> int:
        """Return the number of MPI processes selected by the user."""
        return self._spin_mpi.value()

    def get_output_dir(self) -> str:
        """Return the output directory path entered by the user."""
        return self._edit_output_dir.text().strip()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _browse_output_dir(self) -> None:
        """Open a native folder picker for the output directory."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self._edit_output_dir.text(),
        )
        if path:
            self._edit_output_dir.setText(path)

    def _load_json(self) -> None:
        """Load option values from a JSON file and populate widgets."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Options from JSON",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return

        with open(path, "r", encoding="utf-8") as fh:
            data: dict = json.load(fh)

        for opt in OPM_FLOW_OPTIONS:
            name = opt["name"]
            if name in data:
                self._write_widget_value(
                    self._option_widgets[name],
                    opt["type"],
                    str(data[name]),
                )

    def _save_json(self) -> None:
        """Save current option values to a JSON file."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Options to JSON",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return

        data: dict[str, str] = {}
        for opt in OPM_FLOW_OPTIONS:
            name = opt["name"]
            widget = self._option_widgets.get(name)
            if widget is not None:
                data[name] = self._read_widget_value(widget, opt["type"])

        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)

    def _reset_defaults(self) -> None:
        """Reset every option widget back to its default value."""
        for opt in OPM_FLOW_OPTIONS:
            name = opt["name"]
            widget = self._option_widgets.get(name)
            if widget is not None:
                self._write_widget_value(widget, opt["type"], opt["default"])

    # ------------------------------------------------------------------
    # Widget value helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _read_widget_value(widget: QWidget, opt_type: str) -> str:
        """Extract the current value from *widget* as a string."""
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QCheckBox):
            return "true" if widget.isChecked() else "false"
        if isinstance(widget, QSpinBox):
            return str(widget.value())
        if isinstance(widget, QLineEdit):
            return widget.text()
        return ""

    @staticmethod
    def _write_widget_value(widget: QWidget, opt_type: str, value: str) -> None:
        """Set *widget* to *value* (given as a string)."""
        if isinstance(widget, QComboBox):
            idx = widget.findText(value)
            if idx >= 0:
                widget.setCurrentIndex(idx)
        elif isinstance(widget, QCheckBox):
            widget.setChecked(value.lower() == "true")
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QLineEdit):
            # For float type, reformat to scientific notation if possible
            if opt_type == "float":
                try:
                    value = f"{float(value):g}"
                except ValueError:
                    pass
            widget.setText(value)
