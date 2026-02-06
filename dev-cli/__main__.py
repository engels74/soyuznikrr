#!/usr/bin/env python3
"""Zondarr development server launcher.

Usage:
    uv run dev-cli                          # Start both servers
    uv run dev-cli --backend-only           # Backend only
    uv run dev-cli --frontend-only          # Frontend only
    uv run dev-cli --backend-port 9000      # Custom backend port
    uv run dev-cli --skip-checks            # Skip pre-flight checks
"""

import argparse
import asyncio
import sys
from pathlib import Path

from output import print_banner
from preflight import run_checks
from runner import DevRunner

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start Zondarr dev servers",
    )
    parser.add_argument(
        "--backend-port",
        type=int,
        default=8000,
        help="Backend port (default: 8000)",
    )
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=5173,
        help="Frontend port (default: 5173)",
    )
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip pre-flight checks",
    )

    exclusive = parser.add_mutually_exclusive_group()
    exclusive.add_argument(
        "--backend-only",
        action="store_true",
        help="Run only the backend server",
    )
    exclusive.add_argument(
        "--frontend-only",
        action="store_true",
        help="Run only the frontend server",
    )

    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    if not args.skip_checks:
        if not run_checks(
            repo_root=REPO_ROOT,
            backend_only=args.backend_only,
            frontend_only=args.frontend_only,
        ):
            return 1

    frontend_port: int | None = None if args.backend_only else args.frontend_port
    print_banner(
        backend_port=args.backend_port,
        frontend_port=frontend_port,
    )

    runner = DevRunner(
        repo_root=REPO_ROOT,
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        backend_only=args.backend_only,
        frontend_only=args.frontend_only,
    )

    try:
        return await runner.run()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    try:
        code = asyncio.run(main())
    except KeyboardInterrupt:
        code = 0
    sys.exit(code)
