"""Log streaming endpoint for Zondarr.

Provides a Server-Sent Events (SSE) endpoint that streams structlog output
to the browser in real-time, with optional level and source filtering.
"""

import asyncio
from collections.abc import AsyncGenerator, Sequence

import msgspec
from litestar import Controller, get
from litestar.response import ServerSentEvent, ServerSentEventMessage

from zondarr.core.log_buffer import LogEntry, log_buffer

_LEVEL_ORDER: dict[str, int] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}

_encoder = msgspec.json.Encoder()

_BACKFILL_LIMIT = 500
_BACKFILL_BATCH = 50


class LogController(Controller):
    """Log streaming endpoints."""

    path: str = "/api/v1/logs"
    tags: Sequence[str] | None = ["Logs"]

    @get(
        "/stream",
        summary="Stream log entries via SSE",
        description="Server-Sent Events endpoint that streams structlog output in real-time.",
        include_in_schema=False,
    )
    async def stream_logs(
        self,
        level: str | None = None,
        source: str | None = None,
    ) -> ServerSentEvent:
        """Stream log entries as SSE events.

        Args:
            level: Minimum log level filter (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            source: Logger name prefix filter.

        Returns:
            ServerSentEvent response streaming log entries.
        """
        min_level = _LEVEL_ORDER.get(level.upper(), 0) if level else 0

        async def _generate() -> AsyncGenerator[ServerSentEventMessage | str]:
            last_seq = 0

            try:
                # Send initial backfill (limited to most recent entries)
                entries, last_seq = log_buffer.get_entries_since(0)
                backfill = _filter_entries(entries, min_level, source)
                # Only send the tail if there are too many
                if len(backfill) > _BACKFILL_LIMIT:
                    backfill = backfill[-_BACKFILL_LIMIT:]

                for i, entry in enumerate(backfill):
                    yield ServerSentEventMessage(
                        data=_encoder.encode(entry).decode(),
                        event="log",
                    )
                    # Yield to event loop periodically during backfill
                    if (i + 1) % _BACKFILL_BATCH == 0:
                        await asyncio.sleep(0)

                # Stream new entries
                while True:
                    try:
                        _ = await asyncio.wait_for(
                            log_buffer.wait_for_new(after_seq=last_seq, timeout=30.0),
                            timeout=35.0,
                        )
                    except TimeoutError:
                        pass

                    entries, current_seq = log_buffer.get_entries_since(last_seq)
                    if entries:
                        last_seq = current_seq
                        for entry in _filter_entries(entries, min_level, source):
                            yield ServerSentEventMessage(
                                data=_encoder.encode(entry).decode(),
                                event="log",
                            )
                    else:
                        # Heartbeat comment to keep connection alive
                        yield ServerSentEventMessage(comment="heartbeat")

            except asyncio.CancelledError, GeneratorExit:
                return

        return ServerSentEvent(
            _generate(),
            event_type=None,
            retry_duration=3000,
        )


def _filter_entries(
    entries: list[LogEntry],
    min_level: int,
    source: str | None,
) -> list[LogEntry]:
    """Filter entries by level and source prefix."""
    result: list[LogEntry] = []
    for entry in entries:
        entry_level = _LEVEL_ORDER.get(entry.level, 0)
        if entry_level < min_level:
            continue
        if source and not entry.logger_name.startswith(source):
            continue
        result.append(entry)
    return result
