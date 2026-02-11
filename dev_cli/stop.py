"""Stop command — terminate running dev servers via PID files."""

import os
import signal
import sys
import time
from pathlib import Path

from .output import print_error, print_info
from .pidfile import SERVER_NAMES, is_process_alive, read_pid, remove_pid

_TERM_TIMEOUT: float = 5.0


def _stop_one(repo_root: Path, name: str, *, force: bool) -> bool:
    """Stop a single server by name.  Returns ``True`` on success."""
    pid = read_pid(repo_root, name)
    if pid is None:
        print_info(f"{name}: not running (no PID file)")
        return True

    if not is_process_alive(pid):
        print_info(f"{name}: stale PID file (pid={pid}), cleaning up")
        remove_pid(repo_root, name)
        return True

    sig = signal.SIGKILL if force else signal.SIGTERM
    sig_name = "SIGKILL" if force else "SIGTERM"

    try:
        if sys.platform != "win32":
            os.killpg(pid, sig)
        else:
            os.kill(pid, sig)
    except ProcessLookupError:
        # Raced — already dead.
        remove_pid(repo_root, name)
        return True
    except PermissionError:
        print_error(f"{name}: permission denied sending {sig_name} to pid={pid}")
        return False

    print_info(f"{name}: sent {sig_name} to pid={pid}")

    if force:
        remove_pid(repo_root, name)
        return True

    # Wait for graceful exit with exponential backoff.
    deadline = time.monotonic() + _TERM_TIMEOUT
    delay = 0.05
    while time.monotonic() < deadline:
        if not is_process_alive(pid):
            print_info(f"{name}: stopped")
            remove_pid(repo_root, name)
            return True
        time.sleep(delay)
        delay = min(delay * 2, 0.25)

    # Escalate to SIGKILL.
    print_info(f"{name}: did not exit in {_TERM_TIMEOUT:.0f}s — sending SIGKILL")
    try:
        if sys.platform != "win32":
            os.killpg(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        print_error(f"{name}: permission denied sending SIGKILL to pid={pid}")
        return False

    remove_pid(repo_root, name)
    return True


def stop_servers(
    repo_root: Path,
    *,
    force: bool = False,
    backend_only: bool = False,
    frontend_only: bool = False,
) -> int:
    """Stop running dev servers.  Returns 0 on success, 1 on failure."""
    if backend_only:
        targets = ("backend",)
    elif frontend_only:
        targets = ("frontend",)
    else:
        targets = SERVER_NAMES

    ok = True
    for name in targets:
        if not _stop_one(repo_root, name, force=force):
            ok = False

    return 0 if ok else 1
