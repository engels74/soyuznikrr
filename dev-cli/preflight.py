"""Pre-flight checks for dev environment."""

import os
import secrets
import shutil
from pathlib import Path

from output import print_error, print_info, print_warn


def run_checks(
    *,
    repo_root: Path,
    backend_only: bool,
    frontend_only: bool,
) -> bool:
    """Run all pre-flight checks. Returns True if all critical checks pass."""
    ok = True

    # Tool checks
    if not frontend_only and not _check_tool("uv", hint="https://docs.astral.sh/uv/"):
        ok = False
    if not backend_only and not _check_tool("bun", hint="https://bun.sh/"):
        ok = False

    # Directory checks
    if not frontend_only and not _check_dir(repo_root / "backend"):
        ok = False
    if not backend_only and not _check_dir(repo_root / "frontend"):
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


def _ensure_secret_key() -> None:
    if os.environ.get("SECRET_KEY"):
        return
    generated = secrets.token_hex(32)
    os.environ["SECRET_KEY"] = generated
    print_info(f"SECRET_KEY not set — generated ephemeral key: {generated[:8]}...")
