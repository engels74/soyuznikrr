/**
 * Invitation detail page load function.
 *
 * Fetches a single invitation by ID with all relationships.
 * Also fetches available servers and wizards for the edit form.
 *
 * @module routes/(admin)/invitations/[id]/+page
 */

import {
	createScopedClient,
	getInvitation,
	getServers,
	getWizards,
	type InvitationDetailResponse,
	type MediaServerWithLibrariesResponse,
	type WizardResponse
} from '$lib/api/client';
import { ApiError } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	const client = createScopedClient(fetch);
	const { id } = params;

	try {
		// Fetch invitation, servers, and wizards in parallel
		const [invitationResult, serversResult, wizardsResult] = await Promise.all([
			getInvitation(id, client),
			getServers(true, client),
			getWizards({ page_size: 100 }, fetch)
		]);

		// Handle invitation fetch error
		if (invitationResult.error) {
			const status = invitationResult.response?.status ?? 500;
			const errorBody = invitationResult.error as { error_code?: string; detail?: string };
			return {
				invitation: null as InvitationDetailResponse | null,
				servers: [] as MediaServerWithLibrariesResponse[],
				wizards: [] as WizardResponse[],
				error: new ApiError(
					status,
					errorBody?.error_code ?? 'UNKNOWN_ERROR',
					errorBody?.detail ?? 'Failed to load invitation'
				)
			};
		}

		// Handle servers fetch error (non-fatal, just use empty array)
		const servers = serversResult.data ?? [];

		// Handle wizards fetch error (non-fatal, just use empty array)
		// Only include enabled wizards
		const wizards = wizardsResult.data?.items.filter((w) => w.enabled) ?? [];

		// Cast the invitation data to include wizard fields
		const invitation = invitationResult.data as InvitationDetailResponse | undefined;

		return {
			invitation: invitation ?? null,
			servers,
			wizards,
			error: null as Error | null
		};
	} catch (err) {
		// Handle network errors
		return {
			invitation: null as InvitationDetailResponse | null,
			servers: [] as MediaServerWithLibrariesResponse[],
			wizards: [] as WizardResponse[],
			error: err instanceof Error ? err : new Error('Failed to load invitation')
		};
	}
};
