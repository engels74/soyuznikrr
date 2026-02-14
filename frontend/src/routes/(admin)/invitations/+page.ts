/**
 * Invitation list page load function.
 *
 * Fetches invitations with pagination, filtering, and sorting from URL params.
 * Supports server-side rendering and client-side navigation.
 *
 * @module routes/(admin)/invitations/+page
 */

import {
	createScopedClient,
	getInvitations,
	getServers,
	type InvitationListResponse,
	type ListInvitationsParams,
	type MediaServerWithLibrariesResponse
} from '$lib/api/client';
import { ApiError, asErrorResponse } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const client = createScopedClient(fetch);
	// Extract query parameters from URL
	const page = Number(url.searchParams.get('page')) || 1;
	const pageSize = Number(url.searchParams.get('page_size')) || 50;
	const enabledParam = url.searchParams.get('enabled');
	const expiredParam = url.searchParams.get('expired');
	const sortBy = url.searchParams.get('sort_by') as ListInvitationsParams['sort_by'] | null;
	const sortOrder = url.searchParams.get('sort_order') as
		| ListInvitationsParams['sort_order']
		| null;

	// Build params object, only including defined values
	const params: ListInvitationsParams = {
		page,
		page_size: pageSize
	};

	if (enabledParam !== null) {
		params.enabled = enabledParam === 'true';
	}

	if (expiredParam !== null) {
		params.expired = expiredParam === 'true';
	}

	if (sortBy) {
		params.sort_by = sortBy;
	}

	if (sortOrder) {
		params.sort_order = sortOrder;
	}

	try {
		// Fetch invitations and servers in parallel (servers needed for create dialog)
		// Servers errors are isolated so the invitations list still renders
		const [result, servers] = await Promise.all([
			getInvitations(params, client),
			getServers(true, client).then(
				(r) => r.data ?? ([] as MediaServerWithLibrariesResponse[]),
				() => [] as MediaServerWithLibrariesResponse[]
			)
		]);

		// Check for successful response with data
		if (result.data) {
			return {
				invitations: result.data,
				servers,
				error: null as Error | null,
				params
			};
		}

		// Handle error response
		const status = result.response?.status ?? 500;
		const errorBody = asErrorResponse(result.error);
		return {
			invitations: null as InvitationListResponse | null,
			servers,
			error: new ApiError(
				status,
				errorBody?.error_code ?? 'UNKNOWN_ERROR',
				errorBody?.detail ?? 'An error occurred'
			),
			params
		};
	} catch (err) {
		// Handle network errors
		return {
			invitations: null as InvitationListResponse | null,
			servers: [] as MediaServerWithLibrariesResponse[],
			error: err instanceof Error ? err : new Error('Failed to load invitations'),
			params
		};
	}
};
