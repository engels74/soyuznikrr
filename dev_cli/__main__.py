#!/usr/bin/env python3
"""Zondarr development server launcher.

Usage:
    uv run dev_cli                          # Start both servers
    uv run dev_cli --backend-only           # Backend only
    uv run dev_cli --frontend-only          # Frontend only
    uv run dev_cli --backend-port 9000      # Custom backend port
    uv run dev_cli --skip-checks            # Skip pre-flight checks

    uv run dev_cli stop                     # Stop all running servers
    uv run dev_cli stop --backend-only      # Stop backend only
    uv run dev_cli stop --force             # Send SIGKILL immediately
"""

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so `dev_cli` is importable as a package.
# Required when invoked as `uv run dev_cli` or `python dev_cli` (directory mode).
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from dev_cli.cli import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())
