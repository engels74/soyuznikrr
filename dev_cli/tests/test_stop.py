"""Tests for dev_cli.stop module."""

import signal
from pathlib import Path
from unittest.mock import patch

from dev_cli.pidfile import write_pid
from dev_cli.stop import stop_servers


def test_no_pid_files(tmp_path: Path) -> None:
    assert stop_servers(tmp_path) == 0


def test_stale_pid_cleanup(tmp_path: Path) -> None:
    write_pid(tmp_path, "backend", 2**30)  # Bogus PID, not alive.
    assert stop_servers(tmp_path) == 0
    # PID file should be removed.
    assert not (tmp_path / ".dev_cli" / "backend.pid").exists()


def test_alive_process_sigterm(tmp_path: Path) -> None:
    write_pid(tmp_path, "backend", 42)

    with (
        patch("dev_cli.stop.is_process_alive", side_effect=[True, False]),
        patch("dev_cli.stop.os.killpg") as mock_killpg,
    ):
        result = stop_servers(tmp_path, backend_only=True)

    assert result == 0
    mock_killpg.assert_called_once_with(42, signal.SIGTERM)
    assert not (tmp_path / ".dev_cli" / "backend.pid").exists()


def test_force_sends_sigkill(tmp_path: Path) -> None:
    write_pid(tmp_path, "frontend", 99)

    with (
        patch("dev_cli.stop.is_process_alive", return_value=True),
        patch("dev_cli.stop.os.killpg") as mock_killpg,
    ):
        result = stop_servers(tmp_path, force=True, frontend_only=True)

    assert result == 0
    mock_killpg.assert_called_once_with(99, signal.SIGKILL)


def test_permission_error(tmp_path: Path) -> None:
    write_pid(tmp_path, "backend", 42)

    with (
        patch("dev_cli.stop.is_process_alive", return_value=True),
        patch("dev_cli.stop.os.killpg", side_effect=PermissionError),
    ):
        result = stop_servers(tmp_path, backend_only=True)

    assert result == 1


def test_process_dies_during_kill(tmp_path: Path) -> None:
    """Process dies between is_process_alive and killpg → treated as success."""
    write_pid(tmp_path, "backend", 42)

    with (
        patch("dev_cli.stop.is_process_alive", return_value=True),
        patch("dev_cli.stop.os.killpg", side_effect=ProcessLookupError),
    ):
        result = stop_servers(tmp_path, backend_only=True)

    assert result == 0
    assert not (tmp_path / ".dev_cli" / "backend.pid").exists()


def test_backend_only_flag(tmp_path: Path) -> None:
    write_pid(tmp_path, "backend", 2**30)
    write_pid(tmp_path, "frontend", 2**30)

    result = stop_servers(tmp_path, backend_only=True)

    assert result == 0
    # Backend cleaned up, frontend untouched.
    assert not (tmp_path / ".dev_cli" / "backend.pid").exists()
    assert (tmp_path / ".dev_cli" / "frontend.pid").exists()


def test_frontend_only_flag(tmp_path: Path) -> None:
    write_pid(tmp_path, "backend", 2**30)
    write_pid(tmp_path, "frontend", 2**30)

    result = stop_servers(tmp_path, frontend_only=True)

    assert result == 0
    assert (tmp_path / ".dev_cli" / "backend.pid").exists()
    assert not (tmp_path / ".dev_cli" / "frontend.pid").exists()
