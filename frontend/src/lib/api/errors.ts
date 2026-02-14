/**
 * API error handling utilities.
 *
 * Provides structured error handling for API responses including:
 * - ApiError class for typed error handling
 * - Error transformation from API responses
 * - Helper functions for error message extraction
 *
 * @module $lib/api/errors
 */

import type { ErrorResponse, ValidationErrorResponse } from './client';

/**
 * Structured API error with typed fields.
 *
 * Provides a consistent error interface for all API errors,
 * including status code, error code, and optional correlation ID.
 */
export class ApiError extends Error {
	/** HTTP status code */
	readonly statusCode: number;
	/** Machine-readable error code (e.g., "NOT_FOUND", "VALIDATION_ERROR") */
	readonly errorCode: string;
	/** Human-readable error description */
	readonly detail: string;
	/** Optional correlation ID for tracing errors in logs */
	readonly correlationId?: string;
	/** Optional field-level validation errors */
	readonly fieldErrors?: Record<string, string[]>;

	constructor(
		statusCode: number,
		errorCode: string,
		detail: string,
		correlationId?: string,
		fieldErrors?: Record<string, string[]>
	) {
		super(detail);
		this.name = 'ApiError';
		this.statusCode = statusCode;
		this.errorCode = errorCode;
		this.detail = detail;
		this.correlationId = correlationId;
		this.fieldErrors = fieldErrors;
	}

	/**
	 * Create an ApiError from a standard error response.
	 *
	 * @param status - HTTP status code
	 * @param body - Error response body
	 * @returns ApiError instance
	 */
	static fromResponse(status: number, body: ErrorResponse): ApiError {
		return new ApiError(status, body.error_code, body.detail, body.correlation_id ?? undefined);
	}

	/**
	 * Create an ApiError from a validation error response.
	 *
	 * @param status - HTTP status code
	 * @param body - Validation error response body
	 * @returns ApiError instance with field errors
	 */
	static fromValidationResponse(status: number, body: ValidationErrorResponse): ApiError {
		const fieldErrors: Record<string, string[]> = {};
		for (const fieldError of body.field_errors) {
			fieldErrors[fieldError.field] = fieldError.messages;
		}
		return new ApiError(
			status,
			body.error_code,
			body.detail,
			body.correlation_id ?? undefined,
			fieldErrors
		);
	}

	/**
	 * Check if this is a validation error.
	 */
	isValidationError(): boolean {
		return this.errorCode === 'VALIDATION_ERROR';
	}

	/**
	 * Check if this is a not found error.
	 */
	isNotFoundError(): boolean {
		return this.statusCode === 404 || this.errorCode === 'NOT_FOUND';
	}

	/**
	 * Check if this is a server error.
	 */
	isServerError(): boolean {
		return this.statusCode >= 500;
	}
}

/**
 * Safely cast an unknown API error body to ErrorResponse.
 *
 * openapi-fetch returns error bodies typed as `unknown`. This utility provides
 * runtime validation instead of raw `as unknown as ErrorResponse` casts.
 *
 * @param error - The unknown error body from an API response
 * @returns Typed ErrorResponse if the shape matches, otherwise undefined
 */
export function asErrorResponse(error: unknown): ErrorResponse | undefined {
	if (error && typeof error === 'object' && 'detail' in error) {
		return error as ErrorResponse;
	}
	return undefined;
}

/**
 * Extract a user-friendly error message from any error.
 *
 * Handles ApiError, standard Error, and unknown error types.
 *
 * @param error - The error to extract a message from
 * @returns Human-readable error message
 */
export function getErrorMessage(error: unknown): string {
	if (error instanceof ApiError) {
		return error.detail;
	}
	if (error instanceof Error) {
		return error.message;
	}
	if (typeof error === 'string' && error.length > 0) {
		return error;
	}
	return 'An unexpected error occurred';
}

/**
 * Check if an error is a network error (fetch failed).
 *
 * Network errors typically occur when:
 * - The server is unreachable
 * - The request was blocked by CORS
 * - The network connection was lost
 *
 * @param error - The error to check
 * @returns True if this is a network error
 */
export function isNetworkError(error: unknown): boolean {
	if (error instanceof TypeError) {
		const message = error.message.toLowerCase();
		return (
			message.includes('fetch') ||
			message.includes('network') ||
			message.includes('failed to fetch')
		);
	}
	return false;
}

/**
 * Check if an error is an ApiError.
 *
 * @param error - The error to check
 * @returns True if this is an ApiError
 */
export function isApiError(error: unknown): error is ApiError {
	return error instanceof ApiError;
}

/**
 * Map error codes to user-friendly messages.
 *
 * Provides consistent, user-friendly messages for common error codes.
 */
const ERROR_CODE_MESSAGES: Record<string, string> = {
	VALIDATION_ERROR: 'Please fix the errors below',
	NOT_FOUND: 'The requested resource was not found',
	USERNAME_TAKEN: 'This username is already taken. Please choose another.',
	SERVER_ERROR: 'Failed to connect to the media server',
	SERVER_UNREACHABLE: 'Media server is unreachable',
	INVALID_INVITATION: 'This invitation is no longer valid',
	UNAUTHORIZED: 'You are not authorized to perform this action',
	FORBIDDEN: 'Access denied'
};

/**
 * Get a user-friendly message for an error code.
 *
 * Falls back to the error code itself if no mapping exists.
 *
 * @param errorCode - The error code to look up
 * @returns User-friendly error message
 */
export function getErrorCodeMessage(errorCode: string): string {
	return ERROR_CODE_MESSAGES[errorCode] ?? errorCode;
}

/**
 * Transform an API response error into an ApiError.
 *
 * Handles both standard error responses and validation error responses.
 *
 * @param status - HTTP status code
 * @param body - Response body (may be ErrorResponse or ValidationErrorResponse)
 * @returns ApiError instance
 */
export function transformApiError(
	status: number,
	body: ErrorResponse | ValidationErrorResponse | unknown
): ApiError {
	// Check if it's a validation error response
	if (
		body &&
		typeof body === 'object' &&
		'field_errors' in body &&
		Array.isArray((body as ValidationErrorResponse).field_errors)
	) {
		return ApiError.fromValidationResponse(status, body as ValidationErrorResponse);
	}

	// Check if it's a standard error response
	if (body && typeof body === 'object' && 'error_code' in body && 'detail' in body) {
		return ApiError.fromResponse(status, body as ErrorResponse);
	}

	// Fallback for unknown error format
	return new ApiError(
		status,
		'UNKNOWN_ERROR',
		typeof body === 'string' ? body : 'An unexpected error occurred'
	);
}
