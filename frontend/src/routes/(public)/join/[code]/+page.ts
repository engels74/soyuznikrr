/**
 * Join page load function.
 *
 * Validates the invitation code on page load and returns validation results.
 * Handles valid codes, invalid codes, and network errors.
 *
 * @module routes/(public)/join/[code]/+page
 */

import { type InvitationValidationResponse, validateInvitation } from '$lib/api/client';
import { ApiError } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	const { code } = params;

	try {
		const result = await validateInvitation(code);

		// Check for successful response with data
		if (result.data) {
			return {
				code,
				validation: result.data,
				error: null as Error | null
			};
		}

		// Handle error response
		const status = result.response?.status ?? 500;
		const errorBody = result.error as { error_code?: string; detail?: string } | undefined;
		return {
			code,
			validation: null as InvitationValidationResponse | null,
			error: new ApiError(
				status,
				errorBody?.error_code ?? 'UNKNOWN_ERROR',
				errorBody?.detail ?? 'An error occurred'
			)
		};
	} catch (err) {
		// Handle network errors
		return {
			code,
			validation: null as InvitationValidationResponse | null,
			error: err instanceof Error ? err : new Error('Failed to validate invitation code')
		};
	}
};
