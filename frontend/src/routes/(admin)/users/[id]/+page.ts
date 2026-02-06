/**
 * User detail page load function.
 *
 * Fetches a single user by ID with all relationships including:
 * - Identity information
 * - Media server information
 * - Source invitation (if available)
 * - Linked users across servers (via identity)
 *
 * @module routes/(admin)/users/[id]/+page
 */

import { createScopedClient, getUser, getUsers, type UserDetailResponse } from '$lib/api/client';
import { ApiError } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	const client = createScopedClient(fetch);
	const { id } = params;

	try {
		// Fetch user details
		const userResult = await getUser(id, client);

		// Handle user fetch error
		if (userResult.error) {
			const status = userResult.response?.status ?? 500;
			const errorBody = userResult.error as { error_code?: string; detail?: string };
			return {
				user: null as UserDetailResponse | null,
				linkedUsers: [] as UserDetailResponse[],
				error: new ApiError(
					status,
					errorBody?.error_code ?? 'UNKNOWN_ERROR',
					errorBody?.detail ?? 'Failed to load user'
				)
			};
		}

		const user = userResult.data;

		// Fetch linked users (users with the same identity_id)
		// This shows all users across servers that belong to the same identity
		let linkedUsers: UserDetailResponse[] = [];
		if (user?.identity_id) {
			// We need to fetch users and filter by identity
			// Since there's no direct endpoint for this, we fetch all users
			// and filter client-side (in a real app, this would be a dedicated endpoint)
			const linkedResult = await getUsers({ page_size: 100 }, client);
			if (linkedResult.data) {
				linkedUsers = linkedResult.data.items.filter(
					(u) => u.identity_id === user.identity_id && u.id !== user.id
				);
			}
		}

		return {
			user,
			linkedUsers,
			error: null as Error | null
		};
	} catch (err) {
		// Handle network errors
		return {
			user: null as UserDetailResponse | null,
			linkedUsers: [] as UserDetailResponse[],
			error: err instanceof Error ? err : new Error('Failed to load user')
		};
	}
};
