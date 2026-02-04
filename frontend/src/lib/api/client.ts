/**
 * Type-safe API client using openapi-fetch.
 *
 * Provides typed wrapper functions for all backend endpoints with
 * automatic base URL configuration from environment variables.
 *
 * @module $lib/api/client
 */

import createClient from 'openapi-fetch';
import type { components, paths } from './types';

// Base URL from environment variable, defaults to empty string for same-origin
const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

/**
 * Type-safe API client instance.
 * Use this directly for custom requests or use the typed wrapper functions below.
 */
export const api = createClient<paths>({
	baseUrl: API_BASE_URL,
	headers: {
		'Content-Type': 'application/json'
	}
});

// =============================================================================
// Type Aliases for convenience
// =============================================================================

export type InvitationResponse = components['schemas']['InvitationResponse'];
// Extended InvitationDetailResponse to include wizard fields (until OpenAPI types are regenerated)
export type InvitationDetailResponse = components['schemas']['InvitationDetailResponse'] & {
	pre_wizard?: WizardResponse | null;
	post_wizard?: WizardResponse | null;
};
export type InvitationListResponse = components['schemas']['InvitationListResponse'];
// Extended InvitationValidationResponse to include wizard fields (until OpenAPI types are regenerated)
export type InvitationValidationResponse = components['schemas']['InvitationValidationResponse'] & {
	pre_wizard?: WizardDetailResponse | null;
	post_wizard?: WizardDetailResponse | null;
};
export type CreateInvitationRequest = components['schemas']['CreateInvitationRequest'];
export type UpdateInvitationRequest = components['schemas']['UpdateInvitationRequest'];

export type UserResponse = components['schemas']['UserResponse'];
export type UserDetailResponse = components['schemas']['UserDetailResponse'];
export type UserListResponse = components['schemas']['UserListResponse'];
export type IdentityResponse = components['schemas']['IdentityResponse'];

export type MediaServerResponse = components['schemas']['MediaServerResponse'];
export type MediaServerWithLibrariesResponse =
	components['schemas']['MediaServerWithLibrariesResponse'];
export type LibraryResponse = components['schemas']['LibraryResponse'];

export type SyncRequest = components['schemas']['SyncRequest'];

// SyncResult is manually defined because the OpenAPI generator doesn't handle
// Union return types well (Response[SyncResult] | Response[ErrorResponse])
export interface SyncResult {
	server_id: string;
	server_name: string;
	synced_at: string;
	orphaned_users: string[];
	stale_users: string[];
	matched_users: number;
}

export type RedeemInvitationRequest = components['schemas']['RedeemInvitationRequest'];
export type RedemptionResponse = components['schemas']['RedemptionResponse'];
export type RedemptionErrorResponse = components['schemas']['RedemptionErrorResponse'];

export type PlexOAuthPinResponse = components['schemas']['PlexOAuthPinResponse'];
export type PlexOAuthCheckResponse = components['schemas']['PlexOAuthCheckResponse'];

// ErrorResponse is manually defined because it's not used directly in endpoint responses
export interface ErrorResponse {
	detail: string;
	error_code: string;
	timestamp: string;
	correlation_id?: string | null;
}

// ValidationErrorResponse is manually defined for consistency
export interface ValidationErrorResponse extends ErrorResponse {
	field_errors: Array<{
		field: string;
		messages: string[];
	}>;
}

// =============================================================================
// Invitation API Wrappers
// =============================================================================

/** Parameters for listing invitations */
export interface ListInvitationsParams {
	page?: number;
	page_size?: number;
	enabled?: boolean;
	expired?: boolean;
	sort_by?: 'created_at' | 'expires_at' | 'use_count';
	sort_order?: 'asc' | 'desc';
}

/**
 * List invitations with pagination, filtering, and sorting.
 *
 * @param params - Query parameters for filtering and pagination
 * @returns Paginated list of invitations
 */
