/**
 * Server list page load function.
 *
 * Fetches all media servers with their libraries.
 * Supports server-side rendering and client-side navigation.
 *
 * @module routes/(admin)/servers/+page
 */

import {
	createScopedClient,
	getServers,
	type MediaServerWithLibrariesResponse
} from '$lib/api/client';
import { ApiError, asErrorResponse } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const client = createScopedClient(fetch);
	try {
		const result = await getServers(undefined, client);

		if (result.data) {
			return {
				servers: result.data,
				error: null as Error | null
			};
		}

		// Handle error response
		const status = result.response?.status ?? 500;
		const errorBody = asErrorResponse(result.error);
		return {
			servers: [] as MediaServerWithLibrariesResponse[],
			error: new ApiError(
				status,
				errorBody?.error_code ?? 'UNKNOWN_ERROR',
				errorBody?.detail ?? 'An error occurred'
			)
		};
	} catch (err) {
		// Handle network errors
		return {
			servers: [] as MediaServerWithLibrariesResponse[],
			error: err instanceof Error ? err : new Error('Failed to load servers')
		};
	}
};
