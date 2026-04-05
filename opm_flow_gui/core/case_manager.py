"""Simulation case and run management for OPM Flow GUI."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RunStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SimulationRun:
    case_path: str
    output_dir: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: RunStatus = RunStatus.PENDING
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    started_at: str | None = None
    finished_at: str | None = None
    flow_options: dict[str, Any] = field(default_factory=dict)
    mpi_processes: int = 1
    progress: float = 0.0
    pid: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "case_path": self.case_path,
            "output_dir": self.output_dir,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "flow_options": dict(self.flow_options),
            "mpi_processes": self.mpi_processes,
            "progress": self.progress,
            "pid": self.pid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SimulationRun:
        return cls(
            case_path=str(data.get("case_path", "")),
            output_dir=str(data.get("output_dir", "")),
            run_id=str(data.get("run_id", str(uuid.uuid4()))),
            status=RunStatus(data.get("status", "pending")),
            created_at=str(data.get("created_at", "")),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            flow_options=dict(data.get("flow_options", {})),
            mpi_processes=int(data.get("mpi_processes", 1)),
            progress=float(data.get("progress", 0.0)),
            pid=data.get("pid"),
        )


@dataclass
class Case:
    data_file_path: str
    runs: list[SimulationRun] = field(default_factory=list)

    @property
    def name(self) -> str:
        return Path(self.data_file_path).stem

    @property
    def directory(self) -> str:
        return str(Path(self.data_file_path).parent)

    def add_run(self, run: SimulationRun) -> None:
        self.runs.append(run)

    def remove_run(self, run_id: str) -> None:
        self.runs = [r for r in self.runs if r.run_id != run_id]

    def get_run(self, run_id: str) -> SimulationRun | None:
        for run in self.runs:
            if run.run_id == run_id:
                return run
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_file_path": self.data_file_path,
            "runs": [r.to_dict() for r in self.runs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Case:
        runs = [SimulationRun.from_dict(r) for r in data.get("runs", [])]
        return cls(
            data_file_path=data.get("data_file_path", ""),
            runs=runs,
        )


class CaseManager:
    def __init__(self) -> None:
        self.cases: dict[str, Case] = {}

    def add_case(self, data_file_path: str) -> Case:
        if not data_file_path or not data_file_path.strip():
            raise ValueError("data_file_path cannot be empty")
        resolved = str(Path(data_file_path).resolve())
        if resolved not in self.cases:
            self.cases[resolved] = Case(data_file_path=resolved)
        return self.cases[resolved]

    def remove_case(self, data_file_path: str) -> None:
        resolved = str(Path(data_file_path).resolve())
        self.cases.pop(resolved, None)

    def discover_cases(self, directory: str) -> list[Case]:
        dir_path = Path(directory)
        if not dir_path.is_dir():
            logger.warning("Not a valid directory: %s", directory)
            return []
        discovered: list[Case] = []
        for path in sorted(dir_path.rglob("*.DATA")):
            case = self.add_case(str(path))
            discovered.append(case)
        return discovered

    def get_all_cases(self) -> list[Case]:
        return sorted(self.cases.values(), key=lambda c: c.data_file_path)

    def save(self, filepath: str) -> None:
        path = Path(filepath)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {"cases": [c.to_dict() for c in self.get_all_cases()]}
            path.write_text(
                json.dumps(data, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            logger.exception("Failed to save cases to %s", filepath)

    def load(self, filepath: str) -> None:
        path = Path(filepath)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            logger.warning("Malformed cases file %s – ignoring.", filepath)
            return
        self.cases.clear()
        for case_data in data.get("cases", []):
            case = Case.from_dict(case_data)
            self.cases[case.data_file_path] = case
