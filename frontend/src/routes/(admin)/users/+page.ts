/**
 * User list page load function.
 *
 * Fetches users with pagination, filtering, and sorting from URL params.
 * Supports server-side rendering and client-side navigation.
 *
 * @module routes/(admin)/users/+page
 */

import {
	createScopedClient,
	getInvitations,
	getServers,
	getUsers,
	type ListUsersParams,
	type MediaServerWithLibrariesResponse,
	type UserListResponse
} from '$lib/api/client';
import { ApiError, asErrorResponse } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const client = createScopedClient(fetch);
	// Extract query parameters from URL
	const page = Number(url.searchParams.get('page')) || 1;
	const pageSize = Number(url.searchParams.get('page_size')) || 50;
	const serverId = url.searchParams.get('server_id');
	const invitationId = url.searchParams.get('invitation_id');
	const enabledParam = url.searchParams.get('enabled');
	const expiredParam = url.searchParams.get('expired');
	const sortBy = url.searchParams.get('sort_by') as ListUsersParams['sort_by'] | null;
	const sortOrder = url.searchParams.get('sort_order') as ListUsersParams['sort_order'] | null;

	// Build params object, only including defined values
	const params: ListUsersParams = {
		page,
		page_size: pageSize
	};

	if (serverId) {
		params.server_id = serverId;
	}

	if (invitationId) {
		params.invitation_id = invitationId;
	}

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
		// Fetch users, servers, and invitations in parallel for filter dropdowns
		const [usersResult, serversResult, invitationsResult] = await Promise.all([
			getUsers(params, client),
			getServers(undefined, client),
			getInvitations({ page_size: 100 }, client)
		]);

		// Check for successful users response
		if (usersResult.data) {
			return {
				users: usersResult.data,
				servers: serversResult.data ?? [],
				invitations: invitationsResult.data?.items ?? [],
				error: null as Error | null,
				params
			};
		}

		// Handle error response
		const status = usersResult.response?.status ?? 500;
		const errorBody = asErrorResponse(usersResult.error);
		return {
			users: null as UserListResponse | null,
			servers: serversResult.data ?? ([] as MediaServerWithLibrariesResponse[]),
			invitations: invitationsResult.data?.items ?? [],
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
			users: null as UserListResponse | null,
			servers: [] as MediaServerWithLibrariesResponse[],
			invitations: [],
			error: err instanceof Error ? err : new Error('Failed to load users'),
			params
		};
	}
};
