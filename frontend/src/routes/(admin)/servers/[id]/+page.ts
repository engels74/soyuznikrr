/**
 * Server detail page load function.
 *
 * Fetches a single server by ID from the detail endpoint.
 *
 * @module routes/(admin)/servers/[id]/+page
 */

import { createScopedClient, getServer, type MediaServerDetailResponse } from '$lib/api/client';
import { ApiError, asErrorResponse } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	const client = createScopedClient(fetch);
	const { id } = params;

	try {
		const result = await getServer(id, client);

		if (result.data) {
			return {
				server: result.data,
				error: null as Error | null
			};
		}

		// Handle error response
		const status = result.response?.status ?? 500;
		const errorBody = asErrorResponse(result.error);
		return {
			server: null as MediaServerDetailResponse | null,
			error: new ApiError(
				status,
				errorBody?.error_code ?? 'UNKNOWN_ERROR',
				errorBody?.detail ?? 'An error occurred'
			)
		};
	} catch (err) {
		// Handle network errors
		return {
			server: null as MediaServerDetailResponse | null,
			error: err instanceof Error ? err : new Error('Failed to load server')
		};
	}
};
