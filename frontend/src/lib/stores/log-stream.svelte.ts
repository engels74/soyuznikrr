/**
 * SSE-based log stream store.
 *
 * Connects to the backend's `/api/v1/logs/stream` SSE endpoint and maintains
 * a client-side ring buffer of log entries for the log viewer UI.
 *
 * @module $lib/stores/log-stream
 */

// =============================================================================
// Types
// =============================================================================

export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

export interface LogEntry {
	seq: number;
	timestamp: string;
	level: LogLevel;
	logger_name: string;
	message: string;
	fields: Record<string, string>;
}

export const LEVEL_ORDER: Record<LogLevel, number> = {
	DEBUG: 10,
	INFO: 20,
	WARNING: 30,
	ERROR: 40,
	CRITICAL: 50
};

// =============================================================================
// State
// =============================================================================

const MAX_ENTRIES = 2000;

let _entries = $state<LogEntry[]>([]);
let _connected = $state(false);
let _error = $state<string | null>(null);

let _eventSource: EventSource | null = null;

// =============================================================================
// API
// =============================================================================

/**
 * Connect to the SSE log stream.
 */
export function connect(): void {
	if (_eventSource) return;

	// Use same-origin by default (SvelteKit proxy or direct)
	const url = '/api/v1/logs/stream';

	const es = new EventSource(url, { withCredentials: true });
	_eventSource = es;

	es.onopen = () => {
		_connected = true;
		_error = null;
	};

	es.addEventListener('log', (event: MessageEvent<string>) => {
		try {
			const entry = JSON.parse(event.data) as LogEntry;
			if (_entries.length >= MAX_ENTRIES) {
				// Drop oldest entries to stay within the cap
				_entries = [..._entries.slice(-MAX_ENTRIES + 100), entry];
			} else {
				_entries.push(entry);
			}
		} catch {
			// Ignore malformed events
		}
	});

	es.onerror = () => {
		_connected = false;
		_error = 'Connection lost. Reconnecting...';
	};
}

/**
 * Disconnect from the SSE log stream.
 */
export function disconnect(): void {
	if (_eventSource) {
		_eventSource.close();
		_eventSource = null;
	}
	_connected = false;
	_error = null;
}

/**
 * Clear all buffered log entries.
 */
export function clearEntries(): void {
	_entries = [];
}

// =============================================================================
// Exports (reactive getters)
// =============================================================================

export function getEntries(): LogEntry[] {
	return _entries;
}

export function getConnected(): boolean {
	return _connected;
}

export function getError(): string | null {
	return _error;
}
