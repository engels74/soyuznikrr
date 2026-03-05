"""Tests for dev_cli.runner command construction."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dev_cli.runner import DevRunner


def _build_runner(*, repo_root: Path, reload: bool) -> DevRunner:
    runner = DevRunner(
        repo_root=repo_root,
        backend_port=8000,
        frontend_port=5173,
        backend_only=False,
        frontend_only=False,
        reload=reload,
    )
    runner._build_servers()
    return runner


class DevRunnerCommandTests(unittest.TestCase):
    def test_backend_reload_ignores_bootstrap_token_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            runner = _build_runner(repo_root=repo_root, reload=True)

            backend = next(
                server for server in runner.servers if server.name == "backend"
            )
            frontend = next(
                server for server in runner.servers if server.name == "frontend"
            )
            token_file = str(repo_root / "backend" / "data" / ".bootstrap_token")

            self.assertEqual(backend.env["BOOTSTRAP_TOKEN_FILE"], token_file)
            self.assertNotIn("BOOTSTRAP_TOKEN_FILE", frontend.env)
            self.assertIn("--reload", backend.cmd)

            ignore_idx = backend.cmd.index("--reload-ignore-paths")
            self.assertEqual(backend.cmd[ignore_idx + 1], token_file)

    def test_frontend_strips_inherited_bootstrap_token_file(self) -> None:
        with patch.dict(
            os.environ,
            {"BOOTSTRAP_TOKEN_FILE": "/tmp/inherited-bootstrap-token"},
            clear=False,
        ):
            with tempfile.TemporaryDirectory() as tmp_dir:
                repo_root = Path(tmp_dir)
                runner = _build_runner(repo_root=repo_root, reload=True)

                backend = next(
                    server for server in runner.servers if server.name == "backend"
                )
                frontend = next(
                    server for server in runner.servers if server.name == "frontend"
                )
                token_file = str(repo_root / "backend" / "data" / ".bootstrap_token")

                self.assertEqual(backend.env["BOOTSTRAP_TOKEN_FILE"], token_file)
                self.assertNotIn("BOOTSTRAP_TOKEN_FILE", frontend.env)

    def test_backend_no_reload_omits_reload_ignore_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            runner = _build_runner(repo_root=repo_root, reload=False)

            backend = next(
                server for server in runner.servers if server.name == "backend"
            )

            self.assertNotIn("--reload", backend.cmd)
            self.assertNotIn("--reload-ignore-paths", backend.cmd)
