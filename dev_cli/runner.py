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
            backend_env = {**parent_env, "DEBUG": "true"}
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

        # Start all servers
        for server in self.servers:
            await server.start()

        # Create stream tasks (stdout + stderr per server)
        tasks: list[asyncio.Task[None]] = []
        for server in self.servers:
            assert server.process is not None
            assert server.process.stdout is not None
            assert server.process.stderr is not None
            tasks.append(
                asyncio.create_task(
                    server.stream_output(
                        server.process.stdout,
                        shutdown_event=self.shutdown_event,
                    )
                )
            )
            tasks.append(
                asyncio.create_task(
                    server.stream_output(
                        server.process.stderr,
                        shutdown_event=self.shutdown_event,
                    )
                )
            )

        # Also watch for unexpected exits
        tasks.append(asyncio.create_task(self._watch_exits()))

        # Wait for shutdown signal or all streams to end
        _ = await asyncio.gather(*tasks, return_exceptions=True)

        # Stop any remaining servers
        for server in self.servers:
            await server.stop()

        return 0

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
