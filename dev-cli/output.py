"""Color-coded terminal output helpers."""

import sys

_IS_TTY = sys.stdout.isatty()

# ANSI color codes — disabled when not a TTY
CYAN = "\033[36m" if _IS_TTY else ""
MAGENTA = "\033[35m" if _IS_TTY else ""
GREEN = "\033[32m" if _IS_TTY else ""
YELLOW = "\033[33m" if _IS_TTY else ""
RED = "\033[31m" if _IS_TTY else ""
BOLD = "\033[1m" if _IS_TTY else ""
DIM = "\033[2m" if _IS_TTY else ""
RESET = "\033[0m" if _IS_TTY else ""


def print_info(msg: str, /) -> None:
    print(f"{CYAN}[info]{RESET} {msg}")


def print_warn(msg: str, /) -> None:
    print(f"{YELLOW}[warn]{RESET} {msg}")


def print_error(msg: str, /) -> None:
    print(f"{RED}[error]{RESET} {msg}", file=sys.stderr)


def print_banner(
    *,
    backend_port: int,
    frontend_port: int | None,
) -> None:
    """Print startup banner with server URLs."""
    print()
    print(f"{BOLD}{GREEN}  Zondarr Dev Servers{RESET}")
    print(f"{DIM}  {'─' * 40}{RESET}")
    print(f"  Backend:   {CYAN}http://localhost:{backend_port}{RESET}")
    if frontend_port is not None:
        print(f"  Frontend:  {MAGENTA}http://localhost:{frontend_port}{RESET}")
    print(f"  API Docs:  {CYAN}http://localhost:{backend_port}/docs{RESET}")
    print(f"{DIM}  {'─' * 40}{RESET}")
    print(f"  Press {BOLD}Ctrl+C{RESET} to stop")
    print()