export async function getInvitations(params: ListInvitationsParams = {}) {
	// Cap page_size at 100 as per requirements
	const cappedParams = {
		...params,
		page_size: params.page_size ? Math.min(params.page_size, 100) : undefined
	};
	return api.GET('/api/v1/invitations', { params: { query: cappedParams } });
}

/**
 * Get a single invitation by ID.
 *
 * @param invitationId - UUID of the invitation
 * @returns Invitation detail response
 */
export async function getInvitation(invitationId: string) {
	return api.GET('/api/v1/invitations/{invitation_id}', {
		params: { path: { invitation_id: invitationId } }
	});
}

/**
 * Create a new invitation.
 *
 * @param data - Invitation creation data
 * @returns Created invitation detail response
 */
export async function createInvitation(data: CreateInvitationRequest) {
	return api.POST('/api/v1/invitations', { body: data });
}

/**
 * Update an existing invitation.
 *
 * @param invitationId - UUID of the invitation to update
 * @param data - Fields to update
 * @returns Updated invitation detail response
 */
export async function updateInvitation(invitationId: string, data: UpdateInvitationRequest) {
	return api.PATCH('/api/v1/invitations/{invitation_id}', {
		params: { path: { invitation_id: invitationId } },
		body: data
	});
}

/**
 * Delete an invitation.
 *
 * @param invitationId - UUID of the invitation to delete
 * @returns Empty response on success
 */
export async function deleteInvitation(invitationId: string) {
	return api.DELETE('/api/v1/invitations/{invitation_id}', {
		params: { path: { invitation_id: invitationId } }
	});
}

/**
 * Validate an invitation code without redeeming it.
 *
 * @param code - Invitation code to validate
 * @returns Validation response with target servers if valid
 */
export async function validateInvitation(code: string) {
	return api.GET('/api/v1/invitations/validate/{code}', {
		params: { path: { code } }
	});
}

// =============================================================================
// User API Wrappers
// =============================================================================

/** Parameters for listing users */
export interface ListUsersParams {
	page?: number;
	page_size?: number;
	server_id?: string;
	invitation_id?: string;
	enabled?: boolean;
	expired?: boolean;
	sort_by?: 'created_at' | 'username' | 'expires_at';
	sort_order?: 'asc' | 'desc';
}

/**
 * List users with pagination, filtering, and sorting.
 *
 * @param params - Query parameters for filtering and pagination
 * @returns Paginated list of users with relationships
 */
export async function getUsers(params: ListUsersParams = {}) {
	// Cap page_size at 100 as per requirements
	const cappedParams = {
		...params,
		page_size: params.page_size ? Math.min(params.page_size, 100) : undefined
	};
	return api.GET('/api/v1/users', { params: { query: cappedParams } });
}

/**
 * Get a single user by ID.
 *
 * @param userId - UUID of the user
 * @returns User detail response with relationships
 */
export async function getUser(userId: string) {
	return api.GET('/api/v1/users/{user_id}', {
		params: { path: { user_id: userId } }
	});
}

/**
 * Enable a user account.
 *
 * @param userId - UUID of the user to enable
 * @returns Updated user detail response
 */
export async function enableUser(userId: string) {
	return api.POST('/api/v1/users/{user_id}/enable', {
		params: { path: { user_id: userId } }
	});
}

/**
 * Disable a user account.
 *
 * @param userId - UUID of the user to disable
 * @returns Updated user detail response
 */
export async function disableUser(userId: string) {
	return api.POST('/api/v1/users/{user_id}/disable', {
		params: { path: { user_id: userId } }
	});
}

/**
 * Delete a user account.
 *
 * @param userId - UUID of the user to delete
 * @returns Empty response on success
 */
export async function deleteUser(userId: string) {
	return api.DELETE('/api/v1/users/{user_id}', {
		params: { path: { user_id: userId } }
	});
}

/** User permissions update request */
export interface UpdateUserPermissions {
	can_download?: boolean;
	can_stream?: boolean;
	can_sync?: boolean;
	can_transcode?: boolean;
}

