"""In-memory ring buffer for capturing structlog output.

Provides:
- LogEntry: msgspec Struct for serialized log records
- LogBuffer: Thread-safe ring buffer with async notification for SSE consumers
- capture_log_processor: structlog processor that captures entries into the buffer

The buffer bridges sync structlog processors with async SSE consumers via
``loop.call_soon_threadsafe()`` for cross-thread notification.
"""

from __future__ import annotations

import asyncio
import threading
from collections import deque

import msgspec
from structlog.types import EventDict, WrappedLogger


class LogEntry(msgspec.Struct, frozen=True):
    """A single captured log record."""

    seq: int
    """Monotonic sequence number for client position tracking."""
    timestamp: str
    """ISO 8601 timestamp."""
    level: str
    """Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""
    logger_name: str
    """Dotted module name of the logger."""
    message: str
    """The event text."""
    fields: dict[str, str]
    """Extra structured key-value pairs, stringified."""


_KNOWN_KEYS = frozenset(
    {
        "event",
        "level",
        "timestamp",
        "_logger",
        "_record",
        "_from_structlog",
    }
)

_encoder = msgspec.json.Encoder()


class LogBuffer:
    """Thread-safe ring buffer with async notification for SSE consumers.

    Stores up to ``maxlen`` LogEntry instances in a deque. An asyncio.Condition
    is used to notify waiting SSE consumers when new entries arrive. The
    ``loop.call_soon_threadsafe()`` bridge allows the sync structlog processor
    to wake async waiters.
    """

    _deque: deque[LogEntry]
    _seq: int
    _lock: threading.Lock
    _loop: asyncio.AbstractEventLoop | None
    _condition: asyncio.Condition | None

    def __init__(self, maxlen: int = 5000) -> None:
        self._deque = deque(maxlen=maxlen)
        self._seq = 0
        self._lock = threading.Lock()
        self._loop = None
        self._condition = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind to an asyncio event loop. Must be called during app startup."""
        self._loop = loop
        self._condition = asyncio.Condition()

    def append(self, entry: LogEntry) -> None:
        """Append a log entry (called from any thread)."""
        with self._lock:
            self._deque.append(entry)

        # Wake async consumers if loop is bound
        if self._loop is not None and self._condition is not None:
            _ = self._loop.call_soon_threadsafe(self._notify)

    def _notify(self) -> None:
        """Schedule async notification (runs on the event loop thread)."""
        if self._condition is not None:
            task = asyncio.ensure_future(self._do_notify())
            task.add_done_callback(lambda _: None)  # prevent GC

    async def _do_notify(self) -> None:
        """Actually notify waiting consumers."""
        if self._condition is not None:
            async with self._condition:
                self._condition.notify_all()

    def next_seq(self) -> int:
        """Allocate and return the next sequence number (thread-safe)."""
        with self._lock:
            self._seq += 1
            return self._seq

    def get_entries_since(self, after_seq: int) -> tuple[list[LogEntry], int]:
        """Return entries with seq > after_seq and the current max seq.

        Args:
            after_seq: Return entries after this sequence number.

        Returns:
            Tuple of (matching entries, current max sequence number).
        """
        with self._lock:
            entries = [e for e in self._deque if e.seq > after_seq]
            current_seq = self._seq
        return entries, current_seq

    async def wait_for_new(self, timeout: float = 30.0) -> bool:
        """Wait for new entries with a timeout.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            True if notified, False if timed out.
        """
        if self._condition is None:
            await asyncio.sleep(timeout)
            return False

        try:
            async with asyncio.timeout(timeout):
                async with self._condition:
                    _ = await self._condition.wait()
            return True
        except TimeoutError:
            return False


# Module-level singleton
log_buffer = LogBuffer()


def capture_log_processor(
    _logger: WrappedLogger,  # pyright: ignore[reportExplicitAny,reportAny]
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Structlog processor that captures entries into the log buffer.

    Inserted before the final renderer in the processor chain. Creates a
    LogEntry from the enriched event dict and appends it to the module-level
    log_buffer singleton.

    Returns the event dict unchanged (pass-through).
    """
    # Extract known fields
    timestamp = str(event_dict.get("timestamp", ""))  # pyright: ignore[reportAny]
    level = str(event_dict.get("level", "INFO")).upper()  # pyright: ignore[reportAny]
    logger_name = str(event_dict.get("_logger", ""))  # pyright: ignore[reportAny]
    message = str(event_dict.get("event", ""))  # pyright: ignore[reportAny]

    # Collect extra fields (stringify values for JSON safety)
    fields: dict[str, str] = {}
    for key, value in event_dict.items():  # pyright: ignore[reportAny]
        if key not in _KNOWN_KEYS:
            fields[key] = str(value)  # pyright: ignore[reportAny]

    seq = log_buffer.next_seq()
    entry = LogEntry(
        seq=seq,
        timestamp=timestamp,
        level=level,
        logger_name=logger_name,
        message=message,
        fields=fields,
    )
    log_buffer.append(entry)

    return event_dict
