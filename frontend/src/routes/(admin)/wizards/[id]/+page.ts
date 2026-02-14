/**
 * Wizard editor page load function.
 *
 * Fetches a single wizard with all its steps for editing.
 *
 * Requirements: 13.1-13.6
 *
 * @module routes/(admin)/wizards/[id]/+page
 */

import { createScopedClient, getWizard, type WizardDetailResponse } from '$lib/api/client';
import { ApiError, asErrorResponse } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	const client = createScopedClient(fetch);
	const { id } = params;

	try {
		const result = await getWizard(id, client);

		if (result.data) {
			return {
				wizard: result.data,
				error: null as Error | null
			};
		}

		// Handle error response
		const status = result.response?.status ?? 500;
		const errorBody = asErrorResponse(result.error);
		return {
			wizard: null as WizardDetailResponse | null,
			error: new ApiError(
				status,
				errorBody?.error_code ?? 'UNKNOWN_ERROR',
				errorBody?.detail ?? 'An error occurred'
			)
		};
	} catch (err) {
		return {
			wizard: null as WizardDetailResponse | null,
			error: err instanceof Error ? err : new Error('Failed to load wizard')
		};
	}
};