/**
 * Update user permissions on the media server.
 *
 * @param userId - UUID of the user to update
 * @param permissions - Permission values to update
 * @returns Updated user detail response
 */
export async function updateUserPermissions(userId: string, permissions: UpdateUserPermissions) {
	return api.PATCH('/api/v1/users/{user_id}/permissions', {
		params: { path: { user_id: userId } },
		body: permissions
	});
}

// =============================================================================
// Server API Wrappers
// =============================================================================

/**
 * List all media servers with their libraries.
 *
 * @param enabled - Optional filter for enabled servers only
 * @returns List of servers with libraries
 */
export async function getServers(enabled?: boolean) {
	return api.GET('/api/v1/servers', {
		params: { query: enabled !== undefined ? { enabled } : {} }
	});
}

/**
 * Sync users between local database and media server.
 *
 * @param serverId - UUID of the server to sync
 * @param dryRun - If true, only report discrepancies without making changes
 * @returns Sync result with discrepancy report
 */
export async function syncServer(serverId: string, dryRun = true) {
	return api.POST('/api/v1/servers/{server_id}/sync', {
		params: { path: { server_id: serverId } },
		body: { dry_run: dryRun }
	});
}

/** Create server request */
export interface CreateServerRequest {
	name: string;
	server_type: 'jellyfin' | 'plex';
	url: string;
	api_key: string;
}

/**
 * Create a new media server.
 *
 * @param data - Server creation data
 * @returns Created media server response
 */
export async function createServer(data: CreateServerRequest) {
	return api.POST('/api/v1/servers', { body: data });
}

/**
 * Get a single media server by ID.
 *
 * @param serverId - UUID of the server
 * @returns Media server response
 */
export async function getServer(serverId: string) {
	return api.GET('/api/v1/servers/{server_id}', {
		params: { path: { server_id: serverId } }
	});
}

/**
 * Delete a media server.
 *
 * @param serverId - UUID of the server to delete
 * @returns Empty response on success
 */
export async function deleteServer(serverId: string) {
	return api.DELETE('/api/v1/servers/{server_id}', {
		params: { path: { server_id: serverId } }
	});
}

// =============================================================================
// Join Flow API Wrappers
// =============================================================================

/**
 * Redeem an invitation code to create user accounts.
 *
 * @param code - Invitation code to redeem
 * @param data - Registration data (username, password, optional email)
 * @returns Redemption response with created users
 */
export async function redeemInvitation(code: string, data: RedeemInvitationRequest) {
	return api.POST('/api/v1/join/{code}', {
		params: { path: { code } },
		body: data
	});
}

// =============================================================================
// Plex OAuth API Wrappers
// =============================================================================

/**
 * Create a Plex OAuth PIN for authentication.
 *
 * @returns PIN response with auth URL
 */
export async function createPlexPin() {
	return api.POST('/api/v1/join/plex/oauth/pin');
}

/**
 * Check the status of a Plex OAuth PIN.
 *
 * @param pinId - PIN ID to check
 * @returns Check response with authentication status
 */
export async function checkPlexPin(pinId: number) {
	return api.GET('/api/v1/join/plex/oauth/pin/{pin_id}', {
		params: { path: { pin_id: pinId } }
	});
}

// =============================================================================
// Health API Wrappers
// =============================================================================

/**
 * Check the health status of the backend.
 * Note: Uses direct fetch since health endpoint isn't in OpenAPI spec.
 *
 * @returns Health check response
 */
export async function healthCheck() {
	const response = await fetch(`${API_BASE_URL}/health`);
	return response.json() as Promise<{ status: string; checks: Record<string, boolean> }>;
}

// =============================================================================
// Wizard Types (manually defined until OpenAPI regeneration)
// =============================================================================

/** Wizard step configuration types */
export interface ClickConfig {
	button_text?: string;
}

export interface TimerConfig {
	duration_seconds: number;
}

export interface TosConfig {
	checkbox_label?: string;
}

export interface TextInputConfig {
	label: string;
	placeholder?: string;
	required?: boolean;
	min_length?: number;
	max_length?: number;
}

