"""Right-hand panel displaying summary plot data from completed simulation runs.

Contains two tabs:
- **Summary**: filterable tree of summary vectors + matplotlib plot canvas.
- **Log Files**: scrollable PRT/DBG viewer with search and step navigation.

A "Launch ResInsight" button is available in the Summary tab toolbar.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import matplotlib as mpl
import matplotlib.dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtGui import QBrush, QColor

from opm_flow_gui.core.case_manager import SimulationRun
from opm_flow_gui.core.summary_reader import SummaryReader
from opm_flow_gui.gui.log_viewer import LogViewerPanel
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plot colour palette – a vibrant set that reads well on a dark background
# ---------------------------------------------------------------------------
_PLOT_COLORS: list[str] = [
    "#7c3aed",  # purple (accent)
    "#22c55e",  # green
    "#f59e0b",  # amber
    "#3b82f6",  # blue
    "#ef4444",  # red
    "#06b6d4",  # cyan
    "#ec4899",  # pink
    "#a78bfa",  # light purple
    "#facc15",  # yellow
    "#14b8a6",  # teal
]


class SummaryPanel(QWidget):
    """Right panel showing summary results and log files for a completed run."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._reader: SummaryReader | None = None
        self._current_run: SimulationRun | None = None
        self._resinsight_binary: str = "ResInsight"
        self._legend_visible: bool = True
        self._plotted_keys: list[str] = []
        self._color_index: int = 0

        self._setup_ui()
        self._connect_signals()
        self._show_empty_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_resinsight_binary(self, path: str) -> None:
        """Update the ResInsight executable path."""
        self._resinsight_binary = path

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- header ---
        header = QLabel("Results")
        header.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {TEXT_PRIMARY};"
            f" padding: 12px 12px 8px 12px; background-color: {BG_SECONDARY};"
        )
        root.addWidget(header)

        # --- tab widget ---
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ background-color: {BG_PRIMARY}; border: none; }}"
        )
        self._tabs.addTab(self._build_summary_tab(), "Summary")
        self._tabs.addTab(self._build_log_tab(), "Log Files")
        root.addWidget(self._tabs, 1)

        # --- empty-state overlay ---
        self._empty_label = QLabel("Select a completed run to view results")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 14px; background: transparent;"
        )
        root.addWidget(self._empty_label, 1)

    def _build_summary_tab(self) -> QWidget:
        """Build the summary plot tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- toolbar ----
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background-color: {BG_SECONDARY};")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 6, 8, 6)
        tb_layout.setSpacing(8)

        self._btn_clear = self._make_toolbar_button("Clear Plot")
        self._btn_toggle_legend = self._make_toolbar_button("Toggle Legend")
        self._btn_pop_out = self._make_toolbar_button("\u2197 Pop Out")
        self._btn_pop_out.setToolTip("Open the current plot in a separate window")
        self._btn_pop_out.setEnabled(False)
        self._chk_overlay = QCheckBox("Overlay multiple vectors")
        self._chk_overlay.setStyleSheet(
            f"QCheckBox {{ color: {TEXT_SECONDARY}; font-size: 12px;"
            f" background: transparent; }}"
        )
        self._chk_overlay.setChecked(False)

        self._btn_resinsight = self._make_toolbar_button("\U0001f5a5 Launch ResInsight")
        self._btn_resinsight.setToolTip(
            "Open the simulation output in ResInsight"
        )
        self._btn_resinsight.setEnabled(False)

        tb_layout.addWidget(self._btn_clear)
        tb_layout.addWidget(self._btn_toggle_legend)
        tb_layout.addWidget(self._btn_pop_out)
        tb_layout.addStretch()
        tb_layout.addWidget(self._chk_overlay)
        tb_layout.addWidget(self._btn_resinsight)

        layout.addWidget(toolbar)

        # ---- splitter: tree + canvas ----
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(3)

        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter keys\u2026")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.setStyleSheet(
            f"QLineEdit {{ margin: 6px 8px; padding: 6px 10px;"
            f" border: 1px solid {BORDER}; border-radius: 6px;"
            f" background-color: {BG_TERTIARY}; color: {TEXT_PRIMARY}; }}"
        )
        left_layout.addWidget(self._filter_edit)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._tree.setStyleSheet(
            f"QTreeWidget {{ background-color: {BG_SECONDARY}; border: none;"
            f" outline: none; }}"
            f" QTreeWidget::item {{ padding: 4px 6px; }}"
            f" QTreeWidget::item:selected {{ background-color: {BG_TERTIARY}; }}"
            f" QTreeWidget::item:hover {{ background-color: {BG_TERTIARY}; }}"
        )
        left_layout.addWidget(self._tree, 1)

        self._splitter.addWidget(left_pane)

        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._figure = Figure(facecolor=BG_PRIMARY)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        self._axes = self._figure.add_subplot(111)
        self._style_axes()

        right_layout.addWidget(self._canvas, 1)

        self._splitter.addWidget(right_pane)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 3)

        layout.addWidget(self._splitter, 1)
        return tab

    def _build_log_tab(self) -> QWidget:
        """Build the log file viewer tab."""
        self._log_viewer = LogViewerPanel()
        return self._log_viewer

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_toolbar_button(text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ padding: 4px 12px; border-radius: 4px;"
            f" background-color: {BG_TERTIARY}; color: {TEXT_SECONDARY};"
            f" border: 1px solid {BORDER}; font-size: 12px; }}"
            f" QPushButton:hover {{ background-color: {ACCENT};"
            f" color: {TEXT_PRIMARY}; }}"
            f" QPushButton:disabled {{ background-color: {BG_TERTIARY};"
            f" color: {TEXT_MUTED}; }}"
        )
        return btn

    def _style_axes(self) -> None:
        """Apply dark-theme styling to the matplotlib axes."""
        ax = self._axes
        ax.set_facecolor(BG_SECONDARY)
        ax.tick_params(colors=TEXT_SECONDARY, which="both")
        ax.xaxis.label.set_color(TEXT_SECONDARY)
        ax.yaxis.label.set_color(TEXT_SECONDARY)
        ax.title.set_color(TEXT_PRIMARY)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        ax.grid(True, color=BG_TERTIARY, linewidth=0.5)

    def _next_color(self) -> str:
        color = _PLOT_COLORS[self._color_index % len(_PLOT_COLORS)]
        self._color_index += 1
        return color

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._tree.itemClicked.connect(self._on_key_selected)
        self._tree.currentItemChanged.connect(self._on_current_item_changed)
        self._filter_edit.textChanged.connect(self._filter_keys)
        self._btn_clear.clicked.connect(self._clear_plot)
        self._btn_toggle_legend.clicked.connect(self._toggle_legend)
        self._btn_pop_out.clicked.connect(self._pop_out_plot)
        self._btn_resinsight.clicked.connect(self._launch_resinsight)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_run(self, run: SimulationRun | None) -> None:
        """Load summary data for *run*, or clear the panel when ``None``."""
        self._current_run = run
        self._clear_plot()
        self._tree.clear()
        self._btn_resinsight.setEnabled(run is not None)
        self._btn_pop_out.setEnabled(False)

        if run is None:
            self._reader = None
            self._log_viewer.set_run(None)
            self._show_empty_state()
            return

        self._log_viewer.set_run(run)

        if self._load_summary(run.output_dir):
            self._populate_tree()
            self._tabs.setVisible(True)
            self._empty_label.setVisible(False)
        else:
            self._reader = None
            self._show_empty_state()
            self._empty_label.setText("No summary data available for this run")
            # Still show tabs (log viewer may have files even without summary)
            self._tabs.setVisible(True)
            self._empty_label.setVisible(False)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_summary(self, output_dir: str) -> bool:
        """Create a :class:`SummaryReader` and attempt to load data."""
        out = Path(output_dir)
        candidates = list(out.glob("*.SMSPEC")) + list(out.glob("*.DATA"))
        if not candidates:
            logger.warning("No SMSPEC/DATA files found in %s", output_dir)
            return False

        reader = SummaryReader(str(candidates[0]))
        if not reader.load():
            return False

        self._reader = reader
        return True

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _populate_tree(self) -> None:
        """Fill the tree widget with categorised summary keys."""
        self._tree.clear()
        if self._reader is None:
            return

        categories = self._reader.categorize_keys()
        for category, keys in categories.items():
            parent = QTreeWidgetItem(self._tree, [category])
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            parent.setExpanded(False)
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)
            parent.setForeground(0, QBrush(QColor(ACCENT_LIGHT)))

            for key in keys:
                child = QTreeWidgetItem(parent, [key])
                child.setData(0, Qt.ItemDataRole.UserRole, key)

    # ------------------------------------------------------------------
    # Plotting
    # ------------------------------------------------------------------

    def _on_key_selected(self, item: QTreeWidgetItem, _column: int) -> None:
        """Respond to a tree-item click by plotting the selected vector."""
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if key is None:
            return
        self._plot_vector(key)

    def _on_current_item_changed(
        self, current: QTreeWidgetItem | None, _previous: QTreeWidgetItem | None
    ) -> None:
        """Plot the vector for the newly focused tree item (keyboard navigation)."""
        if current is None:
            return
        key = current.data(0, Qt.ItemDataRole.UserRole)
        if key is None:
            return
        self._plot_vector(key)

    def _plot_vector(self, key: str) -> None:
        """Plot a single summary vector on the canvas."""
        if self._reader is None:
            return

        vector = self._reader.get_vector(key)
        if vector is None:
            return

        dates, values = vector

        if not self._chk_overlay.isChecked():
            self._axes.clear()
            self._style_axes()
            self._plotted_keys.clear()
            self._color_index = 0

        color = self._next_color()
        self._axes.plot(
            dates,
            values,
            color=color,
            linewidth=1.5,
            label=key,
        )

        self._plotted_keys.append(key)

        # Axis labels / title
        info = self._reader.get_info()
        unit = info.units.get(key, "") if info else ""
        ylabel = unit if unit else "Value"

        if len(self._plotted_keys) == 1:
            self._axes.set_title(key, fontsize=13, fontweight="bold")
            self._axes.set_ylabel(ylabel, fontsize=11)
        else:
            self._axes.set_title(
                ", ".join(self._plotted_keys), fontsize=11, fontweight="bold",
            )
            self._axes.set_ylabel("Value", fontsize=11)

        self._axes.set_xlabel("Date", fontsize=11)
        self._axes.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        self._axes.xaxis.set_major_locator(mdates.AutoDateLocator())
        self._figure.autofmt_xdate(rotation=30)

        if self._legend_visible and self._plotted_keys:
            legend = self._axes.legend(
                loc="best",
                fontsize=10,
                facecolor=BG_TERTIARY,
                edgecolor=BORDER,
                labelcolor=TEXT_PRIMARY,
            )
            legend.get_frame().set_alpha(0.9)

        self._figure.tight_layout()
        self._canvas.draw_idle()
        self._btn_pop_out.setEnabled(True)

    def _clear_plot(self) -> None:
        """Clear the matplotlib figure."""
        self._axes.clear()
        self._style_axes()
        self._plotted_keys.clear()
        self._color_index = 0
        self._canvas.draw_idle()
        self._btn_pop_out.setEnabled(False)

    def _toggle_legend(self) -> None:
        """Toggle legend visibility and redraw."""
        self._legend_visible = not self._legend_visible
        legend = self._axes.get_legend()
        if legend is not None:
            legend.set_visible(self._legend_visible)
        self._canvas.draw_idle()

    # ------------------------------------------------------------------
    # Pop-out plot
    # ------------------------------------------------------------------

    def _pop_out_plot(self) -> None:
        """Open the current plot in a detached dialog window."""
        if not self._plotted_keys:
            return

        dlg = QDialog(self)
        # Limit title length when many keys are plotted
        if len(self._plotted_keys) > 3:
            key_str = ", ".join(self._plotted_keys[:3]) + f"… (+{len(self._plotted_keys) - 3})"
        else:
            key_str = ", ".join(self._plotted_keys)
        dlg.setWindowTitle("Plot – " + key_str)
        dlg.resize(800, 500)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)

        fig = Figure(facecolor=BG_PRIMARY)
        canvas = FigureCanvasQTAgg(fig)
        ax = fig.add_subplot(111)

        # Copy current axes content to the new figure
        ax.set_facecolor(BG_SECONDARY)
        ax.tick_params(colors=TEXT_SECONDARY, which="both")
        ax.xaxis.label.set_color(TEXT_SECONDARY)
        ax.yaxis.label.set_color(TEXT_SECONDARY)
        ax.title.set_color(TEXT_PRIMARY)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        ax.grid(True, color=BG_TERTIARY, linewidth=0.5)

        if self._reader is not None:
            info = self._reader.get_info()
            for i, key in enumerate(self._plotted_keys):
                vector = self._reader.get_vector(key)
                if vector is None:
                    continue
                dates, values = vector
                color = _PLOT_COLORS[i % len(_PLOT_COLORS)]
                ax.plot(dates, values, color=color, linewidth=1.5, label=key)

            if self._plotted_keys:
                ax.set_title(
                    ", ".join(self._plotted_keys), fontsize=13, fontweight="bold"
                )
                ax.set_xlabel("Date", fontsize=11)
                unit = info.units.get(self._plotted_keys[0], "") if info else ""
                ax.set_ylabel(unit or "Value", fontsize=11)
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                fig.autofmt_xdate(rotation=30)
                ax.legend(
                    loc="best",
                    fontsize=10,
                    facecolor=BG_TERTIARY,
                    edgecolor=BORDER,
                    labelcolor=TEXT_PRIMARY,
                )
                fig.tight_layout()

        layout.addWidget(canvas)
        dlg.show()

    # ------------------------------------------------------------------
    # ResInsight
    # ------------------------------------------------------------------

    def _launch_resinsight(self) -> None:
        """Launch ResInsight with the current run's output files."""
        if self._current_run is None:
            return
        out_dir = Path(self._current_run.output_dir).resolve()
        binary = self._resinsight_binary or "ResInsight"

        # Prefer an EGRID file; fall back to SMSPEC; lastly open ResInsight with no file.
        egrid_files = sorted(out_dir.glob("*.EGRID"))
        smspec_files = sorted(out_dir.glob("*.SMSPEC"))
        case_file = (egrid_files or smspec_files or [None])[0]

        args: list[str] = [binary]
        if case_file is not None:
            args += ["--case", str(case_file)]

        try:
            subprocess.Popen(args)  # noqa: S603
        except FileNotFoundError:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "ResInsight Not Found",
                f"Could not launch ResInsight.\n"
                f"Configured binary: {binary}\n\n"
                "Please update the ResInsight binary path in Settings.",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to launch ResInsight: %s", exc)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _filter_keys(self, text: str) -> None:
        """Show only tree items whose key contains *text* (case-insensitive)."""
        needle = text.lower()
        root = self._tree.invisibleRootItem()
        for cat_idx in range(root.childCount()):
            cat_item = root.child(cat_idx)
            any_visible = False
            for key_idx in range(cat_item.childCount()):
                child = cat_item.child(key_idx)
                match = needle in child.text(0).lower()
                child.setHidden(not match)
                if match:
                    any_visible = True
            cat_item.setHidden(not any_visible)
            if any_visible and needle:
                cat_item.setExpanded(True)

    # ------------------------------------------------------------------
    # Empty state
    # ------------------------------------------------------------------

    def _show_empty_state(self) -> None:
        """Display the empty-state message and hide content widgets."""
        self._tabs.setVisible(False)
        self._empty_label.setVisible(True)
        self._empty_label.setText("Select a completed run to view results")
