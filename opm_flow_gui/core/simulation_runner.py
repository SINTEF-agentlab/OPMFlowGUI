"""Run OPM Flow simulations as subprocesses and monitor their progress."""

from __future__ import annotations

import logging
import re
import subprocess
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QProcess, Signal

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .case_manager import SimulationRun

# ---------------------------------------------------------------------------
# OPM Flow help-text parser
# ---------------------------------------------------------------------------

# Matches an option definition line: "    --name=TYPE   description..."
_HELP_OPT_RE = re.compile(r"^ {4}--([^=\s]+)=(\w+)\s+(.*)")
# Matches a description continuation line (heavily indented, 20+ spaces)
_HELP_CONT_RE = re.compile(r"^ {20,}\S")
# Extracts the default value from "Default: <value>" at end of description
_DEFAULT_RE = re.compile(r"Default:\s*(.+?)\s*$", re.IGNORECASE)
# Extracts choices from "[opt1|opt2|opt3]" patterns
_CHOICES_RE = re.compile(r"\[([^\]]+)\]")

_TYPE_MAP: dict[str, str] = {
    "STRING": "string",
    "BOOLEAN": "bool",
    "INTEGER": "int",
    "SCALAR": "float",
}


def parse_flow_help(help_text: str) -> list[dict]:
    """Parse the output of ``flow --help`` into option descriptors.

    Each descriptor is a dict with keys ``name``, ``type``, ``default``,
    ``description`` and optionally ``choices`` (for string options that list
    valid values in the help text).

    Parameters
    ----------
    help_text:
        The full text printed by ``flow --help`` (stdout or stderr).

    Returns
    -------
    list[dict]
        Ordered list of option descriptors ready for use in :class:`RunDialog`.
    """
    options: list[dict] = []

    # First pass: collect (name, raw_type, description_lines) blocks
    current_name: str | None = None
    current_raw_type: str | None = None
    current_desc_parts: list[str] = []

    def _flush() -> None:
        if current_name is None:
            return
        full_desc = " ".join(current_desc_parts)
        opt = _build_option(current_name, current_raw_type or "STRING", full_desc)
        if opt is not None:
            options.append(opt)

    for line in help_text.splitlines():
        opt_match = _HELP_OPT_RE.match(line)
        if opt_match:
            _flush()
            current_name = opt_match.group(1)
            current_raw_type = opt_match.group(2)
            current_desc_parts = [opt_match.group(3).strip()]
        elif current_name and _HELP_CONT_RE.match(line):
            current_desc_parts.append(line.strip())

    _flush()
    return options


def _build_option(name: str, raw_type: str, description: str) -> dict | None:
    """Convert a raw option block into a descriptor dict."""
    opt_type = _TYPE_MAP.get(raw_type.upper(), "string")

    # Extract and strip the default value from the description
    default = ""
    dm = _DEFAULT_RE.search(description)
    if dm:
        raw_default = dm.group(1).strip()
        # Strip surrounding quotes from string defaults
        if len(raw_default) >= 2 and raw_default[0] == '"' and raw_default[-1] == '"':
            default = raw_default[1:-1]
        else:
            default = raw_default
        # Trim the "Default: …" suffix from the visible description
        description = description[: dm.start()].rstrip(". \t")

    if opt_type == "bool":
        default = default.lower()

    # Extract enumerated choices from "[a|b|c]" patterns (skip for booleans)
    choices: list[str] | None = None
    if opt_type != "bool":
        cm = _CHOICES_RE.search(description)
        if cm and "|" in cm.group(1):
            choices = [c.strip() for c in cm.group(1).split("|")]

    opt: dict = {
        "name": name,
        "type": opt_type,
        "default": default,
        "description": description.strip(),
    }
    if choices:
        opt["choices"] = choices
    return opt


# Cache parsed options per binary path so ``flow --help`` is only run once
_flow_options_cache: dict[str, list[dict]] = {}