export interface QuizConfig {
	question: string;
	options: string[];
	correct_answer_index: number;
}

export type StepConfig = ClickConfig | TimerConfig | TosConfig | TextInputConfig | QuizConfig;

/** Wizard step response */
export interface WizardStepResponse {
	id: string;
	wizard_id: string;
	step_order: number;
	interaction_type: 'click' | 'timer' | 'tos' | 'text_input' | 'quiz';
	title: string;
	content_markdown: string;
	config: { [key: string]: string | number | boolean | string[] | null };
	created_at: string;
	updated_at?: string | null;
}

/** Wizard response (without steps) */
export interface WizardResponse {
	id: string;
	name: string;
	enabled: boolean;
	created_at: string;
	description?: string | null;
	updated_at?: string | null;
}

/** Wizard detail response (with steps) */
export interface WizardDetailResponse {
	id: string;
	name: string;
	enabled: boolean;
	created_at: string;
	steps: WizardStepResponse[];
	description?: string | null;
	updated_at?: string | null;
}

/** Wizard list response */
export interface WizardListResponse {
	items: WizardResponse[];
	total: number;
	page: number;
	page_size: number;
	has_next: boolean;
}

/** Step validation response */
export interface StepValidationResponse {
	valid: boolean;
	completion_token?: string | null;
	error?: string | null;
}

/** Create wizard request */
export interface CreateWizardRequest {
	name: string;
	description?: string | null;
	enabled?: boolean;
}

/** Update wizard request */
export interface UpdateWizardRequest {
	name?: string | null;
	description?: string | null;
	enabled?: boolean | null;
}

/** Create wizard step request */
export interface CreateWizardStepRequest {
	interaction_type: 'click' | 'timer' | 'tos' | 'text_input' | 'quiz';
	title: string;
	content_markdown: string;
	config?: { [key: string]: string | number | boolean | string[] | null };
	step_order?: number | null;
}

/** Update wizard step request */
export interface UpdateWizardStepRequest {
	title?: string | null;
	content_markdown?: string | null;
	config?: { [key: string]: string | number | boolean | string[] | null } | null;
}

/** Step reorder request */
export interface StepReorderRequest {
	new_order: number;
}

/** Step validation request */
export interface StepValidationRequest {
	step_id: string;
	response: { [key: string]: string | number | boolean | null };
	started_at?: string | null;
}

// =============================================================================
// Wizard API Wrappers
// =============================================================================

/** Parameters for listing wizards */
export interface ListWizardsParams {
	page?: number;
	page_size?: number;
}

/**
 * List wizards with pagination.
 *
 * @param params - Query parameters for pagination
 * @returns Paginated list of wizards
 */
export async function getWizards(params: ListWizardsParams = {}) {
	const queryParams = new URLSearchParams();
	if (params.page !== undefined) queryParams.set('page', String(params.page));
	if (params.page_size !== undefined) queryParams.set('page_size', String(params.page_size));

	const queryString = queryParams.toString();
	const url = `${API_BASE_URL}/api/v1/wizards${queryString ? `?${queryString}` : ''}`;

	const response = await fetch(url, {
		headers: { 'Content-Type': 'application/json' }
	});

	if (!response.ok) {
		const error = await response.json();
		return { data: undefined, error };
	}

	const data = (await response.json()) as WizardListResponse;
	return { data, error: undefined };
}

/**
 * Get a single wizard by ID with all its steps.
 *
 * @param wizardId - UUID of the wizard
 * @returns Wizard detail response with steps
 */
export async function getWizard(wizardId: string) {
	const response = await fetch(`${API_BASE_URL}/api/v1/wizards/${wizardId}`, {
		headers: { 'Content-Type': 'application/json' }
	});

	if (!response.ok) {
		const error = await response.json();
		return { data: undefined, error };
	}

	const data = (await response.json()) as WizardDetailResponse;
	return { data, error: undefined };
}

