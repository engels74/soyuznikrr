"""Tests for dev_cli.pidfile module."""

import os

from dev_cli.pidfile import (
    is_process_alive,
    pid_file_path,
    read_pid,
    remove_pid,
    write_pid,
)


def test_write_read_roundtrip(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    write_pid(root, "backend", 12345)
    assert read_pid(root, "backend") == 12345


def test_read_missing_file(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    assert read_pid(root, "backend") is None


def test_read_malformed_file(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    path = pid_file_path(root, "backend")
    _ = path.write_text("not-a-number")
    assert read_pid(root, "backend") is None


def test_remove_missing_file(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    # Should not raise.
    remove_pid(root, "backend")


def test_remove_existing_file(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    write_pid(root, "frontend", 99999)
    assert pid_file_path(root, "frontend").exists()
    remove_pid(root, "frontend")
    assert not pid_file_path(root, "frontend").exists()


def test_is_process_alive_current_process() -> None:
    assert is_process_alive(os.getpid()) is True


def test_is_process_alive_bogus_pid() -> None:
    # PID 0 is the kernel; PID 2**30 is almost certainly not running.
    assert is_process_alive(2**30) is False


def test_pid_dir_created(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    path = pid_file_path(root, "backend")
    assert path.parent.exists()
    assert path.parent.name == ".dev_cli"
