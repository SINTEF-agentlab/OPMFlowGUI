"""WSL (Windows Subsystem for Linux) utility helpers for OPM Flow GUI.

Only relevant on Microsoft Windows; all helpers are safe to call on other
platforms (they simply return sensible no-op values).
"""

from __future__ import annotations

import re
import shutil
import sys


def is_windows() -> bool:
    """Return ``True`` when the GUI is running on Microsoft Windows."""
    return sys.platform == "win32"


def is_wsl_available() -> bool:
    """Return ``True`` if WSL is installed and reachable on this system.

    Always returns ``False`` on non-Windows platforms.
    """
    if not is_windows():
        return False
    return shutil.which("wsl") is not None


def should_default_use_wsl(flow_binary: str = "flow") -> bool:
    """Return ``True`` if WSL should be enabled by default.

    The heuristic is: running on Windows **and** WSL is available **and**
    *flow_binary* cannot be resolved in the native Windows PATH.
    """
    if not is_windows():
        return False
    if not is_wsl_available():
        return False
    return shutil.which(flow_binary) is None


def windows_path_to_wsl(path: str) -> str:
    """Convert a Windows absolute path to its WSL ``/mnt/<drive>/…`` form.

    Paths that are already UNIX-style (no drive letter) are returned
    unchanged except that back-slashes are normalised to forward-slashes.

    Examples
    --------
    >>> windows_path_to_wsl("C:\\\\Users\\\\alice\\\\sim.DATA")
    '/mnt/c/Users/alice/sim.DATA'
    >>> windows_path_to_wsl("D:/models/reservoir")
    '/mnt/d/models/reservoir'
    >>> windows_path_to_wsl("/already/unix")
    '/already/unix'
    """
    m = re.match(r"^([A-Za-z]):[/\\](.*)", path)
    if m:
        drive = m.group(1).lower()
        rest = m.group(2).replace("\\", "/")
        if rest:
            return f"/mnt/{drive}/{rest}"
        return f"/mnt/{drive}"
    # Already UNIX-style or relative – normalise separators only
    return path.replace("\\", "/")
