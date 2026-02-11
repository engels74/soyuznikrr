"""Tests for dev_cli.cli argument parsing."""

from dev_cli.cli import _parse_args, _StartArgs, _StopArgs


def test_empty_args_defaults_to_start() -> None:
    args = _parse_args([])
    assert isinstance(args, _StartArgs)
    assert args.command == "start"


def test_backend_only_implicit_start() -> None:
    args = _parse_args(["--backend-only"])
    assert isinstance(args, _StartArgs)
    assert args.backend_only is True
    assert args.frontend_only is False


def test_frontend_only_implicit_start() -> None:
    args = _parse_args(["--frontend-only"])
    assert isinstance(args, _StartArgs)
    assert args.frontend_only is True


def test_explicit_start() -> None:
    args = _parse_args(["start", "--open"])
    assert isinstance(args, _StartArgs)
    assert args.open_browser is True


def test_start_custom_ports() -> None:
    args = _parse_args(["start", "--backend-port", "9000", "--frontend-port", "3000"])
    assert isinstance(args, _StartArgs)
    assert args.backend_port == 9000
    assert args.frontend_port == 3000


def test_stop_subcommand() -> None:
    args = _parse_args(["stop"])
    assert isinstance(args, _StopArgs)
    assert args.command == "stop"
    assert args.force is False
    assert args.backend_only is False
    assert args.frontend_only is False


def test_stop_force() -> None:
    args = _parse_args(["stop", "--force"])
    assert isinstance(args, _StopArgs)
    assert args.force is True


def test_stop_backend_only() -> None:
    args = _parse_args(["stop", "--backend-only"])
    assert isinstance(args, _StopArgs)
    assert args.backend_only is True
    assert args.frontend_only is False


def test_stop_force_backend_only() -> None:
    args = _parse_args(["stop", "--force", "--backend-only"])
    assert isinstance(args, _StopArgs)
    assert args.force is True
    assert args.backend_only is True


def test_skip_checks_implicit_start() -> None:
    args = _parse_args(["--skip-checks"])
    assert isinstance(args, _StartArgs)
    assert args.skip_checks is True


def test_no_reload_implicit_start() -> None:
    args = _parse_args(["--no-reload"])
    assert isinstance(args, _StartArgs)
    assert args.no_reload is True
