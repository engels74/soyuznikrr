"""Subprocess orchestration for dev servers."""

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import final

from .output import BOLD, CYAN, DIM, MAGENTA, RESET, print_error, print_info


@final
class ServerProcess:
    """Wraps a single child process with colored output streaming."""

    def __init__(
        self,
        *,
        name: str,
        cmd: list[str],
        cwd: Path,
        env: dict[str, str],
        color: str,
        ready_pattern: str,
    ) -> None:
        self.name = name
        self.cmd = cmd
        self.cwd = cwd
        self.env = env
        self.color = color
        self.ready_pattern = ready_pattern
        self.process: asyncio.subprocess.Process | None = None
        self.ready = asyncio.Event()

    async def start(self) -> None:
        self.process = await asyncio.create_subprocess_exec(
            *self.cmd,
            cwd=self.cwd,
            env=self.env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        print_info(f"Started {self.name} (pid={self.process.pid})")

    async def stream_output(
        self,
        stream: asyncio.StreamReader,
        *,
        shutdown_event: asyncio.Event,
    ) -> None:
        prefix = f"{self.color}{BOLD}{self.name:<8}{RESET}{DIM}|{RESET} "
        while not shutdown_event.is_set():
            try:
                line = await asyncio.wait_for(stream.readline(), timeout=0.5)
            except TimeoutError:
                continue
            if not line:
                break
            decoded = line.decode(errors="replace").rstrip()
            print(f"{prefix}{decoded}")
            if not self.ready.is_set() and self.ready_pattern in decoded:
                self.ready.set()

    async def stop(self) -> None:
        if self.process is None or self.process.returncode is not None:
            return
        print_info(f"Stopping {self.name} (pid={self.process.pid})...")
        self.process.terminate()
        try:
            _ = await asyncio.wait_for(self.process.wait(), timeout=5.0)
        except TimeoutError:
            print_error(f"{self.name} did not exit in 5s — sending SIGKILL")
            self.process.kill()
            _ = await self.process.wait()


@final
class DevRunner:
    """Orchestrates multiple ServerProcess instances."""

    def __init__(
        self,
        *,
        repo_root: Path,
        backend_port: int,
        frontend_port: int,
        backend_only: bool,
        frontend_only: bool,
    ) -> None:
        self.repo_root = repo_root
        self.backend_port = backend_port
        self.frontend_port = frontend_port
        self.backend_only = backend_only
        self.frontend_only = frontend_only
        self.shutdown_event = asyncio.Event()
        self.servers: list[ServerProcess] = []

    def _build_servers(self) -> None:
        parent_env = dict(os.environ)

        if not self.frontend_only:
            backend_env = {
                **parent_env,
                "DEBUG": "true",
                "CORS_ORIGINS": f"http://localhost:{self.frontend_port}",
            }
            self.servers.append(
                ServerProcess(
                    name="backend",
                    cmd=[
                        "uv",
                        "run",
                        "granian",
                        "zondarr.app:app",
                        "--interface",
                        "asgi",
                        "--host",
                        "0.0.0.0",
                        "--port",
                        str(self.backend_port),
                    ],
                    cwd=self.repo_root / "backend",
                    env=backend_env,
                    color=CYAN,
                    ready_pattern="Listening at:",
                )
            )

        if not self.backend_only:
            frontend_env = {
                **parent_env,
                "VITE_API_URL": f"http://localhost:{self.backend_port}",
            }
            self.servers.append(
                ServerProcess(
                    name="frontend",
                    cmd=[
                        "bun",
                        "run",
                        "dev",
                        "--",
                        "--port",
                        str(self.frontend_port),
                    ],
                    cwd=self.repo_root / "frontend",
                    env=frontend_env,
                    color=MAGENTA,
                    ready_pattern="Local:",
                )
            )

    _STARTUP_TIMEOUT: float = 30.0

    async def run(self) -> int:
        self._build_servers()

        if not self.servers:
            print_error("No servers to run (check --backend-only / --frontend-only)")
            return 1

        # Install signal handlers
        loop = asyncio.get_running_loop()
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self.shutdown_event.set)

        tasks: list[asyncio.Task[None]] = []

        # Separate backend and frontend servers for sequenced startup
        backend = next((s for s in self.servers if s.name == "backend"), None)
        frontend = next((s for s in self.servers if s.name == "frontend"), None)

        # Start backend first (if present) and wait for it to be ready
        if backend is not None:
            await backend.start()
            assert backend.process is not None
            assert backend.process.stdout is not None
            assert backend.process.stderr is not None
            tasks.extend(self._stream_tasks(backend))

            # Wait for backend readiness before starting frontend
            if frontend is not None:
                ready = await self._await_ready(backend)
                if not ready:
                    await backend.stop()
                    return 1

        # Start frontend (if present)
        if frontend is not None:
            await frontend.start()
            assert frontend.process is not None
            assert frontend.process.stdout is not None
            assert frontend.process.stderr is not None
            tasks.extend(self._stream_tasks(frontend))

        # Watch for unexpected exits and startup timeout
        tasks.append(asyncio.create_task(self._watch_exits()))
        tasks.append(asyncio.create_task(self._check_startup()))

        # Wait for shutdown signal or all streams to end
        _ = await asyncio.gather(*tasks, return_exceptions=True)

        # Stop any remaining servers
        for server in self.servers:
            await server.stop()

        return 0

    def _stream_tasks(self, server: ServerProcess) -> list[asyncio.Task[None]]:
        """Create stdout + stderr stream tasks for a server."""
        assert server.process is not None
        assert server.process.stdout is not None
        assert server.process.stderr is not None
        return [
            asyncio.create_task(
                server.stream_output(
                    server.process.stdout,
                    shutdown_event=self.shutdown_event,
                )
            ),
            asyncio.create_task(
                server.stream_output(
                    server.process.stderr,
                    shutdown_event=self.shutdown_event,
                )
            ),
        ]

    async def _await_ready(self, server: ServerProcess) -> bool:
        """Wait for a server's ready event with timeout. Returns True if ready."""
        try:
            _ = await asyncio.wait_for(
                server.ready.wait(), timeout=self._STARTUP_TIMEOUT
            )
            return True
        except TimeoutError:
            print_error(
                f"{server.name} did not start within {self._STARTUP_TIMEOUT:.0f}s"
            )
            return False

    async def _check_startup(self) -> None:
        """Wait for all servers to become ready, trigger shutdown on timeout."""
        for server in self.servers:
            if server.ready.is_set():
                continue
            try:
                _ = await asyncio.wait_for(
                    server.ready.wait(), timeout=self._STARTUP_TIMEOUT
                )
            except TimeoutError:
                if not self.shutdown_event.is_set():
                    msg = (
                        f"{server.name} did not become ready within"
                        f" {self._STARTUP_TIMEOUT:.0f}s — shutting down"
                    )
                    print_error(msg)
                    self.shutdown_event.set()
                return

    async def _watch_exits(self) -> None:
        """Monitor server processes and cascade shutdown on unexpected exit."""
        while not self.shutdown_event.is_set():
            for server in self.servers:
                if (
                    server.process is not None
                    and server.process.returncode is not None
                    and server.process.returncode != 0
                ):
                    print_error(
                        f"{server.name} exited with code {server.process.returncode}"
                    )
                    self.shutdown_event.set()
                    return
            try:
                _ = await asyncio.wait_for(self.shutdown_event.wait(), timeout=0.5)
            except TimeoutError:
                continue
