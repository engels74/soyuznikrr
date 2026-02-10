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
import { ApiError } from '$lib/api/errors';
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
		const errorBody = result.error as { error_code?: string; detail?: string } | undefined;
		return {
			wizard: null as WizardDetailResponse | null,
			error: new ApiError(
				404,
				errorBody?.error_code ?? 'NOT_FOUND',
				errorBody?.detail ?? 'Wizard not found'
			)
		};
	} catch (err) {
		return {
			wizard: null as WizardDetailResponse | null,
			error: err instanceof Error ? err : new Error('Failed to load wizard')
		};
	}
};
