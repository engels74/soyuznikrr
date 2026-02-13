/**
 * Type-safe API client using openapi-fetch.
 *
 * Provides typed wrapper functions for all backend endpoints with
 * automatic base URL configuration from environment variables.
 *
 * @module $lib/api/client
 */

import createClient, { type Client } from 'openapi-fetch';
import { showApiError, showNetworkError } from '$lib/utils/toast';
import type { components, paths } from './types';

/** Type alias for a typed openapi-fetch client instance. */
export type ApiClient = Client<paths>;

// Base URL from environment variable, defaults to empty string for same-origin
const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

/**
 * Type-safe API client instance.
 * Use this directly for custom requests or use the typed wrapper functions below.
 */
export const api = createClient<paths>({
	baseUrl: API_BASE_URL,
	credentials: 'include',
	headers: {
		'Content-Type': 'application/json'
	}
});

/**
 * Create a scoped API client that uses a custom fetch function.
 * Use this in SvelteKit load functions to pass SvelteKit's provided fetch.
 */
export function createScopedClient(customFetch: typeof globalThis.fetch): ApiClient {
	return createClient<paths>({
		baseUrl: API_BASE_URL,
		credentials: 'include',
		headers: {
			'Content-Type': 'application/json'
		},
		fetch: customFetch
	});
}

// =============================================================================
// Type Aliases for convenience
// =============================================================================

export type InvitationResponse = components['schemas']['InvitationResponse'];
export type InvitationDetailResponse = components['schemas']['InvitationDetailResponse'];
export type InvitationListResponse = components['schemas']['InvitationListResponse'];
export type InvitationValidationResponse = components['schemas']['InvitationValidationResponse'];
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
	imported_users: number;
}

export type RedeemInvitationRequest = components['schemas']['RedeemInvitationRequest'];
export type RedemptionResponse = components['schemas']['RedemptionResponse'];
export type RedemptionErrorResponse = components['schemas']['RedemptionErrorResponse'];

export type OAuthPinResponse = components['schemas']['OAuthPinResponse'];
export type OAuthCheckResponse = components['schemas']['OAuthCheckResponse'];

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
// Error Handling Wrapper
// =============================================================================

/** Options for the withErrorHandling wrapper */
export interface WithErrorHandlingOptions {
	/** Whether to show error toasts automatically (default: true) */
	showErrorToast?: boolean;
}

/**
 * Wrapper for API calls that handles errors and shows toasts.
 *
 * Automatically displays toast notifications for API errors and network failures.
 * Use this wrapper around API calls to provide consistent error feedback to users.
 *
 * @param apiCall - Function that returns a promise with { data, error } shape
 * @param options - Configuration options
 * @returns The API call result with { data, error } shape
 *
 * @example
 * ```ts
 * const result = await withErrorHandling(() => deleteInvitation(id));
 * if (result.data) {
 *   showSuccess('Invitation deleted');
 * }
 * ```
 */
