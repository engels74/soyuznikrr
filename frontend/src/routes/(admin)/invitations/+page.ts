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
	type InvitationListResponse,
	type ListInvitationsParams
} from '$lib/api/client';
import { ApiError } from '$lib/api/errors';
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
		const result = await getInvitations(params, client);

		// Check for successful response with data
		if (result.data) {
			return {
				invitations: result.data,
				error: null as Error | null,
				params
			};
		}

		// Handle error response
		const status = result.response?.status ?? 500;
		const errorBody = result.error as { error_code?: string; detail?: string } | undefined;
		return {
			invitations: null as InvitationListResponse | null,
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
			error: err instanceof Error ? err : new Error('Failed to load invitations'),
			params
		};
	}
};
