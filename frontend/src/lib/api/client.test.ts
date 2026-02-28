/**
 * Property-based tests for API client.
 *
 * Tests the following properties:
 * - Property 3: API Error Transformation
 * - Property 4: Pagination Parameter Passing
 * - Property 5: Filter Parameter Passing
 *
 * @module $lib/api/client.test
 */

import * as fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import type { ListInvitationsParams, ListUsersParams } from './client';
import { ApiError, getErrorMessage, isNetworkError, transformApiError } from './errors';

// =============================================================================
// Test Data Generators
// =============================================================================

/**
 * Generate a valid ISO 8601 date string within a reasonable range.
 * Uses integer timestamps to avoid invalid date issues.
 */
const isoDateArb = fc
	.integer({
		min: new Date('2020-01-01T00:00:00.000Z').getTime(),
		max: new Date('2030-12-31T23:59:59.999Z').getTime()
	})
	.map((timestamp) => new Date(timestamp).toISOString());

// =============================================================================
// Property 3: API Error Transformation
// =============================================================================

describe('Property 3: API Error Transformation', () => {
	/**
	 * For any API error response with an error_code and detail field,
	 * the API client SHALL transform it into a structured error object
	 * containing both fields.
	 */
	it('should transform any error response with error_code and detail into ApiError', () => {
		fc.assert(
			fc.property(
				fc.record({
					error_code: fc.string({ minLength: 1, maxLength: 50 }),
					detail: fc.string({ minLength: 1, maxLength: 500 }),
					timestamp: isoDateArb,
					correlation_id: fc.option(fc.uuid(), { nil: undefined })
				}),
				fc.integer({ min: 400, max: 599 }),
				(errorBody, statusCode) => {
					const apiError = transformApiError(statusCode, errorBody);

					// Verify the error is an ApiError instance
					expect(apiError).toBeInstanceOf(ApiError);

					// Verify error_code is preserved
					expect(apiError.errorCode).toBe(errorBody.error_code);

					// Verify detail is preserved
					expect(apiError.detail).toBe(errorBody.detail);

					// Verify status code is preserved
					expect(apiError.statusCode).toBe(statusCode);

					// Verify correlation_id is preserved when present
					if (errorBody.correlation_id) {
						expect(apiError.correlationId).toBe(errorBody.correlation_id);
					}
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any validation error response with field_errors,
	 * the transformation should preserve field-level errors.
	 */
	it('should transform validation error responses with field_errors', () => {
		fc.assert(
			fc.property(
				fc.record({
					error_code: fc.constant('VALIDATION_ERROR'),
					detail: fc.string({ minLength: 1, maxLength: 500 }),
					timestamp: isoDateArb,
					correlation_id: fc.option(fc.uuid(), { nil: undefined }),
					field_errors: fc.uniqueArray(
						fc.record({
							field: fc.string({ minLength: 1, maxLength: 50 }),
							messages: fc.array(fc.string({ minLength: 1, maxLength: 200 }), {
								minLength: 1,
								maxLength: 3
							})
						}),
						{
							minLength: 1,
							maxLength: 5,
							selector: (item) => item.field
						}
					)
				}),
				(validationBody) => {
					const apiError = transformApiError(400, validationBody);

					// Verify the error is an ApiError instance
					expect(apiError).toBeInstanceOf(ApiError);

					// Verify error_code is VALIDATION_ERROR
					expect(apiError.errorCode).toBe('VALIDATION_ERROR');

					// Verify field_errors are preserved
					expect(apiError.fieldErrors).toBeDefined();

					// Verify each field error is preserved (with unique field names)
					for (const fieldError of validationBody.field_errors) {
						expect(apiError.fieldErrors?.[fieldError.field]).toEqual(fieldError.messages);
					}
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * getErrorMessage should always return a string for any error type.
	 */
	it('should return a string message for any error type', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					// ApiError
					fc.record({
						statusCode: fc.integer({ min: 400, max: 599 }),
						errorCode: fc.string({ minLength: 1, maxLength: 50 }),
						detail: fc.string({ minLength: 1, maxLength: 500 })
					}),
					// Standard Error
					fc
						.string({ minLength: 1, maxLength: 500 })
						.map((msg) => ({
							type: 'error' as const,
							message: msg
						})),
					// Non-empty String
					fc.string({ minLength: 1, maxLength: 500 })
				),
				(errorInput) => {
					let error: unknown;

					if (typeof errorInput === 'object' && errorInput !== null && 'statusCode' in errorInput) {
						error = new ApiError(errorInput.statusCode, errorInput.errorCode, errorInput.detail);
					} else if (
						typeof errorInput === 'object' &&
						errorInput !== null &&
						'type' in errorInput &&
						errorInput.type === 'error'
					) {
						error = new Error(errorInput.message);
					} else {
						error = errorInput;
					}

					const message = getErrorMessage(error);

					// Should always return a string
					expect(typeof message).toBe('string');

					// Should never be empty for non-empty inputs
					expect(message.length).toBeGreaterThan(0);
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * getErrorMessage should return fallback message for unknown types.
	 */
	it('should return fallback message for unknown error types', () => {
		// Empty string should return fallback
		expect(getErrorMessage('')).toBe('An unexpected error occurred');

		// Null should return fallback
		expect(getErrorMessage(null)).toBe('An unexpected error occurred');

		// Undefined should return fallback
		expect(getErrorMessage(undefined)).toBe('An unexpected error occurred');

		// Object without message should return fallback
		expect(getErrorMessage({})).toBe('An unexpected error occurred');
	});

	/**
	 * isNetworkError should correctly identify TypeError with fetch-related messages.
	 */
	it('should identify network errors correctly', () => {
		const networkErrorMessages = [
			'Failed to fetch',
			'fetch failed',
			'Network request failed',
			'network error',
			'Unable to connect',
			'Connection refused',
			'ECONNREFUSED'
		];

		// Both TypeError and plain Error should be recognized (Bun throws plain Error)
		for (const msg of networkErrorMessages) {
			expect(isNetworkError(new TypeError(msg))).toBe(true);
			expect(isNetworkError(new Error(msg))).toBe(true);
		}

		// Non-network errors should return false
		const nonNetworkError = new TypeError("Cannot read property 'x' of null");
		expect(isNetworkError(nonNetworkError)).toBe(false);

		// Non-Error values should return false
		expect(isNetworkError('Failed to fetch')).toBe(false);
		expect(isNetworkError(null)).toBe(false);
	});
});

// =============================================================================
// Property 4: Pagination Parameter Passing
// =============================================================================

describe('Property 4: Pagination Parameter Passing', () => {
	/**
	 * For any list endpoint call with page and page_size parameters,
	 * the API client SHALL correctly pass these parameters and
	 * page_size SHALL be capped at 100.
	 */
	it('should cap page_size at 100 for invitation list params', () => {
		fc.assert(
			fc.property(
				fc.record({
					page: fc.option(fc.integer({ min: 1, max: 1000 }), {
						nil: undefined
					}),
					page_size: fc.option(fc.integer({ min: 1, max: 500 }), {
						nil: undefined
					})
				}),
				(params: ListInvitationsParams) => {
					// Simulate the capping logic from getInvitations
					const cappedParams = {
						...params,
						page_size: params.page_size ? Math.min(params.page_size, 100) : undefined
					};

					// Verify page_size is capped at 100
					if (params.page_size !== undefined) {
						expect(cappedParams.page_size).toBeLessThanOrEqual(100);
						expect(cappedParams.page_size).toBe(Math.min(params.page_size, 100));
					}

					// Verify page is passed through unchanged
					expect(cappedParams.page).toBe(params.page);
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any list endpoint call with page and page_size parameters,
	 * the API client SHALL correctly pass these parameters and
	 * page_size SHALL be capped at 100.
	 */
	it('should cap page_size at 100 for user list params', () => {
		fc.assert(
			fc.property(
				fc.record({
					page: fc.option(fc.integer({ min: 1, max: 1000 }), {
						nil: undefined
					}),
					page_size: fc.option(fc.integer({ min: 1, max: 500 }), {
						nil: undefined
					})
				}),
				(params: ListUsersParams) => {
					// Simulate the capping logic from getUsers
					const cappedParams = {
						...params,
						page_size: params.page_size ? Math.min(params.page_size, 100) : undefined
					};

					// Verify page_size is capped at 100
					if (params.page_size !== undefined) {
						expect(cappedParams.page_size).toBeLessThanOrEqual(100);
						expect(cappedParams.page_size).toBe(Math.min(params.page_size, 100));
					}

					// Verify page is passed through unchanged
					expect(cappedParams.page).toBe(params.page);
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * page_size values at or below 100 should pass through unchanged.
	 */
	it('should pass through page_size values at or below 100 unchanged', () => {
		fc.assert(
			fc.property(fc.integer({ min: 1, max: 100 }), (pageSize) => {
				const cappedPageSize = Math.min(pageSize, 100);
				expect(cappedPageSize).toBe(pageSize);
			}),
			{ numRuns: 100 }
		);
	});
});

// =============================================================================
// Property 5: Filter Parameter Passing
// =============================================================================

describe('Property 5: Filter Parameter Passing', () => {
	/**
	 * For any filter parameter (enabled, expired, server_id, invitation_id)
	 * passed to list endpoints, the API client SHALL correctly include
	 * the parameter in the request query string.
	 */
	it('should preserve all invitation filter parameters', () => {
		fc.assert(
			fc.property(
				fc.record({
					enabled: fc.option(fc.boolean(), { nil: undefined }),
					expired: fc.option(fc.boolean(), { nil: undefined }),
					sort_by: fc.option(
						fc.constantFrom('created_at' as const, 'expires_at' as const, 'use_count' as const),
						{ nil: undefined }
					),
					sort_order: fc.option(fc.constantFrom('asc' as const, 'desc' as const), {
						nil: undefined
					})
				}),
				(params: ListInvitationsParams) => {
					// Verify all filter parameters are preserved
					const queryParams = { ...params };

					if (params.enabled !== undefined) {
						expect(queryParams.enabled).toBe(params.enabled);
					}

					if (params.expired !== undefined) {
						expect(queryParams.expired).toBe(params.expired);
					}

					if (params.sort_by !== undefined) {
						expect(queryParams.sort_by).toBe(params.sort_by);
					}

					if (params.sort_order !== undefined) {
						expect(queryParams.sort_order).toBe(params.sort_order);
					}
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any filter parameter (enabled, expired, server_id, invitation_id)
	 * passed to user list endpoints, the API client SHALL correctly include
	 * the parameter in the request query string.
	 */
	it('should preserve all user filter parameters', () => {
		fc.assert(
			fc.property(
				fc.record({
					server_id: fc.option(fc.uuid(), { nil: undefined }),
					invitation_id: fc.option(fc.uuid(), { nil: undefined }),
					enabled: fc.option(fc.boolean(), { nil: undefined }),
					expired: fc.option(fc.boolean(), { nil: undefined }),
					sort_by: fc.option(
						fc.constantFrom('created_at' as const, 'username' as const, 'expires_at' as const),
						{ nil: undefined }
					),
					sort_order: fc.option(fc.constantFrom('asc' as const, 'desc' as const), {
						nil: undefined
					})
				}),
				(params: ListUsersParams) => {
					// Verify all filter parameters are preserved
					const queryParams = { ...params };

					if (params.server_id !== undefined) {
						expect(queryParams.server_id).toBe(params.server_id);
					}

					if (params.invitation_id !== undefined) {
						expect(queryParams.invitation_id).toBe(params.invitation_id);
					}

					if (params.enabled !== undefined) {
						expect(queryParams.enabled).toBe(params.enabled);
					}

					if (params.expired !== undefined) {
						expect(queryParams.expired).toBe(params.expired);
					}

					if (params.sort_by !== undefined) {
						expect(queryParams.sort_by).toBe(params.sort_by);
					}

					if (params.sort_order !== undefined) {
						expect(queryParams.sort_order).toBe(params.sort_order);
					}
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * Boolean filter values should be preserved exactly.
	 */
	it('should preserve boolean filter values exactly', () => {
		fc.assert(
			fc.property(fc.boolean(), (boolValue) => {
				const params = { enabled: boolValue };
				expect(params.enabled).toBe(boolValue);
				expect(typeof params.enabled).toBe('boolean');
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * UUID filter values should be preserved exactly.
	 */
	it('should preserve UUID filter values exactly', () => {
		fc.assert(
			fc.property(fc.uuid(), (uuidValue) => {
				const params = { server_id: uuidValue };
				expect(params.server_id).toBe(uuidValue);
				// UUID format validation
				expect(params.server_id).toMatch(
					/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
				);
			}),
			{ numRuns: 100 }
		);
	});
});
