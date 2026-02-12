"""Tests for dev_cli.cli argument parsing."""

from dev_cli.cli import parse_args, StartArgs, StopArgs


def test_empty_args_defaults_to_start() -> None:
    args = parse_args([])
    assert isinstance(args, StartArgs)
    assert args.command == "start"


def test_backend_only_implicit_start() -> None:
    args = parse_args(["--backend-only"])
    assert isinstance(args, StartArgs)
    assert args.backend_only is True
    assert args.frontend_only is False


def test_frontend_only_implicit_start() -> None:
    args = parse_args(["--frontend-only"])
    assert isinstance(args, StartArgs)
    assert args.frontend_only is True


def test_explicit_start() -> None:
    args = parse_args(["start", "--open"])
    assert isinstance(args, StartArgs)
    assert args.open_browser is True


def test_start_custom_ports() -> None:
    args = parse_args(["start", "--backend-port", "9000", "--frontend-port", "3000"])
    assert isinstance(args, StartArgs)
    assert args.backend_port == 9000
    assert args.frontend_port == 3000


def test_stop_subcommand() -> None:
    args = parse_args(["stop"])
    assert isinstance(args, StopArgs)
    assert args.command == "stop"
    assert args.force is False
    assert args.backend_only is False
    assert args.frontend_only is False


def test_stop_force() -> None:
    args = parse_args(["stop", "--force"])
    assert isinstance(args, StopArgs)
    assert args.force is True


def test_stop_backend_only() -> None:
    args = parse_args(["stop", "--backend-only"])
    assert isinstance(args, StopArgs)
    assert args.backend_only is True
    assert args.frontend_only is False


def test_stop_force_backend_only() -> None:
    args = parse_args(["stop", "--force", "--backend-only"])
    assert isinstance(args, StopArgs)
    assert args.force is True
    assert args.backend_only is True


def test_skip_checks_implicit_start() -> None:
    args = parse_args(["--skip-checks"])
    assert isinstance(args, StartArgs)
    assert args.skip_checks is True


def test_no_reload_implicit_start() -> None:
    args = parse_args(["--no-reload"])
    assert isinstance(args, StartArgs)
    assert args.no_reload is True