export async function withErrorHandling<T>(
	apiCall: () => Promise<{ data?: T; error?: unknown }>,
	options?: WithErrorHandlingOptions
): Promise<{ data?: T; error?: unknown }> {
	const { showErrorToast = true } = options ?? {};

	try {
		const result = await apiCall();

		if (result.error && showErrorToast) {
			showApiError(result.error);
		}

		return result;
	} catch (error) {
		if (error instanceof TypeError && error.message.toLowerCase().includes('fetch')) {
			if (showErrorToast) {
				showNetworkError();
			}
		} else if (showErrorToast) {
			showApiError(error);
		}

		return { error };
	}
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
export async function getInvitations(params: ListInvitationsParams = {}, client: ApiClient = api) {
	// Cap page_size at 100 as per requirements
	const cappedParams = {
		...params,
		page_size: params.page_size ? Math.min(params.page_size, 100) : undefined
	};
	return client.GET('/api/v1/invitations', { params: { query: cappedParams } });
}

/**
 * Get a single invitation by ID.
 *
 * @param invitationId - UUID of the invitation
 * @returns Invitation detail response
 */
export async function getInvitation(invitationId: string, client: ApiClient = api) {
	return client.GET('/api/v1/invitations/{invitation_id}', {
		params: { path: { invitation_id: invitationId } }
	});
}

/**
 * Create a new invitation.
 *
 * @param data - Invitation creation data
 * @returns Created invitation detail response
 */
export async function createInvitation(data: CreateInvitationRequest, client: ApiClient = api) {
	return client.POST('/api/v1/invitations', { body: data });
}

/**
 * Update an existing invitation.
 *
 * @param invitationId - UUID of the invitation to update
 * @param data - Fields to update
 * @returns Updated invitation detail response
 */
export async function updateInvitation(
	invitationId: string,
	data: UpdateInvitationRequest,
	client: ApiClient = api
) {
	return client.PATCH('/api/v1/invitations/{invitation_id}', {
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
export async function deleteInvitation(invitationId: string, client: ApiClient = api) {
	return client.DELETE('/api/v1/invitations/{invitation_id}', {
		params: { path: { invitation_id: invitationId } }
	});
}

/**
 * Validate an invitation code without redeeming it.
 *
 * @param code - Invitation code to validate
 * @returns Validation response with target servers if valid
 */
export async function validateInvitation(code: string, client: ApiClient = api) {
	return client.GET('/api/v1/invitations/validate/{code}', {
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
export async function getUsers(params: ListUsersParams = {}, client: ApiClient = api) {
	// Cap page_size at 100 as per requirements
	const cappedParams = {
		...params,
		page_size: params.page_size ? Math.min(params.page_size, 100) : undefined
	};
	return client.GET('/api/v1/users', { params: { query: cappedParams } });
}

/**
 * Get a single user by ID.
 *
 * @param userId - UUID of the user
 * @returns User detail response with relationships
 */
export async function getUser(userId: string, client: ApiClient = api) {
	return client.GET('/api/v1/users/{user_id}', {
		params: { path: { user_id: userId } }
	});
}

/**
 * Enable a user account.
 *
 * @param userId - UUID of the user to enable
 * @returns Updated user detail response
 */
export async function enableUser(userId: string, client: ApiClient = api) {
	return client.POST('/api/v1/users/{user_id}/enable', {
		params: { path: { user_id: userId } }
	});
}

/**
 * Disable a user account.
 *
 * @param userId - UUID of the user to disable
 * @returns Updated user detail response
 */
export async function disableUser(userId: string, client: ApiClient = api) {
	return client.POST('/api/v1/users/{user_id}/disable', {
		params: { path: { user_id: userId } }
	});
}

/**
 * Delete a user account.
 *
 * @param userId - UUID of the user to delete
 * @returns Empty response on success
 */
export async function deleteUser(userId: string, client: ApiClient = api) {
	return client.DELETE('/api/v1/users/{user_id}', {
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
export async function updateUserPermissions(
	userId: string,
	permissions: UpdateUserPermissions,
	client: ApiClient = api
) {
	return client.PATCH('/api/v1/users/{user_id}/permissions', {
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
export async function getServers(enabled?: boolean, client: ApiClient = api) {
	return client.GET('/api/v1/servers', {
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
export async function syncServer(serverId: string, dryRun = false, client: ApiClient = api) {
	return client.POST('/api/v1/servers/{server_id}/sync', {
		params: { path: { server_id: serverId } },
		body: { dry_run: dryRun }
	});
}

/** Create server request */
export interface CreateServerRequest {
	name: string;
	server_type: string;
	url: string;
	api_key: string;
}

/**
 * Create a new media server.
 *
 * @param data - Server creation data
 * @returns Created media server response
 */
export async function createServer(data: CreateServerRequest, client: ApiClient = api) {
	return client.POST('/api/v1/servers', { body: data });
}

/**
 * Get a single media server by ID.
 *
 * @param serverId - UUID of the server
 * @returns Media server response
 */
export async function getServer(serverId: string, client: ApiClient = api) {
	return client.GET('/api/v1/servers/{server_id}', {
		params: { path: { server_id: serverId } }
	});
}

export type ConnectionTestRequest = components['schemas']['ConnectionTestRequest'];
export type ConnectionTestResponse = components['schemas']['ConnectionTestResponse'];

/**
 * Test a media server connection and optionally auto-detect server type.
 *
 * @param data - Connection test data (url, api_key, optional server_type)
 * @returns Connection test response
 */
export async function testConnection(data: ConnectionTestRequest, client: ApiClient = api) {
	return client.POST('/api/v1/servers/test-connection', { body: data });
}

/**
 * Delete a media server.
 *
 * @param serverId - UUID of the server to delete
 * @returns Empty response on success
 */
export async function deleteServer(serverId: string, client: ApiClient = api) {
	return client.DELETE('/api/v1/servers/{server_id}', {
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
export async function redeemInvitation(
	code: string,
	data: RedeemInvitationRequest,
	client: ApiClient = api
) {
	return client.POST('/api/v1/join/{code}', {
		params: { path: { code } },
		body: data
	});
}

// =============================================================================
// OAuth API Wrappers
// =============================================================================

/**
 * Create an OAuth PIN for authentication with a provider.
 *
 * @param provider - Provider type
 * @returns PIN response with auth URL
 */
export async function createOAuthPin(
	provider: string,
	client: ApiClient = api
): Promise<{ data?: OAuthPinResponse; error?: unknown }> {
	return client.POST('/api/v1/join/{provider}/oauth/pin', {
		params: { path: { provider } }
	});
}

/**
 * Check the status of an OAuth PIN.
 *
 * @param provider - Provider type
 * @param pinId - PIN ID to check
 * @returns Check response with authentication status
 */
export async function checkOAuthPin(
	provider: string,
	pinId: number,
	client: ApiClient = api
): Promise<{ data?: OAuthCheckResponse; error?: unknown }> {
	return client.GET('/api/v1/join/{provider}/oauth/pin/{pin_id}', {
		params: { path: { provider, pin_id: pinId } }
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
export async function healthCheck(customFetch: typeof globalThis.fetch = fetch) {
	const response = await customFetch(`${API_BASE_URL}/health`);
	return response.json() as Promise<{
		status: string;
		checks: Record<string, boolean>;
	}>;
}

// =============================================================================
// Wizard Types
// =============================================================================

/** Wizard step configuration types (not in OpenAPI spec) */
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

export type WizardStepResponse = components['schemas']['WizardStepResponse'];
export type WizardResponse = components['schemas']['WizardResponse'];
export type WizardDetailResponse = components['schemas']['WizardDetailResponse'];
export type WizardListResponse = components['schemas']['WizardListResponse'];
export type StepValidationResponse = components['schemas']['StepValidationResponse'];
export type StepValidationRequest = components['schemas']['StepValidationRequest'];
export type StepReorderRequest = components['schemas']['StepReorderRequest'];
export type CreateWizardRequest = components['schemas']['WizardCreate'];
export type UpdateWizardRequest = components['schemas']['WizardUpdate'];
export type CreateWizardStepRequest = components['schemas']['WizardStepCreate'];
export type UpdateWizardStepRequest = components['schemas']['WizardStepUpdate'];

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
export async function getWizards(params: ListWizardsParams = {}, client: ApiClient = api) {
	// Cap page_size at 100 as per requirements
	const cappedParams = {
		...params,
		page_size: params.page_size ? Math.min(params.page_size, 100) : undefined
	};
	return client.GET('/api/v1/wizards', { params: { query: cappedParams } });
}

/**
 * Get a single wizard by ID with all its steps.
 *
 * @param wizardId - UUID of the wizard
 * @returns Wizard detail response with steps
 */
export async function getWizard(wizardId: string, client: ApiClient = api) {
	return client.GET('/api/v1/wizards/{wizard_id}', {
		params: { path: { wizard_id: wizardId } }
	});
}

/**
 * Create a new wizard.
 *
 * @param data - Wizard creation data
 * @returns Created wizard response
 */
export async function createWizard(data: CreateWizardRequest, client: ApiClient = api) {
	return client.POST('/api/v1/wizards', { body: data });
}

/**
 * Update an existing wizard.
 *
 * @param wizardId - UUID of the wizard to update
 * @param data - Fields to update
 * @returns Updated wizard response
 */
export async function updateWizard(
	wizardId: string,
	data: UpdateWizardRequest,
	client: ApiClient = api
) {
	return client.PATCH('/api/v1/wizards/{wizard_id}', {
		params: { path: { wizard_id: wizardId } },
		body: data
	});
}

/**
 * Delete a wizard.
 *
 * @param wizardId - UUID of the wizard to delete
 * @returns Empty response on success
 */
export async function deleteWizard(wizardId: string, client: ApiClient = api) {
	return client.DELETE('/api/v1/wizards/{wizard_id}', {
		params: { path: { wizard_id: wizardId } }
	});
}

/**
 * Create a new wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param data - Step creation data
 * @returns Created step response
 */
export async function createStep(
	wizardId: string,
	data: CreateWizardStepRequest,
	client: ApiClient = api
) {
	return client.POST('/api/v1/wizards/{wizard_id}/steps', {
		params: { path: { wizard_id: wizardId } },
		body: data
	});
}

/**
 * Update an existing wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param stepId - UUID of the step to update
 * @param data - Fields to update
 * @returns Updated step response
 */
export async function updateStep(
	wizardId: string,
	stepId: string,
	data: UpdateWizardStepRequest,
	client: ApiClient = api
) {
	return client.PATCH('/api/v1/wizards/{wizard_id}/steps/{step_id}', {
		params: { path: { wizard_id: wizardId, step_id: stepId } },
		body: data
	});
}

/**
 * Delete a wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param stepId - UUID of the step to delete
 * @returns Empty response on success
 */
export async function deleteStep(wizardId: string, stepId: string, client: ApiClient = api) {
	return client.DELETE('/api/v1/wizards/{wizard_id}/steps/{step_id}', {
		params: { path: { wizard_id: wizardId, step_id: stepId } }
	});
}

/**
 * Reorder a wizard step.
 *
 * @param wizardId - UUID of the parent wizard
 * @param stepId - UUID of the step to reorder
 * @param newOrder - New position for the step
 * @returns Updated step response
 */
export async function reorderStep(
	wizardId: string,
	stepId: string,
	newOrder: number,
	client: ApiClient = api
) {
	return client.POST('/api/v1/wizards/{wizard_id}/steps/{step_id}/reorder', {
		params: { path: { wizard_id: wizardId, step_id: stepId } },
		body: { new_order: newOrder }
	});
}

/**
 * Validate a wizard step completion.
 *
 * @param data - Step validation request
 * @returns Validation response with completion token if valid
 */
export async function validateStep(data: StepValidationRequest, client: ApiClient = api) {
	return client.POST('/api/v1/wizards/validate-step', { body: data });
}