def get_flow_options(flow_binary: str) -> list[dict]:
    """Return option descriptors for *flow_binary* by parsing ``--help``.

    The result is cached so the subprocess is only spawned once per binary
    path within a single process lifetime.  Returns an empty list if
    *flow_binary* cannot be executed.
    """
    if flow_binary in _flow_options_cache:
        return _flow_options_cache[flow_binary]

    try:
        result = subprocess.run(
            [flow_binary, "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # flow may print help to stdout or stderr depending on version
        text = result.stdout if result.stdout.strip() else result.stderr
        options = parse_flow_help(text)
    except Exception:
        logger.warning(
            "Could not run '%s --help'; no Flow options will be available",
            flow_binary,
        )
        options = []

    _flow_options_cache[flow_binary] = options
    return options


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
# Matches "Report step N of M" or "Report step N/M"
_RE_REPORT_STEP_OF = re.compile(
    r"Report\s+step\s+(\d+)\s*(?:of|/)\s*(\d+)",
    re.IGNORECASE,
)
_RE_TIME_STEP = re.compile(
    r"Time\s+step\s+\d+.*?at.*?day\s+([\d.eE+\-]+)",
    re.IGNORECASE,
)
# Also matches "Time: X days" or "Current time X days"
_RE_CURRENT_DAY = re.compile(
    r"(?:current\s+)?time[:\s]+(?:=\s*)?([\d.eE+\-]+)\s*days?",
    re.IGNORECASE,
)
_RE_TOTAL_TIME = re.compile(
    r"Simulation\s+(?:total\s+)?time.*?(\d[\d.eE+\-]*)\s*days",
    re.IGNORECASE,
)
# Total steps from "N report steps" or "N time steps"
_RE_TOTAL_STEPS = re.compile(
    r"(\d+)\s+report\s+steps",
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
        self._total_steps: dict[str, int] = {}

    # -- public API ---------------------------------------------------------

    def start_run(self, run: SimulationRun) -> bool:
        """Launch the OPM Flow subprocess for *run*.

        Returns ``True`` if the process was started successfully.
        """
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
        self._total_steps.pop(run_id, None)

        process.start(program, arguments)
        if not process.waitForStarted(5000):
            logger.error(
                "Failed to start process for run %s: %s",
                run_id,
                process.errorString(),
            )
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

            # Try to detect total number of report steps once
            if run_id not in self._total_steps:
                match = _RE_TOTAL_STEPS.search(line)
                if match:
                    try:
                        self._total_steps[run_id] = int(match.group(1))
                    except ValueError:
                        pass

            # Best case: "Report step N of M" gives exact percentage
            of_match = _RE_REPORT_STEP_OF.search(line)
            if of_match:
                try:
                    current = int(of_match.group(1))
                    total = int(of_match.group(2))
                    if total > 0:
                        progress = min(current / total * 100.0, 99.0)
                        self.progress_updated.emit(run_id, progress)
                        continue
                except ValueError:
                    pass

            # Estimate progress from current simulation day vs total time
            total_days = self._total_time.get(run_id)
            if total_days and total_days > 0:
                ts_match = _RE_TIME_STEP.search(line) or _RE_CURRENT_DAY.search(line)
                if ts_match:
                    try:
                        current_day = float(ts_match.group(1))
                        progress = min(current_day / total_days * 100.0, 99.0)
                        self.progress_updated.emit(run_id, progress)
                        continue
                    except ValueError:
                        pass

            # Use report step number vs known total steps
            total_steps = self._total_steps.get(run_id)
            rs_match = _RE_REPORT_STEP.search(line)
            if rs_match:
                try:
                    step = int(rs_match.group(1))
                    if total_steps and total_steps > 0:
                        progress = min(step / total_steps * 100.0, 99.0)
                    else:
                        # No total known: use step as an indeterminate hint,
                        # capped so 100 is reserved for actual completion.
                        progress = min(float(step), 99.0)
                    self.progress_updated.emit(run_id, progress)
                except ValueError:
                    pass

    def _on_process_finished(self, run_id: str, exit_code: int) -> None:
        """Handle subprocess completion."""
        self._processes.pop(run_id, None)
        self._total_time.pop(run_id, None)
        self._total_steps.pop(run_id, None)

        status = "completed" if exit_code == 0 else "failed"
        if status == "completed":
            self.progress_updated.emit(run_id, 100.0)
        self.run_finished.emit(run_id, status)
