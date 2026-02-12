"""PID file utilities for dev server process management."""

import os
from pathlib import Path

SERVER_NAMES: tuple[str, ...] = ("backend", "frontend")

_PID_DIR_NAME = ".dev_cli"


def pid_dir(repo_root: Path) -> Path:
    """Return the PID file directory, creating it if needed."""
    d = repo_root / _PID_DIR_NAME
    d.mkdir(exist_ok=True)
    return d


def pid_file_path(repo_root: Path, name: str) -> Path:
    """Return the path to a PID file (e.g. ``.dev_cli/backend.pid``)."""
    return pid_dir(repo_root) / f"{name}.pid"


def write_pid(repo_root: Path, name: str, pid: int) -> None:
    """Write a PID to its file."""
    _ = pid_file_path(repo_root, name).write_text(str(pid))


def read_pid(repo_root: Path, name: str) -> int | None:
    """Read a PID from its file.  Returns ``None`` if missing or malformed."""
    path = pid_file_path(repo_root, name)
    try:
        text = path.read_text().strip()
        return int(text)
    except (FileNotFoundError, ValueError):
        return None


def remove_pid(repo_root: Path, name: str) -> None:
    """Delete a PID file (silent if absent)."""
    try:
        pid_file_path(repo_root, name).unlink()
    except FileNotFoundError:
        pass


def is_process_alive(pid: int) -> bool:
    """Check whether a process with the given PID is alive."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't own it — still alive.
        return True
    return True
