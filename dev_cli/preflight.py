"""Pre-flight checks for dev environment."""

import os
import re
import secrets
import shutil
import socket
import sqlite3
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
    has_uv = True
    has_bun = True

    # Load .env first so all subsequent steps have env vars available
    _load_dotenv(repo_root)

    # Tool checks
    if not frontend_only and not _check_tool("uv", hint="https://docs.astral.sh/uv/"):
        ok = False
        has_uv = False
    if not backend_only and not _check_tool("bun", hint="https://bun.sh/"):
        ok = False
        has_bun = False

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

    # Auto-install backend dependencies if missing (skip if uv not found)
    if not frontend_only and has_uv:
        if not _install_backend_deps(repo_root / "backend"):
            ok = False

    # Database migrations (skip if uv not found)
    if not frontend_only and has_uv:
        if not _run_migrations(repo_root / "backend"):
            ok = False

    # Auto-install frontend dependencies if missing (skip if bun not found)
    if not backend_only and has_bun:
        if not _install_frontend_deps(repo_root / "frontend"):
            ok = False

    # Advisory: warn if backend is unreachable in frontend-only mode
    if frontend_only:
        _check_backend_reachable(backend_port)

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
    # Fast path: check if DB is already at head without spawning a subprocess
    if _is_db_at_head(backend_dir):
        return True

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


def _is_db_at_head(backend_dir: Path, /) -> bool:
    """Check if the SQLite DB is already at head revision (no subprocess needed).

    Returns True only when we can confidently determine the DB is current.
    Any failure falls through to running Alembic normally.
    """
    try:
        head = _get_head_revision(backend_dir / "migrations" / "versions")
        if head is None:
            return False
        current = _get_current_db_revision(backend_dir)
        if current is None:
            return False
        if current == head:
            print_info(f"Database already at head ({head[:12]})")
            return True
    except Exception:
        pass
    return False


def _get_head_revision(versions_dir: Path, /) -> str | None:
    """Parse migration files to find the head revision (via set subtraction).

    Head = any revision that is not referenced as another file's down_revision.
    Returns None if there are zero or multiple heads.
    """
    revision_re = re.compile(r'^revision\b.*?["\'](.+?)["\']', re.MULTILINE)
    down_re = re.compile(r'^down_revision\b.*?["\'](.+?)["\']', re.MULTILINE)

    revisions: set[str] = set()
    down_revisions: set[str] = set()

    for path in versions_dir.glob("*.py"):
        text = path.read_text()
        rev_match = revision_re.search(text)
        if rev_match is None:
            continue
        revisions.add(rev_match.group(1))
        down_match = down_re.search(text)
        if down_match is not None:
            down_revisions.add(down_match.group(1))

    heads = revisions - down_revisions
    if len(heads) == 1:
        return heads.pop()
    return None


def _get_current_db_revision(backend_dir: Path, /) -> str | None:
    """Read the current revision from the SQLite alembic_version table."""
    db_path = _resolve_sqlite_path(backend_dir)
    if db_path is None or not db_path.is_file():
        return None
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute("SELECT version_num FROM alembic_version LIMIT 1")
        row: tuple[str, ...] | None = cursor.fetchone()  # pyright: ignore[reportAny]  # sqlite3 returns Any
        if row is None:
            return None
        return str(row[0])
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def _resolve_sqlite_path(backend_dir: Path, /) -> Path | None:
    """Resolve the SQLite database path from DATABASE_URL or default.

    Returns None for non-SQLite URLs (e.g. PostgreSQL), causing the fast-path
    to fall through to running Alembic normally.
    """
    url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./zondarr.db")
    if not url.startswith("sqlite"):
        return None
    # Strip the scheme: sqlite:/// or sqlite+aiosqlite:///
    _, _, path_part = url.partition("///")
    if not path_part:
        return None
    db_path = Path(path_part)
    if not db_path.is_absolute():
        db_path = backend_dir / db_path
    return db_path


def _install_backend_deps(backend_dir: Path, /) -> bool:
    """Run ``uv sync`` if the backend .venv is missing."""
    venv = backend_dir / ".venv"
    if venv.exists():
        return True

    print_info("Backend .venv not found — running uv sync --extra dev...")
    result = subprocess.run(
        ["uv", "sync", "--extra", "dev"],
        cwd=backend_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print_error(f"uv sync failed:\n{result.stderr.strip()}")
        return False
    print_info("Backend dependencies installed")
    return True


def _install_frontend_deps(frontend_dir: Path, /) -> bool:
    """Run ``bun install`` if node_modules is missing."""
    node_modules = frontend_dir / "node_modules"
    if node_modules.exists():
        return True

    print_info("node_modules not found — running bun install...")
    result = subprocess.run(
        ["bun", "install"],
        cwd=frontend_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print_error(f"bun install failed:\n{result.stderr.strip()}")
        return False
    print_info("Frontend dependencies installed")
    return True


def _check_backend_reachable(port: int, /) -> None:
    """Advisory check: warn if backend port is unreachable in frontend-only mode."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", port)) != 0:
            print_warn(
                f"Backend is not running on port {port} — API calls from the frontend will fail"
            )


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
        value = value.strip()
        if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
            # Quoted value — strip matching quotes, keep content as-is
            value = value[1:-1]
        else:
            # Unquoted value — strip inline comments
            comment_idx = value.find(" #")
            if comment_idx != -1:
                value = value[:comment_idx].rstrip()
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
