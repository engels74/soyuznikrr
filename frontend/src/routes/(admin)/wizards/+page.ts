/**
 * Wizard list page load function.
 *
 * Fetches wizards with pagination from URL params.
 * Supports server-side rendering and client-side navigation.
 *
 * @module routes/(admin)/wizards/+page
 */

import {
	createScopedClient,
	getWizards,
	type ListWizardsParams,
	type WizardListResponse
} from '$lib/api/client';
import { ApiError, asErrorResponse } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const client = createScopedClient(fetch);

	// Extract query parameters from URL
	const page = Number(url.searchParams.get('page')) || 1;
	const pageSize = Number(url.searchParams.get('page_size')) || 50;

	const params: ListWizardsParams = {
		page,
		page_size: pageSize
	};

	try {
		const result = await getWizards(params, client);

		if (result.data) {
			return {
				wizards: result.data,
				error: null as Error | null,
				params
			};
		}

		// Handle error response
		const status = result.response?.status ?? 500;
		const errorBody = asErrorResponse(result.error);
		return {
			wizards: null as WizardListResponse | null,
			error: new ApiError(
				status,
				errorBody?.error_code ?? 'UNKNOWN_ERROR',
				errorBody?.detail ?? 'An error occurred'
			),
			params
		};
	} catch (err) {
		return {
			wizards: null as WizardListResponse | null,
			error: err instanceof Error ? err : new Error('Failed to load wizards'),
			params
		};
	}
};
