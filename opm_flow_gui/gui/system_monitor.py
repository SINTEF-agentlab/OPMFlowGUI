"""System resource monitor panel for OPM Flow GUI.

Displays live CPU core utilisation, memory usage and a list of running
OPM Flow processes in a dashboard-style layout.  Data is collected in a
background :class:`~PySide6.QtCore.QThread` to avoid blocking the GUI on
Windows where :mod:`psutil` process enumeration can be slow.
"""

from __future__ import annotations

import logging

import psutil

from PySide6.QtCore import QMetaObject, QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import opm_flow_gui.gui.styles as _styles

logger = logging.getLogger(__name__)

_REFRESH_INTERVAL_MS = 5000


def _pct_color(pct: float) -> str:
    """Return a colour string that transitions green → amber → red with load."""
    if pct < 60:
        return _styles.SUCCESS
    if pct < 85:
        return _styles.WARNING
    return _styles.ERROR


# ---------------------------------------------------------------------------
# Background worker – runs psutil calls off the GUI thread
# ---------------------------------------------------------------------------

class _MonitorWorker(QObject):
    """Collects system metrics in a background thread and emits the results."""

    data_ready = Signal(object)  # emits a dict with collected metrics

    @Slot()
    def collect(self) -> None:
        """Gather CPU, memory and OPM Flow process data, then emit *data_ready*."""
        result: dict = {"cpu_per": [], "cpu_avg": 0.0, "mem": None, "procs": []}

        try:
            per_cpu: list[float] = psutil.cpu_percent(interval=None, percpu=True)  # type: ignore[assignment]
            result["cpu_per"] = per_cpu
            result["cpu_avg"] = sum(per_cpu) / len(per_cpu) if per_cpu else 0.0
        except Exception:
            pass

        try:
            result["mem"] = psutil.virtual_memory()
        except Exception:
            pass

        try:
            flow_procs: list[dict] = []
            for proc in psutil.process_iter(
                ["pid", "name", "cpu_percent", "memory_info", "status"]
            ):
                try:
                    name = (proc.info.get("name") or "").lower()
                    if name == "flow" or name.startswith("flow_") or name == "opm-flow":
                        mem_info = proc.info.get("memory_info")
                        mem_mb = mem_info.rss / (1024 ** 2) if mem_info else 0.0
                        flow_procs.append({
                            "pid": proc.info.get("pid", ""),
                            "name": proc.info.get("name", ""),
                            "cpu": proc.info.get("cpu_percent") or 0.0,
                            "mem_mb": mem_mb,
                            "status": proc.info.get("status", ""),
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            result["procs"] = flow_procs
        except Exception:
            pass

        self.data_ready.emit(result)


class _MetricCard(QFrame):
    """A small dashboard card showing a title, a large value and a sub-label."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            f"QFrame {{ background-color: {_styles.BG_SECONDARY}; border: 1px solid {_styles.BORDER};"
            f" border-radius: 8px; padding: 4px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(
            f"color: {_styles.TEXT_MUTED}; font-size: 11px; font-weight: 600;"
            " text-transform: uppercase; background: transparent; border: none;"
        )
        layout.addWidget(self._title_lbl)

        self._value_lbl = QLabel("—")
        self._value_lbl.setStyleSheet(
            f"color: {_styles.TEXT_PRIMARY}; font-size: 22px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        layout.addWidget(self._value_lbl)

        self._sub_lbl = QLabel("")
        self._sub_lbl.setStyleSheet(
            f"color: {_styles.TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none;"
        )
        layout.addWidget(self._sub_lbl)

    def set_value(self, value: str, color: str | None = None) -> None:
        self._value_lbl.setText(value)
        style = (
            f"color: {color}; font-size: 22px; font-weight: bold;"
            " background: transparent; border: none;"
        ) if color else (
            f"color: {_styles.TEXT_PRIMARY}; font-size: 22px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        self._value_lbl.setStyleSheet(style)

    def set_sub(self, text: str) -> None:
        self._sub_lbl.setText(text)

    def refresh_styles(self) -> None:
        """Re-apply inline stylesheets using the current active theme colours."""
        self.setStyleSheet(
            f"QFrame {{ background-color: {_styles.BG_SECONDARY}; border: 1px solid {_styles.BORDER};"
            f" border-radius: 8px; padding: 4px; }}"
        )
        self._title_lbl.setStyleSheet(
            f"color: {_styles.TEXT_MUTED}; font-size: 11px; font-weight: 600;"
            " text-transform: uppercase; background: transparent; border: none;"
        )
        self._value_lbl.setStyleSheet(
            f"color: {_styles.TEXT_PRIMARY}; font-size: 22px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        self._sub_lbl.setStyleSheet(
            f"color: {_styles.TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none;"
        )


class _CpuCoreBar(QWidget):
    """A labelled progress bar showing utilisation for a single CPU core."""

    def __init__(self, core_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._last_color: str = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)

        self._label = QLabel(f"CPU {core_index}")
        self._label.setFixedWidth(46)
        self._label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._label.setStyleSheet(
            f"color: {_styles.TEXT_MUTED}; font-size: 10px; background: transparent;"
        )
        layout.addWidget(self._label)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(10)
        self._bar.setStyleSheet(
            f"QProgressBar {{ background-color: {_styles.BG_TERTIARY}; border: none;"
            f" border-radius: 5px; }}"
            f" QProgressBar::chunk {{ background-color: {_styles.ACCENT}; border-radius: 5px; }}"
        )
        layout.addWidget(self._bar, 1)

        self._pct_label = QLabel("0%")
        self._pct_label.setFixedWidth(36)
        self._pct_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._pct_label.setStyleSheet(
            f"color: {_styles.TEXT_SECONDARY}; font-size: 10px; background: transparent;"
        )
        layout.addWidget(self._pct_label)

    def update_value(self, pct: float) -> None:
        ipct = int(pct)
        self._bar.setValue(ipct)
        self._pct_label.setText(f"{ipct}%")
        color = _pct_color(pct)
        if color != self._last_color:
            self._last_color = color
            self._bar.setStyleSheet(
                f"QProgressBar {{ background-color: {_styles.BG_TERTIARY}; border: none;"
                f" border-radius: 5px; }}"
                f" QProgressBar::chunk {{ background-color: {color}; border-radius: 5px; }}"
            )

    def refresh_styles(self) -> None:
        """Re-apply inline stylesheets using the current active theme colours."""
        self._label.setStyleSheet(
            f"color: {_styles.TEXT_MUTED}; font-size: 10px; background: transparent;"
        )
        pct = self._bar.value()
        color = _pct_color(pct)
        self._last_color = color  # resync cache with the newly applied stylesheet
        self._bar.setStyleSheet(
            f"QProgressBar {{ background-color: {_styles.BG_TERTIARY}; border: none;"
            f" border-radius: 5px; }}"
            f" QProgressBar::chunk {{ background-color: {color}; border-radius: 5px; }}"
        )
        self._pct_label.setStyleSheet(
            f"color: {_styles.TEXT_SECONDARY}; font-size: 10px; background: transparent;"
        )


class SystemMonitorPanel(QWidget):
    """Dashboard panel showing CPU, memory and OPM Flow process information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cpu_bars: list[_CpuCoreBar] = []
        self._started_once: bool = False
        self._setup_ui()

        # Background thread for psutil data collection (avoids GUI freezes on Windows)
        self._worker_thread = QThread(self)
        self._worker = _MonitorWorker()
        self._worker.moveToThread(self._worker_thread)
        self._worker.data_ready.connect(self._on_data_ready)
        self._worker_thread.start()

        # Timer fires on the GUI thread and triggers the worker via a queued connection.
        # The timer is started lazily by start() so it does not consume resources
        # while the System Monitor tab is not visible.
        self._timer = QTimer(self)
        self._timer.setInterval(_REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._worker.collect)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ── Summary cards row ────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)

        self._card_cpu_avg = _MetricCard("CPU Average")
        self._card_flow_count = _MetricCard("Flow Processes")
        self._card_mem_used = _MetricCard("Memory Used")
        self._card_mem_avail = _MetricCard("Memory Available")

        for card in (
            self._card_cpu_avg,
            self._card_flow_count,
            self._card_mem_used,
            self._card_mem_avail,
        ):
            card.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            cards_row.addWidget(card)

        root.addLayout(cards_row)

        # ── Per-core CPU bars ────────────────────────────────────────────
        self._cpu_section = QWidget()
        self._cpu_section.setStyleSheet(
            f"QWidget {{ background-color: {_styles.BG_SECONDARY}; border: 1px solid {_styles.BORDER};"
            f" border-radius: 8px; }}"
        )
        cpu_outer = QVBoxLayout(self._cpu_section)
        cpu_outer.setContentsMargins(12, 10, 12, 10)
        cpu_outer.setSpacing(6)

        self._cpu_title = QLabel("Per-Core CPU Utilisation")
        self._cpu_title.setStyleSheet(
            f"color: {_styles.ACCENT_LIGHT}; font-size: 13px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        cpu_outer.addWidget(self._cpu_title)

        # Scrollable core-bar grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        bars_widget = QWidget()
        bars_widget.setStyleSheet("background: transparent;")
        n_cores = psutil.cpu_count(logical=True) or 1

        # Two-column grid of core bars
        grid = QGridLayout(bars_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        cols = 2 if n_cores > 8 else 1

        for i in range(n_cores):
            bar = _CpuCoreBar(i)
            self._cpu_bars.append(bar)
            grid.addWidget(bar, i // cols, i % cols)

        scroll.setWidget(bars_widget)
        cpu_outer.addWidget(scroll, 1)

        root.addWidget(self._cpu_section, 1)

        # ── Flow processes table ─────────────────────────────────────────
        self._proc_section = QWidget()
        self._proc_section.setStyleSheet(
            f"QWidget {{ background-color: {_styles.BG_SECONDARY}; border: 1px solid {_styles.BORDER};"
            f" border-radius: 8px; }}"
        )
        proc_outer = QVBoxLayout(self._proc_section)
        proc_outer.setContentsMargins(12, 10, 12, 10)
        proc_outer.setSpacing(6)

        self._proc_title = QLabel("Running OPM Flow Processes")
        self._proc_title.setStyleSheet(
            f"color: {_styles.ACCENT_LIGHT}; font-size: 13px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        proc_outer.addWidget(self._proc_title)

        self._proc_table = QTableWidget(0, 5)
        self._proc_table.setHorizontalHeaderLabels(
            ["PID", "Name", "CPU %", "Memory", "Status"]
        )
        self._proc_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._proc_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._proc_table.setAlternatingRowColors(True)
        self._proc_table.verticalHeader().setVisible(False)
        self._proc_table.horizontalHeader().setStretchLastSection(True)
        self._proc_table.setShowGrid(False)
        self._proc_table.setStyleSheet(
            f"QTableWidget {{ background-color: {_styles.BG_PRIMARY}; border: none;"
            f" gridline-color: {_styles.BORDER}; }}"
            f" QTableWidget::item {{ padding: 4px 8px; }}"
        )
        proc_outer.addWidget(self._proc_table, 1)

        self._no_proc_label = QLabel("No OPM Flow processes currently running")
        self._no_proc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_proc_label.setStyleSheet(
            f"color: {_styles.TEXT_MUTED}; font-size: 12px; background: transparent; border: none;"
        )
        proc_outer.addWidget(self._no_proc_label)

        root.addWidget(self._proc_section, 1)

    # ------------------------------------------------------------------
    # Slot – receives results from the background worker
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_data_ready(self, data: dict) -> None:
        """Update all widgets from data collected by *_MonitorWorker*."""
        # CPU
        per_cpu: list[float] = data.get("cpu_per", [])
        for i, bar in enumerate(self._cpu_bars):
            if i < len(per_cpu):
                bar.update_value(per_cpu[i])
        avg: float = data.get("cpu_avg", 0.0)
        self._card_cpu_avg.set_value(f"{avg:.0f}%", _pct_color(avg))
        self._card_cpu_avg.set_sub(f"{len(per_cpu)} logical cores")

        # Memory
        mem = data.get("mem")
        if mem is not None:
            used_gb = mem.used / (1024 ** 3)
            avail_gb = mem.available / (1024 ** 3)
            total_gb = mem.total / (1024 ** 3)
            self._card_mem_used.set_value(f"{used_gb:.1f} GB", _pct_color(mem.percent))
            self._card_mem_used.set_sub(f"{mem.percent:.0f}% of {total_gb:.1f} GB")
            self._card_mem_avail.set_value(f"{avail_gb:.1f} GB")
            self._card_mem_avail.set_sub(f"{(100 - mem.percent):.0f}% free")

        # OPM Flow processes
        flow_procs: list[dict] = data.get("procs", [])
        count = len(flow_procs)
        self._card_flow_count.set_value(
            str(count),
            _styles.ACCENT if count > 0 else _styles.TEXT_MUTED,
        )
        self._card_flow_count.set_sub("process" if count == 1 else "processes")

        self._proc_table.setRowCount(count)
        has_procs = bool(flow_procs)
        self._proc_table.setVisible(has_procs)
        self._no_proc_label.setVisible(not has_procs)

        for row, p in enumerate(flow_procs):
            pid_item = QTableWidgetItem(str(p["pid"]))
            pid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._proc_table.setItem(row, 0, pid_item)

            self._proc_table.setItem(row, 1, QTableWidgetItem(str(p["name"])))

            cpu_item = QTableWidgetItem(f"{p['cpu']:.1f}%")
            cpu_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._proc_table.setItem(row, 2, cpu_item)

            mem_item = QTableWidgetItem(f"{p['mem_mb']:.0f} MB")
            mem_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._proc_table.setItem(row, 3, mem_item)

            status_item = QTableWidgetItem(str(p["status"]))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._proc_table.setItem(row, 4, status_item)

        if has_procs:
            self._proc_table.resizeColumnsToContents()
            self._proc_table.horizontalHeader().setStretchLastSection(True)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the refresh timer (called when the tab becomes visible)."""
        if not self._timer.isActive():
            self._timer.start()
        if not self._started_once:
            # Trigger an immediate first collection via a queued cross-thread
            # invocation so it always runs in the worker thread, preventing a
            # GUI freeze from slow psutil calls (e.g. process enumeration).
            self._started_once = True
            QMetaObject.invokeMethod(
                self._worker, "collect", Qt.ConnectionType.QueuedConnection
            )

    def stop(self) -> None:
        """Stop the refresh timer (called when the tab is hidden)."""
        self._timer.stop()

    def shutdown(self) -> None:
        """Stop the timer and cleanly shut down the background worker thread.

        Must be called before the widget (or its parent window) is destroyed to
        prevent the "QThread: Destroyed while thread is still running" warning.
        """
        self._timer.stop()
        self._worker_thread.quit()
        self._worker_thread.wait(2000)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Stop the timer and worker thread on close."""
        self.shutdown()
        super().closeEvent(event)

    def refresh_styles(self) -> None:
        """Re-apply inline stylesheets using the current active theme colours."""
        for card in (
            self._card_cpu_avg,
            self._card_flow_count,
            self._card_mem_used,
            self._card_mem_avail,
        ):
            card.refresh_styles()

        for bar in self._cpu_bars:
            bar.refresh_styles()

        self._cpu_section.setStyleSheet(
            f"QWidget {{ background-color: {_styles.BG_SECONDARY}; border: 1px solid {_styles.BORDER};"
            f" border-radius: 8px; }}"
        )
        self._cpu_title.setStyleSheet(
            f"color: {_styles.ACCENT_LIGHT}; font-size: 13px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        self._proc_section.setStyleSheet(
            f"QWidget {{ background-color: {_styles.BG_SECONDARY}; border: 1px solid {_styles.BORDER};"
            f" border-radius: 8px; }}"
        )
        self._proc_title.setStyleSheet(
            f"color: {_styles.ACCENT_LIGHT}; font-size: 13px; font-weight: bold;"
            " background: transparent; border: none;"
        )
        self._proc_table.setStyleSheet(
            f"QTableWidget {{ background-color: {_styles.BG_PRIMARY}; border: none;"
            f" gridline-color: {_styles.BORDER}; }}"
            f" QTableWidget::item {{ padding: 4px 8px; }}"
        )
        self._no_proc_label.setStyleSheet(
            f"color: {_styles.TEXT_MUTED}; font-size: 12px; background: transparent; border: none;"
        )
