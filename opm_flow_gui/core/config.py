"""Application configuration management for OPM Flow GUI."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_DIR = Path.home() / ".opm_flow_gui"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"


@dataclass
class Config:
    flow_binary: str = "flow"
    mpirun_binary: str = "mpirun"
    output_base_path: str = ""
    search_directories: list[str] = field(default_factory=list)
    case_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow_binary": self.flow_binary,
            "mpirun_binary": self.mpirun_binary,
            "output_base_path": self.output_base_path,
            "search_directories": list(self.search_directories),
            "case_files": list(self.case_files),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        return cls(
            flow_binary=data.get("flow_binary", "flow"),
            mpirun_binary=data.get("mpirun_binary", "mpirun"),
            output_base_path=data.get("output_base_path", ""),
            search_directories=list(data.get("search_directories", [])),
            case_files=list(data.get("case_files", [])),
        )


class ConfigManager:
    def __init__(self, config_path: str | None = None) -> None:
        self._path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._config = Config()
        self.load()

    @property
    def config(self) -> Config:
        return self._config

    def load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                self._config = Config()
                return
            self._config = Config.from_dict(data)
        else:
            self._config = Config()
            self.save()

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._config.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
