"""Pre-flight checks for dev environment."""

import os
import secrets
import shutil
import socket
import subprocess
from pathlib import Path

from .output import print_error, print_info, print_warn


def run_checks(
    *,
    repo_root: Path,
    backend_port: int,
    frontend_port: int,
    backend_only: bool,
    frontend_only: bool,
) -> bool:
    """Run all pre-flight checks. Returns True if all critical checks pass."""
    ok = True

    # Load .env first so all subsequent steps have env vars available
    _load_dotenv(repo_root)

    # Tool checks
    if not frontend_only and not _check_tool("uv", hint="https://docs.astral.sh/uv/"):
        ok = False
    if not backend_only and not _check_tool("bun", hint="https://bun.sh/"):
        ok = False

    # Port availability checks
    if not frontend_only and not _check_port(backend_port, "backend"):
        ok = False
    if not backend_only and not _check_port(frontend_port, "frontend"):
        ok = False

    # Directory checks
    if not frontend_only and not _check_dir(repo_root / "backend"):
        ok = False
    if not backend_only and not _check_dir(repo_root / "frontend"):
        ok = False

    # Database migrations
    if not frontend_only:
        if not _run_migrations(repo_root / "backend"):
            ok = False

    # Advisory checks (non-fatal)
    if not frontend_only:
        venv = repo_root / "backend" / ".venv"
        if not venv.exists():
            print_warn(f"{venv} not found — uv will auto-sync on first run")

    if not backend_only:
        node_modules = repo_root / "frontend" / "node_modules"
        if not node_modules.exists():
            print_warn(f"{node_modules} not found — bun will install on first run")

    # SECRET_KEY
    _ensure_secret_key()

    return ok


def _check_tool(name: str, /, *, hint: str) -> bool:
    if shutil.which(name) is None:
        print_error(f"'{name}' not found on PATH. Install: {hint}")
        return False
    return True


def _check_dir(path: Path, /) -> bool:
    if not path.is_dir():
        print_error(f"Directory not found: {path}")
        return False
    return True


def _run_migrations(backend_dir: Path, /) -> bool:
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print_error(f"Alembic migrations failed:\n{result.stderr.strip()}")
        return False
    print_info("Database migrations up to date")
    return True


def _ensure_secret_key() -> None:
    if os.environ.get("SECRET_KEY"):
        return
    generated = secrets.token_hex(32)
    os.environ["SECRET_KEY"] = generated
    print_info(f"SECRET_KEY not set — generated ephemeral key: {generated[:8]}...")


def _load_dotenv(repo_root: Path, /) -> None:
    """Load variables from .env into os.environ (setdefault — no overrides)."""
    env_file = repo_root / ".env"
    if not env_file.is_file():
        print_warn(".env file not found — using environment variables only")
        return

    count = 0
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip().removeprefix("export ")
        if not key:
            continue
        value = value.strip().strip("\"'")
        _ = os.environ.setdefault(key, value)
        count += 1

    print_info(f"Loaded {count} variables from .env")


def _check_port(port: int, name: str, /) -> bool:
    """Return True if the port is available, False if in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", port)) != 0:
            return True

    # Port is in use — try to find the PID
    pid_info = ""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.stdout.strip():
            pids = result.stdout.strip()
            pid_info = f" (pid={pids}). Kill it with: kill {pids}"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    print_error(f"Port {port} ({name}) is already in use{pid_info}")
    return False
