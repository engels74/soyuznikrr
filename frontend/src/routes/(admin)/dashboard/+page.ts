import {
	createScopedClient,
	getDashboardStats,
	type DashboardStatsResponse
} from '$lib/api/client';
import { ApiError, asErrorResponse } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const client = createScopedClient(fetch);
	try {
		const result = await getDashboardStats(client);

		if (result.data) {
			return {
				stats: result.data,
				error: null as Error | null
			};
		}

		// Handle error response
		const status = result.response?.status ?? 500;
		const errorBody = asErrorResponse(result.error);
		return {
			stats: null as DashboardStatsResponse | null,
			error: new ApiError(
				status,
				errorBody?.error_code ?? 'UNKNOWN_ERROR',
				errorBody?.detail ?? 'An error occurred'
			)
		};
	} catch (err) {
		// Handle network errors
		return {
			stats: null as DashboardStatsResponse | null,
			error: err instanceof Error ? err : new Error('Failed to load dashboard')
		};
	}
};
