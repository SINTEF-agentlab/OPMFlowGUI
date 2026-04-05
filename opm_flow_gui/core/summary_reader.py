"""Summary file reader for OPM Flow simulation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    from resdata.summary import Summary

    _HAS_RESDATA = True
except ImportError:  # pragma: no cover
    _HAS_RESDATA = False
    print("Warning: resdata is not installed. Summary reading is disabled.")

_KEY_CATEGORIES: dict[str, str] = {
    "F": "Field",
    "W": "Well",
    "G": "Group",
    "R": "Region",
    "B": "Block",
}


@dataclass
class SummaryData:
    """Metadata extracted from a loaded summary file."""

    keys: list[str] = field(default_factory=list)
    dates: list[datetime] = field(default_factory=list)
    units: dict[str, str] = field(default_factory=dict)


class SummaryReader:
    """Read OPM Flow summary output files via *resdata*.

    Args:
        case_path: Base name (without extension) or path to a
            ``.DATA`` / ``.SMSPEC`` / ``.UNSMRY`` file.
    """

    def __init__(self, case_path: str) -> None:
        self._case_path = self._resolve_path(case_path)
        self._summary: Summary | None = None

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_path(case_path: str) -> str:
        """Resolve *case_path* to the extension-free base name that resdata expects."""
        p = Path(case_path)
        if p.suffix.upper() in {".DATA", ".SMSPEC", ".UNSMRY"}:
            return str(p.with_suffix(""))
        return str(p)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Attempt to load the summary file.

        Returns:
            ``True`` if the file was loaded successfully, ``False`` otherwise.
        """
        if not _HAS_RESDATA:
            return False
        try:
            self._summary = Summary(self._case_path)
        except Exception:  # noqa: BLE001
            return False
        return True

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_info(self) -> SummaryData | None:
        """Return high-level metadata for the loaded summary.

        Returns:
            A :class:`SummaryData` instance, or ``None`` when no file is loaded.
        """
        if self._summary is None:
            return None

        keys: list[str] = sorted(self._summary.keys())
        dates: list[datetime] = list(self._summary.dates)
        units: dict[str, str] = {k: self._summary.unit(k) for k in keys}
        return SummaryData(keys=keys, dates=dates, units=units)

    def get_vector(self, key: str) -> tuple[list[datetime], list[float]] | None:
        """Return ``(dates, values)`` for a single summary vector.

        Args:
            key: Summary vector name (e.g. ``"FOPT"``).

        Returns:
            A tuple of dates and float values, or ``None`` if the key is
            not available.
        """
        if self._summary is None or not self._summary.has_key(key):
            return None
        dates: list[datetime] = list(self._summary.dates)
        values: list[float] = list(self._summary.numpy_vector(key))
        return dates, values

    def get_vectors(
        self, keys: list[str]
    ) -> dict[str, tuple[list[datetime], list[float]]]:
        """Return multiple vectors at once.

        Args:
            keys: List of summary vector names.

        Returns:
            Mapping of each found key to its ``(dates, values)`` tuple.
            Keys that are not present in the summary are silently skipped.
        """
        result: dict[str, tuple[list[datetime], list[float]]] = {}
        for key in keys:
            vector = self.get_vector(key)
            if vector is not None:
                result[key] = vector
        return result

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def get_well_names(self) -> list[str]:
        """Extract unique well names from summary keys."""
        if self._summary is None:
            return []
        return sorted(
            {self._summary.smspec_node(k).wgname
             for k in self._summary.keys()
             if k.startswith("W") and self._summary.smspec_node(k).wgname}
        )

    def get_group_names(self) -> list[str]:
        """Extract unique group names from summary keys."""
        if self._summary is None:
            return []
        return sorted(
            {self._summary.smspec_node(k).wgname
             for k in self._summary.keys()
             if k.startswith("G") and self._summary.smspec_node(k).wgname}
        )

    def categorize_keys(self) -> dict[str, list[str]]:
        """Categorize summary keys by their first-letter prefix.

        Returns:
            Mapping of category name to sorted list of keys.  Categories
            are *Field*, *Well*, *Group*, *Region*, *Block*, and *Other*.
        """
        if self._summary is None:
            return {}

        categories: dict[str, list[str]] = {v: [] for v in _KEY_CATEGORIES.values()}
        categories["Other"] = []

        for key in sorted(self._summary.keys()):
            prefix = key[0] if key else ""
            category = _KEY_CATEGORIES.get(prefix, "Other")
            categories[category].append(key)

        return {k: v for k, v in categories.items() if v}
