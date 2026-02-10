"""CLI entry point — argument parsing and main async loop."""

import argparse
import asyncio
from pathlib import Path

from .output import print_banner
from .preflight import run_checks
from .runner import DevRunner

REPO_ROOT = Path(__file__).resolve().parent.parent


class _Args(argparse.Namespace):
    """Typed namespace for parsed CLI arguments."""

    backend_port: int = 8000
    frontend_port: int = 5173
    skip_checks: bool = False
    backend_only: bool = False
    frontend_only: bool = False


def _parse_args() -> _Args:
    parser = argparse.ArgumentParser(
        description="Start Zondarr dev servers",
    )
    _ = parser.add_argument(
        "--backend-port",
        type=int,
        default=8000,
        help="Backend port (default: 8000)",
    )
    _ = parser.add_argument(
        "--frontend-port",
        type=int,
        default=5173,
        help="Frontend port (default: 5173)",
    )
    _ = parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip pre-flight checks",
    )

    exclusive = parser.add_mutually_exclusive_group()
    _ = exclusive.add_argument(
        "--backend-only",
        action="store_true",
        help="Run only the backend server",
    )
    _ = exclusive.add_argument(
        "--frontend-only",
        action="store_true",
        help="Run only the frontend server",
    )

    return parser.parse_args(namespace=_Args())


async def _main() -> int:
    args = _parse_args()

    if not args.skip_checks:
        if not run_checks(
            repo_root=REPO_ROOT,
            backend_port=args.backend_port,
            frontend_port=args.frontend_port,
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


def run() -> int:
    """Sync entry point for __main__.py."""
    try:
        return asyncio.run(_main())
    except KeyboardInterrupt:
        return 0
