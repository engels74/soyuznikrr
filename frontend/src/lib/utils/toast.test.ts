/**
 * Property-based tests for toast utilities.
 *
 * **Property 9: API Error Toast Display**
 * *For any* API error response, the frontend error handling SHALL extract
 * the error message and display it via toast notification.
 *
 * **Property 12: Error Message Safety**
 * *For any* error displayed to users, the message SHALL NOT contain stack traces,
 * file paths, or internal implementation details.
 */

import * as fc from 'fast-check';
import { toast } from 'svelte-sonner';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
	sanitizeErrorMessage,
	showApiError,
	showError,
	showInfo,
	showNetworkError,
	showSuccess,
	showWarning
} from './toast';

// Mock svelte-sonner toast
vi.mock('svelte-sonner', () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
		info: vi.fn(),
		warning: vi.fn()
	}
}));

// Generator for safe error messages (no internal details)
const safeMessageArb = fc.string({ minLength: 1, maxLength: 100 }).filter((s) => {
	// Filter out strings that would be considered unsafe
	const unsafePatterns = [
		/at\s+\S+\s+\(/i,
		/^\s+at\s+/m,
		/\.ts:\d+:\d+/i,
		/\.js:\d+:\d+/i,
		/\.py:\d+/i,
		/\/src\//i,
		/\/node_modules\//i,
		/\/backend\//i,
		/Traceback\s*\(/i,
		/File\s+"[^"]+",\s+line\s+\d+/i,
		/Error:\s+\w+Error:/i,
		/INTERNAL_ERROR/i,
		/DATABASE_ERROR/i,
		/SQL/i
	];
	return !unsafePatterns.some((p) => p.test(s));
});

// Generator for unsafe error messages (containing internal details)
const unsafeMessageArb = fc.oneof(
	fc.constant('Error at functionName (file.ts:10:5)'),
	fc.constant('    at Object.handler (/src/api/handler.ts:42:15)'),
	fc.constant('TypeError: Cannot read property of undefined\n    at processRequest'),
	fc.constant('File "/backend/src/main.py", line 42, in handler'),
	fc.constant('Traceback (most recent call last):'),
	fc.constant('INTERNAL_ERROR: Database connection failed'),
	fc.constant('DATABASE_ERROR: SQL syntax error near SELECT'),
	fc.constant('/node_modules/express/lib/router.js:123:45'),
	fc.constant('Error: TypeError: at Object.handler')
);

describe('Toast Utilities', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		vi.clearAllMocks();
	});

	/**
	 * Property 12: Error Message Safety
	 *
	 * For any error message containing internal details (stack traces, file paths,
	 * internal error codes), sanitizeErrorMessage SHALL return a generic message.
	 */
	describe('Property 12: Error Message Safety', () => {
		it('sanitizes messages containing stack traces', () => {
			fc.assert(
				fc.property(unsafeMessageArb, (unsafeMessage) => {
					const result = sanitizeErrorMessage(unsafeMessage);
					expect(result).toBe('An unexpected error occurred');
				}),
				{ numRuns: 100 }
			);
		});

		it('preserves safe user-facing messages', () => {
			fc.assert(
				fc.property(safeMessageArb, (safeMessage) => {
					const result = sanitizeErrorMessage(safeMessage);
					expect(result).toBe(safeMessage);
				}),
				{ numRuns: 100 }
			);
		});

		it('returns generic message for very long messages', () => {
			const longMessage = 'a'.repeat(250);
			expect(sanitizeErrorMessage(longMessage)).toBe('An unexpected error occurred');
		});

		it('returns generic message for empty or invalid input', () => {
			expect(sanitizeErrorMessage('')).toBe('An unexpected error occurred');
			expect(sanitizeErrorMessage(null as unknown as string)).toBe('An unexpected error occurred');
			expect(sanitizeErrorMessage(undefined as unknown as string)).toBe(
				'An unexpected error occurred'
			);
		});
	});

	/**
	 * Property 9: API Error Toast Display
	 *
	 * For any API error response with a detail field, showApiError SHALL
	 * extract the error message, sanitize it, and display it via toast.error.
	 */
	describe('Property 9: API Error Toast Display', () => {
		it('extracts and sanitizes detail from API error objects', () => {
			fc.assert(
				fc.property(
					fc.record({
						detail: safeMessageArb,
						error_code: fc.option(
							fc
								.string({ minLength: 1, maxLength: 20 })
								.filter((s) => !s.includes('INTERNAL') && !/SQL/i.test(s) && !/DATABASE/i.test(s)),
							{ nil: undefined }
						)
					}),
					(apiError) => {
						vi.clearAllMocks();

						showApiError(apiError);

						expect(toast.error).toHaveBeenCalledTimes(1);
						// The message should be the same since it's safe
						expect(toast.error).toHaveBeenCalledWith(
							apiError.detail,
							expect.objectContaining({
								description: apiError.error_code ? `Error code: ${apiError.error_code}` : undefined
							})
						);
					}
				),
				{ numRuns: 100 }
			);
		});

		it('sanitizes unsafe API error messages', () => {
			fc.assert(
				fc.property(
					fc.record({
						detail: unsafeMessageArb,
						error_code: fc.option(fc.string({ minLength: 1 }), {
							nil: undefined
						})
					}),
					(apiError) => {
						vi.clearAllMocks();

						showApiError(apiError);

						expect(toast.error).toHaveBeenCalledTimes(1);
						// Unsafe messages should be replaced with generic message
						expect(toast.error).toHaveBeenCalledWith(
							'An unexpected error occurred',
							expect.anything()
						);
					}
				),
				{ numRuns: 100 }
			);
		});

		it('handles Error instances with generic message (no internal details exposed)', () => {
			fc.assert(
				fc.property(fc.string({ minLength: 1 }), (errorMessage) => {
					vi.clearAllMocks();

					const error = new Error(errorMessage);
					showApiError(error);

					expect(toast.error).toHaveBeenCalledTimes(1);
					// Error instances should always show generic message for safety
					expect(toast.error).toHaveBeenCalledWith('An unexpected error occurred');
				}),
				{ numRuns: 100 }
			);
		});

		it('handles unknown error types with generic message', () => {
			fc.assert(
				fc.property(
					fc.oneof(
						fc.constant(null),
						fc.constant(undefined),
						fc.integer(),
						fc.string(),
						fc.boolean(),
						fc.array(fc.integer())
					),
					(unknownError) => {
						vi.clearAllMocks();

						showApiError(unknownError);

						expect(toast.error).toHaveBeenCalledTimes(1);
						expect(toast.error).toHaveBeenCalledWith('An unexpected error occurred');
					}
				),
				{ numRuns: 100 }
			);
		});
	});

	describe('showNetworkError', () => {
		it('displays network error with retry guidance', () => {
			showNetworkError();

			expect(toast.error).toHaveBeenCalledTimes(1);
			expect(toast.error).toHaveBeenCalledWith('Network error', {
				description: 'Please check your connection and try again.'
			});
		});
	});

	describe('showSuccess', () => {
		it('displays success toast with message and optional description', () => {
			fc.assert(
				fc.property(
					fc.string({ minLength: 1 }),
					fc.option(fc.string({ minLength: 1 }), { nil: undefined }),
					(message, description) => {
						vi.clearAllMocks();

						showSuccess(message, description);

						expect(toast.success).toHaveBeenCalledTimes(1);
						expect(toast.success).toHaveBeenCalledWith(message, {
							description
						});
					}
				),
				{ numRuns: 100 }
			);
		});
	});

	describe('showError', () => {
		it('displays sanitized error toast with message and optional description', () => {
			fc.assert(
				fc.property(
					safeMessageArb,
					fc.option(safeMessageArb, { nil: undefined }),
					(message, description) => {
						vi.clearAllMocks();

						showError(message, description);

						expect(toast.error).toHaveBeenCalledTimes(1);
						expect(toast.error).toHaveBeenCalledWith(message, { description });
					}
				),
				{ numRuns: 100 }
			);
		});

		it('sanitizes unsafe messages in showError', () => {
			fc.assert(
				fc.property(unsafeMessageArb, (unsafeMessage) => {
					vi.clearAllMocks();

					showError(unsafeMessage);

					expect(toast.error).toHaveBeenCalledTimes(1);
					expect(toast.error).toHaveBeenCalledWith('An unexpected error occurred', {
						description: undefined
					});
				}),
				{ numRuns: 100 }
			);
		});
	});

	describe('showInfo', () => {
		it('displays info toast with message and optional description', () => {
			fc.assert(
				fc.property(
					fc.string({ minLength: 1 }),
					fc.option(fc.string({ minLength: 1 }), { nil: undefined }),
					(message, description) => {
						vi.clearAllMocks();

						showInfo(message, description);

						expect(toast.info).toHaveBeenCalledTimes(1);
						expect(toast.info).toHaveBeenCalledWith(message, { description });
					}
				),
				{ numRuns: 100 }
			);
		});
	});

	describe('showWarning', () => {
		it('displays warning toast with message and optional description', () => {
			fc.assert(
				fc.property(
					fc.string({ minLength: 1 }),
					fc.option(fc.string({ minLength: 1 }), { nil: undefined }),
					(message, description) => {
						vi.clearAllMocks();

						showWarning(message, description);

						expect(toast.warning).toHaveBeenCalledTimes(1);
						expect(toast.warning).toHaveBeenCalledWith(message, {
							description
						});
					}
				),
				{ numRuns: 100 }
			);
		});
	});
});
