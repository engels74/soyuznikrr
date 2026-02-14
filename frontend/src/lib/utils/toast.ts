import { toast } from 'svelte-sonner';
import type { ErrorResponse } from '$lib/api/client';

// Patterns that indicate unsafe/internal error details
const UNSAFE_PATTERNS = [
	/at\s+\S+\s+\(/i, // Stack trace lines: "at functionName ("
	/^\s+at\s+/m, // Indented stack trace lines
	/\.ts:\d+:\d+/i, // TypeScript file references: file.ts:10:5
	/\.js:\d+:\d+/i, // JavaScript file references: file.js:10:5
	/\.py:\d+/i, // Python file references: file.py:10
	/\/src\//i, // Source paths
	/\/node_modules\//i, // Node modules paths
	/\/backend\//i, // Backend paths
	/Traceback\s*\(/i, // Python tracebacks
	/File\s+"[^"]+",\s+line\s+\d+/i, // Python file references
	/Error:\s+\w+Error:/i, // Nested error types
	/INTERNAL_ERROR/i, // Internal error codes
	/DATABASE_ERROR/i, // Database error codes
	/SQL/i // SQL-related errors
];

// Generic fallback message for unsafe errors
const GENERIC_ERROR_MESSAGE = 'An unexpected error occurred';

/**
 * Check if an error message contains unsafe internal details.
 *
 * @param message - The error message to check
 * @returns true if the message contains unsafe patterns
 */
function containsUnsafeDetails(message: string): boolean {
	return UNSAFE_PATTERNS.some((pattern) => pattern.test(message));
}

/**
 * Sanitize an error message by removing or replacing unsafe content.
 *
 * @param message - The error message to sanitize
 * @returns A safe error message suitable for display to users
 */
export function sanitizeErrorMessage(message: string): string {
	if (!message || typeof message !== 'string') {
		return GENERIC_ERROR_MESSAGE;
	}

	// If the message contains unsafe patterns, return generic message
	if (containsUnsafeDetails(message)) {
		return GENERIC_ERROR_MESSAGE;
	}

	// Truncate very long messages (likely contain debug info)
	if (message.length > 200) {
		return GENERIC_ERROR_MESSAGE;
	}

	return message;
}

/**
 * Display a success toast notification.
 */
export function showSuccess(message: string, description?: string): void {
	toast.success(message, { description });
}

/**
 * Display an error toast notification.
 */
export function showError(message: string, description?: string): void {
	toast.error(sanitizeErrorMessage(message), {
		description: description ? sanitizeErrorMessage(description) : undefined
	});
}

/**
 * Display an error toast from an API error response.
 * Filters out stack traces and internal details for security.
 */
export function showApiError(error: unknown): void {
	if (error && typeof error === 'object' && 'detail' in error) {
		const apiError = error as ErrorResponse;
		const safeMessage = sanitizeErrorMessage(apiError.detail);

		// Only show error code if it's a user-facing code (not internal)
		const showErrorCode =
			apiError.error_code &&
			!containsUnsafeDetails(apiError.error_code) &&
			!apiError.error_code.includes('INTERNAL');

		toast.error(safeMessage, {
			description: showErrorCode ? `Error code: ${apiError.error_code}` : undefined
		});
	} else if (error instanceof Error) {
		// Don't expose raw Error messages - they often contain internal details
		toast.error(GENERIC_ERROR_MESSAGE);
	} else {
		toast.error(GENERIC_ERROR_MESSAGE);
	}
}

/**
 * Display a network error toast with retry guidance.
 */
export function showNetworkError(): void {
	toast.error('Network error', {
		description: 'Please check your connection and try again.'
	});
}

/**
 * Display an info toast notification.
 */
export function showInfo(message: string, description?: string): void {
	toast.info(message, { description });
}

/**
 * Display a warning toast notification.
 */
export function showWarning(message: string, description?: string): void {
	toast.warning(message, { description });
}
