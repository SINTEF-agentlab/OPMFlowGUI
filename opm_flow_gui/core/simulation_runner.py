"""Run OPM Flow simulations as subprocesses and monitor their progress."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QProcess, Signal

if TYPE_CHECKING:
    from .case_manager import SimulationRun

# ---------------------------------------------------------------------------
# OPM Flow command-line option descriptors
# ---------------------------------------------------------------------------

OPM_FLOW_OPTIONS: list[dict] = [
    {
        "name": "linear-solver",
        "type": "string",
        "default": "cpr_trueimpes",
        "description": "Linear solver method",
        "choices": ["cpr_trueimpes", "cpr_quasiimpes", "ilu0", "amg"],
    },
    {
        "name": "tolerance-mb",
        "type": "float",
        "default": "1e-6",
        "description": "Tolerance for mass balance equations",
    },
    {
        "name": "tolerance-cnv",
        "type": "float",
        "default": "1e-2",
        "description": "Tolerance for CNV convergence criterion",
    },
    {
        "name": "tolerance-cnv-relaxed",
        "type": "float",
        "default": "1e9",
        "description": "Relaxed tolerance for CNV convergence criterion",
    },
    {
        "name": "tolerance-wells",
        "type": "float",
        "default": "1e-4",
        "description": "Tolerance for well equations",
    },
    {
        "name": "max-inner-iterations",
        "type": "int",
        "default": "50",
        "description": "Maximum number of inner linear solver iterations",
    },
    {
        "name": "newton-max-iterations",
        "type": "int",
        "default": "20",
        "description": "Maximum number of Newton iterations per time step",
    },
    {
        "name": "enable-tuning",
        "type": "bool",
        "default": "false",
        "description": "Honor TUNING keyword settings from the deck",
    },
    {
        "name": "enable-opm-rst-file",
        "type": "bool",
        "default": "false",
        "description": "Write OPM-native restart files",
    },
    {
        "name": "output-extra-convergence-info",
        "type": "string",
        "default": "none",
        "description": "Extra convergence information to output",
        "choices": ["none", "steps", "iterations"],
    },
    {
        "name": "relaxed-max-pv-fraction",
        "type": "float",
        "default": "0.03",
        "description": "Max pore-volume fraction for relaxed CNV convergence",
    },
    {
        "name": "solver-approach",
        "type": "string",
        "default": "fully_implicit",
        "description": "Solver approach for the simulation",
        "choices": ["fully_implicit"],
    },
    {
        "name": "threads-per-process",
        "type": "int",
        "default": "1",
        "description": "Number of threads per MPI process",
    },
    {
        "name": "enable-adaptive-time-stepping",
        "type": "bool",
        "default": "true",
        "description": "Enable adaptive time stepping",
    },
    {
        "name": "time-step-control",
        "type": "string",
        "default": "pid",
        "description": "Time step control strategy",
        "choices": ["pid", "pid+newtoniterationcount", "simple", "hardcoded"],
    },
    {
        "name": "max-time-step-in-days",
        "type": "float",
        "default": "365.0",
        "description": "Maximum time step size in days",
    },
    {
        "name": "min-time-step-in-days",
        "type": "float",
        "default": "0.0",
        "description": "Minimum time step size in days",
    },
    {
        "name": "max-restarts",
        "type": "int",
        "default": "10",
        "description": "Maximum number of solver restarts per time step",
    },
    {
        "name": "ecl-output",
        "type": "bool",
        "default": "true",
        "description": "Write Eclipse-compatible output files",
    },
    {
        "name": "output-mode",
        "type": "string",
        "default": "all",
        "description": "Controls which data is written to output files",
        "choices": ["all", "none", "steps"],
    },
    {
        "name": "enable-dry-run",
        "type": "bool",
        "default": "false",
        "description": "Perform input-only run without simulation",
    },
]


# ---------------------------------------------------------------------------
# Helper: build the command list for a simulation run
# ---------------------------------------------------------------------------

def build_flow_command(
    run: SimulationRun,
    flow_binary: str = "flow",
    mpirun_binary: str = "mpirun",
) -> list[str]:
    """Build the full command list to launch an OPM Flow simulation.

    Parameters
    ----------
    run:
        A :class:`SimulationRun` instance describing the case and options.
    flow_binary:
        Path or name of the ``flow`` executable.
    mpirun_binary:
        Path or name of the ``mpirun`` executable.

    Returns
    -------
    list[str]
        The command and arguments ready for :class:`QProcess`.
    """
    flow_args: list[str] = [run.case_path, f"--output-dir={run.output_dir}"]

    for key, value in run.flow_options.items():
        flow_args.append(f"--{key}={value}")

    if run.mpi_processes > 1:
        return [
            mpirun_binary,
            "-np",
            str(run.mpi_processes),
            flow_binary,
            *flow_args,
        ]

    return [flow_binary, *flow_args]


# ---------------------------------------------------------------------------
# Regex patterns used to estimate simulation progress
# ---------------------------------------------------------------------------

_RE_REPORT_STEP = re.compile(
    r"Report\s+step\s+(\d+)",
    re.IGNORECASE,
)
_RE_TIME_STEP = re.compile(
    r"Time\s+step\s+\d+.*?at.*?day\s+([\d.eE+\-]+)",
    re.IGNORECASE,
)
_RE_TOTAL_TIME = re.compile(
    r"Simulation\s+(?:total\s+)?time.*?(\d[\d.eE+\-]*)\s*days",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# SimulationRunner
# ---------------------------------------------------------------------------

class SimulationRunner(QObject):
    """Manage OPM Flow subprocess execution and progress monitoring."""

    progress_updated = Signal(str, float)   # (run_id, progress 0-100)
    run_finished = Signal(str, str)         # (run_id, "completed" | "failed")
    output_received = Signal(str, str)      # (run_id, line)

    def __init__(
        self,
        flow_binary: str = "flow",
        mpirun_binary: str = "mpirun",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._flow_binary = flow_binary
        self._mpirun_binary = mpirun_binary
        self._processes: dict[str, QProcess] = {}
        self._total_time: dict[str, float] = {}

    # -- public API ---------------------------------------------------------

    def start_run(self, run: SimulationRun) -> bool:
        """Launch the OPM Flow subprocess for *run*.

        Returns ``True`` if the process was started successfully.
        """
        from .case_manager import SimulationRun as _SR  # noqa: F811

        if run.run_id in self._processes:
            return False

        cmd = build_flow_command(run, self._flow_binary, self._mpirun_binary)
        program = cmd[0]
        arguments = cmd[1:]

        process = QProcess(self)
        process.setWorkingDirectory(run.output_dir)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

        run_id = run.run_id

        process.readyReadStandardOutput.connect(
            lambda rid=run_id: self._parse_output(rid)
        )
        process.finished.connect(
            lambda exit_code, _status, rid=run_id: self._on_process_finished(
                rid, exit_code
            )
        )

        self._processes[run_id] = process
        self._total_time.pop(run_id, None)

        process.start(program, arguments)
        if not process.waitForStarted(5000):
            self._processes.pop(run_id, None)
            return False

        return True

    def cancel_run(self, run_id: str) -> None:
        """Kill a running simulation process."""
        process = self._processes.get(run_id)
        if process is None:
            return
        process.kill()

    # -- internal -----------------------------------------------------------

    def _parse_output(self, run_id: str) -> None:
        """Read available stdout data and emit signals."""
        process = self._processes.get(run_id)
        if process is None:
            return

        raw = process.readAllStandardOutput()
        if raw is None:
            return

        text = bytes(raw).decode("utf-8", errors="replace")

        for line in text.splitlines():
            self.output_received.emit(run_id, line)

            # Try to detect total simulation time once
            if run_id not in self._total_time:
                match = _RE_TOTAL_TIME.search(line)
                if match:
                    try:
                        self._total_time[run_id] = float(match.group(1))
                    except ValueError:
                        pass

            # Estimate progress from current simulation day
            total = self._total_time.get(run_id)
            if total and total > 0:
                ts_match = _RE_TIME_STEP.search(line)
                if ts_match:
                    try:
                        current_day = float(ts_match.group(1))
                        progress = min(current_day / total * 100.0, 100.0)
                        self.progress_updated.emit(run_id, progress)
                    except ValueError:
                        pass

            # Fallback: emit report-step-based progress (no total known)
            if run_id not in self._total_time:
                rs_match = _RE_REPORT_STEP.search(line)
                if rs_match:
                    try:
                        step = int(rs_match.group(1))
                        # Without total time we report step number as a hint;
                        # cap at 99 so 100 is only sent on completion.
                        progress = min(float(step), 99.0)
                        self.progress_updated.emit(run_id, progress)
                    except ValueError:
                        pass

    def _on_process_finished(self, run_id: str, exit_code: int) -> None:
        """Handle subprocess completion."""
        self._processes.pop(run_id, None)
        self._total_time.pop(run_id, None)

        status = "completed" if exit_code == 0 else "failed"
        if status == "completed":
            self.progress_updated.emit(run_id, 100.0)
        self.run_finished.emit(run_id, status)
