"""Application configuration management for OPM Flow GUI."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from opm_flow_gui.core.wsl_utils import should_default_use_wsl

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_DIR = Path.home() / ".opm_flow_gui"
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.json"


@dataclass
class Config:
    flow_binary: str = "flow"
    mpirun_binary: str = "mpirun"
    resinsight_binary: str = "ResInsight"
    output_base_path: str = ""
    search_directories: list[str] = field(default_factory=list)
    case_files: list[str] = field(default_factory=list)
    theme: str = "Dark Purple"
    use_wsl: bool = field(default_factory=should_default_use_wsl)

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow_binary": self.flow_binary,
            "mpirun_binary": self.mpirun_binary,
            "resinsight_binary": self.resinsight_binary,
            "output_base_path": self.output_base_path,
            "search_directories": list(self.search_directories),
            "case_files": list(self.case_files),
            "theme": self.theme,
            "use_wsl": self.use_wsl,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        flow_binary = str(data.get("flow_binary", "flow"))
        # If "use_wsl" was never saved before, auto-detect the right default.
        if "use_wsl" in data:
            use_wsl = bool(data["use_wsl"])
        else:
            use_wsl = should_default_use_wsl(flow_binary)
        return cls(
            flow_binary=flow_binary,
            mpirun_binary=str(data.get("mpirun_binary", "mpirun")),
            resinsight_binary=str(data.get("resinsight_binary", "ResInsight")),
            output_base_path=str(data.get("output_base_path", "")),
            search_directories=[str(d) for d in data.get("search_directories", [])],
            case_files=[str(f) for f in data.get("case_files", [])],
            theme=str(data.get("theme", "Dark Purple")),
            use_wsl=use_wsl,
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
                logger.warning("Malformed config file %s – using defaults.", self._path)
                self._config = Config()
                return
            self._config = Config.from_dict(data)
        else:
            self._config = Config()
            self.save()

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._config.to_dict(), indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            logger.exception("Failed to save config to %s", self._path)
