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
export type InvitationDetailResponse = components['schemas']['InvitationDetailResponse'];
export type InvitationListResponse = components['schemas']['InvitationListResponse'];
export type InvitationValidationResponse = components['schemas']['InvitationValidationResponse'];
export type CreateInvitationRequest = components['schemas']['CreateInvitationRequest'];
export type UpdateInvitationRequest = components['schemas']['UpdateInvitationRequest'];

export type UserResponse = components['schemas']['UserResponse'];
export type UserDetailResponse = components['schemas']['UserDetailResponse'];
export type UserListResponse = components['schemas']['UserListResponse'];

export type MediaServerResponse = components['schemas']['MediaServerResponse'];
export type MediaServerWithLibrariesResponse =
	components['schemas']['MediaServerWithLibrariesResponse'];
export type LibraryResponse = components['schemas']['LibraryResponse'];

export type SyncRequest = components['schemas']['SyncRequest'];
export type SyncResult = components['schemas']['SyncResult'];

export type RedeemInvitationRequest = components['schemas']['RedeemInvitationRequest'];
export type RedemptionResponse = components['schemas']['RedemptionResponse'];
export type RedemptionErrorResponse = components['schemas']['RedemptionErrorResponse'];

export type PlexOAuthPinResponse = components['schemas']['PlexOAuthPinResponse'];
export type PlexOAuthCheckResponse = components['schemas']['PlexOAuthCheckResponse'];

export type ErrorResponse = components['schemas']['ErrorResponse'];
export type ValidationErrorResponse = components['schemas']['ValidationErrorResponse'];

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

// =============================================================================
// Server API Wrappers
// =============================================================================

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
 *
 * @returns Health check response
 */
export async function healthCheck() {
	return api.GET('/health');
}
