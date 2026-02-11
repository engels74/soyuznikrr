"""CLI entry point — argument parsing and main async loop."""

import argparse
import asyncio
import sys
from pathlib import Path

from .output import print_banner
from .preflight import run_checks
from .runner import DevRunner
from .stop import stop_servers

REPO_ROOT = Path(__file__).resolve().parent.parent

_SUBCOMMANDS = frozenset({"start", "stop"})


class _StartArgs(argparse.Namespace):
    """Typed namespace for ``start`` subcommand arguments."""

    command: str = "start"
    backend_port: int = 8000
    frontend_port: int = 5173
    skip_checks: bool = False
    backend_only: bool = False
    frontend_only: bool = False
    open_browser: bool = False
    no_reload: bool = False


class _StopArgs(argparse.Namespace):
    """Typed namespace for ``stop`` subcommand arguments."""

    command: str = "stop"
    force: bool = False
    backend_only: bool = False
    frontend_only: bool = False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Zondarr dev server manager",
    )
    subs = parser.add_subparsers(dest="command")

    # --- start ---
    start_p = subs.add_parser("start", help="Start dev servers (default)")
    _ = start_p.add_argument(
        "--backend-port",
        type=int,
        default=8000,
        help="Backend port (default: 8000)",
    )
    _ = start_p.add_argument(
        "--frontend-port",
        type=int,
        default=5173,
        help="Frontend port (default: 5173)",
    )
    _ = start_p.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip pre-flight checks",
    )
    _ = start_p.add_argument(
        "--open",
        action="store_true",
        dest="open_browser",
        help="Open browser after servers are ready",
    )
    _ = start_p.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable backend auto-reload on file changes",
    )
    start_excl = start_p.add_mutually_exclusive_group()
    _ = start_excl.add_argument(
        "--backend-only",
        action="store_true",
        help="Run only the backend server",
    )
    _ = start_excl.add_argument(
        "--frontend-only",
        action="store_true",
        help="Run only the frontend server",
    )

    # --- stop ---
    stop_p = subs.add_parser("stop", help="Stop running dev servers")
    _ = stop_p.add_argument(
        "--force",
        action="store_true",
        help="Send SIGKILL immediately instead of SIGTERM",
    )
    stop_excl = stop_p.add_mutually_exclusive_group()
    _ = stop_excl.add_argument(
        "--backend-only",
        action="store_true",
        help="Stop only the backend server",
    )
    _ = stop_excl.add_argument(
        "--frontend-only",
        action="store_true",
        help="Stop only the frontend server",
    )

    return parser


def _parse_args(argv: list[str] | None = None) -> _StartArgs | _StopArgs:
    raw = sys.argv[1:] if argv is None else argv

    # Backward compat: if the first arg is not a known subcommand, insert "start".
    if not raw or raw[0] not in _SUBCOMMANDS:
        raw = ["start", *raw]

    parser = _build_parser()

    if raw[0] == "stop":
        return parser.parse_args(raw, namespace=_StopArgs())
    return parser.parse_args(raw, namespace=_StartArgs())


# ── stop (sync) ─────────────────────────────────────────────────────


def _main_stop(args: _StopArgs) -> int:
    return stop_servers(
        REPO_ROOT,
        force=args.force,
        backend_only=args.backend_only,
        frontend_only=args.frontend_only,
    )


# ── start (async) ───────────────────────────────────────────────────


async def _main_start(args: _StartArgs) -> int:
    if not args.skip_checks:
        if not run_checks(
            repo_root=REPO_ROOT,
            backend_port=args.backend_port,
            frontend_port=args.frontend_port,
            backend_only=args.backend_only,
            frontend_only=args.frontend_only,
        ):
            return 1

    backend_port: int | None = None if args.frontend_only else args.backend_port
    frontend_port: int | None = None if args.backend_only else args.frontend_port
    print_banner(
        backend_port=backend_port,
        frontend_port=frontend_port,
    )

    runner = DevRunner(
        repo_root=REPO_ROOT,
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        backend_only=args.backend_only,
        frontend_only=args.frontend_only,
        open_browser=args.open_browser,
        reload=not args.no_reload,
    )

    try:
        return await runner.run()
    except KeyboardInterrupt:
        return 0


# ── entry point ─────────────────────────────────────────────────────


def run() -> int:
    """Sync entry point for __main__.py."""
    args = _parse_args()

    if isinstance(args, _StopArgs):
        return _main_stop(args)

    try:
        return asyncio.run(_main_start(args))
    except KeyboardInterrupt:
        return 0