/**
 * Create a new wizard.
 *
 * @param data - Wizard creation data
 * @returns Created wizard response
 */
export async function createWizard(data: CreateWizardRequest) {
	const response = await fetch(`${API_BASE_URL}/api/v1/wizards`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});

	if (!response.ok) {
		const error = await response.json();
		return { data: undefined, error };
	}

	const result = (await response.json()) as WizardResponse;
	return { data: result, error: undefined };
}

/**
 * Update an existing wizard.
 *
 * @param wizardId - UUID of the wizard to update
 * @param data - Fields to update
 * @returns Updated wizard response
 */
export async function updateWizard(wizardId: string, data: UpdateWizardRequest) {
	const response = await fetch(`${API_BASE_URL}/api/v1/wizards/${wizardId}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});

	if (!response.ok) {
		const error = await response.json();
		return { data: undefined, error };
	}

	const result = (await response.json()) as WizardResponse;
	return { data: result, error: undefined };
}

/**
 * Delete a wizard.
 *
 * @param wizardId - UUID of the wizard to delete
 * @returns Empty response on success
 */
export async function deleteWizard(wizardId: string) {
	const response = await fetch(`${API_BASE_URL}/api/v1/wizards/${wizardId}`, {
		method: 'DELETE',
		headers: { 'Content-Type': 'application/json' }
	});

	if (!response.ok) {
		const error = await response.json();
		return { data: undefined, error };
	}

	return { data: null, error: undefined };
}

/**
 * Create a new wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param data - Step creation data
 * @returns Created step response
 */
export async function createStep(wizardId: string, data: CreateWizardStepRequest) {
	const response = await fetch(`${API_BASE_URL}/api/v1/wizards/${wizardId}/steps`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});

	if (!response.ok) {
		const error = await response.json();
		return { data: undefined, error };
	}

	const result = (await response.json()) as WizardStepResponse;
	return { data: result, error: undefined };
}

/**
 * Update an existing wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param stepId - UUID of the step to update
 * @param data - Fields to update
 * @returns Updated step response
 */
export async function updateStep(wizardId: string, stepId: string, data: UpdateWizardStepRequest) {
	const response = await fetch(`${API_BASE_URL}/api/v1/wizards/${wizardId}/steps/${stepId}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});

	if (!response.ok) {
		const error = await response.json();
		return { data: undefined, error };
	}

	const result = (await response.json()) as WizardStepResponse;
	return { data: result, error: undefined };
}

/**
 * Delete a wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param stepId - UUID of the step to delete
 * @returns Empty response on success
 */
export async function deleteStep(wizardId: string, stepId: string) {
	const response = await fetch(`${API_BASE_URL}/api/v1/wizards/${wizardId}/steps/${stepId}`, {
		method: 'DELETE',
		headers: { 'Content-Type': 'application/json' }
	});

	if (!response.ok) {
		const error = await response.json();
		return { data: undefined, error };
	}

	return { data: null, error: undefined };
}

/**
 * Reorder a wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param stepId - UUID of the step to reorder
 * @param newOrder - New position for the step
 * @returns Updated step response
 */
export async function reorderStep(wizardId: string, stepId: string, newOrder: number) {
	const response = await fetch(
		`${API_BASE_URL}/api/v1/wizards/${wizardId}/steps/${stepId}/reorder`,
		{
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ new_order: newOrder })
		}
	);

	if (!response.ok) {
		const error = await response.json();
		return { data: undefined, error };
	}

	const result = (await response.json()) as WizardStepResponse;
	return { data: result, error: undefined };
}

/**
 * Validate a wizard step completion.
 *
 * @param data - Step validation request
 * @returns Validation response with completion token if valid
 */
export async function validateStep(data: StepValidationRequest) {
	const response = await fetch(`${API_BASE_URL}/api/v1/wizards/validate-step`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});

	if (!response.ok) {
		const error = await response.json();
		return { data: undefined, error };
	}

	const result = (await response.json()) as StepValidationResponse;
	return { data: result, error: undefined };
}
