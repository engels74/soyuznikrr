/**
 * Server detail page load function.
 *
 * Fetches a single server by ID from the servers list.
 * Since there's no individual server endpoint, we fetch all servers
 * and filter by ID.
 *
 * @module routes/(admin)/servers/[id]/+page
 */

import {
	createScopedClient,
	type ErrorResponse,
	getServers,
	type MediaServerWithLibrariesResponse
} from '$lib/api/client';
import { ApiError } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	const client = createScopedClient(fetch);
	const { id } = params;

	try {
		// Fetch all servers and find the one with matching ID
		const result = await getServers(undefined, client);

		if (result.data) {
			const server = result.data.find((s) => s.id === id);

			if (server) {
				return {
					server,
					error: null as Error | null
				};
			}

			// Server not found
			return {
				server: null as MediaServerWithLibrariesResponse | null,
				error: new ApiError(404, 'NOT_FOUND', 'Server not found')
			};
		}

		// Handle error response
		const status = result.response?.status ?? 500;
		const errorBody = result.error as unknown as ErrorResponse | undefined;
		return {
			server: null as MediaServerWithLibrariesResponse | null,
			error: new ApiError(
				status,
				errorBody?.error_code ?? 'UNKNOWN_ERROR',
				errorBody?.detail ?? 'An error occurred'
			)
		};
	} catch (err) {
		// Handle network errors
		return {
			server: null as MediaServerWithLibrariesResponse | null,
			error: err instanceof Error ? err : new Error('Failed to load server')
		};
	}
};
