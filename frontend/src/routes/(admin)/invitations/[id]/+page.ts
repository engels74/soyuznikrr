/**
 * Invitation detail page load function.
 *
 * Fetches a single invitation by ID with all relationships.
 * Also fetches available servers for the edit form.
 *
 * @module routes/(admin)/invitations/[id]/+page
 */

import {
	getInvitation,
	getServers,
	type InvitationDetailResponse,
	type MediaServerWithLibrariesResponse
} from '$lib/api/client';
import { ApiError } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	const { id } = params;

	try {
		// Fetch invitation and servers in parallel
		const [invitationResult, serversResult] = await Promise.all([
			getInvitation(id),
			getServers(true) // Only enabled servers
		]);

		// Handle invitation fetch error
		if (invitationResult.error) {
			const status = invitationResult.response?.status ?? 500;
			const errorBody = invitationResult.error as { error_code?: string; detail?: string };
			return {
				invitation: null as InvitationDetailResponse | null,
				servers: [] as MediaServerWithLibrariesResponse[],
				error: new ApiError(
					status,
					errorBody?.error_code ?? 'UNKNOWN_ERROR',
					errorBody?.detail ?? 'Failed to load invitation'
				)
			};
		}

		// Handle servers fetch error (non-fatal, just use empty array)
		const servers = serversResult.data ?? [];

		return {
			invitation: invitationResult.data,
			servers,
			error: null as Error | null
		};
	} catch (err) {
		// Handle network errors
		return {
			invitation: null as InvitationDetailResponse | null,
			servers: [] as MediaServerWithLibrariesResponse[],
			error: err instanceof Error ? err : new Error('Failed to load invitation')
		};
	}
};
