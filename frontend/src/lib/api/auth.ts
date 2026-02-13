/**
 * Auth API wrappers for /api/auth/* endpoints.
 *
 * Uses raw fetch for auth endpoints that use cookie-based auth.
 * Types are imported from the auto-generated OpenAPI types.
 */

import type { components } from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

// =============================================================================
// Types — re-export from generated OpenAPI types
// =============================================================================

export type AuthFieldInfo = components['schemas']['AuthFieldInfo'];
export type ProviderAuthInfo = Omit<
	components['schemas']['ProviderAuthInfo'],
	'flow_type' | 'fields'
> & {
	/** Narrowed from the generated `string` to known flow types. */
	flow_type: 'oauth' | 'credentials';
	/** Always present (defaults to [] on backend). */
	fields: AuthFieldInfo[];
};
export type AuthMethodsResponse = Omit<
	components['schemas']['AuthMethodsResponse'],
	'provider_auth'
> & {
	provider_auth: ProviderAuthInfo[];
};

export interface AdminMeResponse {
	id: string;
	username: string;
	email: string | null;
	auth_method: string;
}

export interface AuthTokenResponse {
	refresh_token: string;
}

// =============================================================================
// Helpers
// =============================================================================

/**
 * Extract `detail` string from an unknown error response body.
 *
 * Backend error responses are `{ detail: string }`, but the raw-fetch
 * wrappers type errors as `unknown`. This helper narrows safely.
 */
export function getErrorDetail(error: unknown, fallback: string = 'Unknown error'): string {
	if (error != null && typeof error === 'object' && 'detail' in error) {
		const detail = (error as Record<string, unknown>).detail;
		if (typeof detail === 'string') return detail;
	}
	return fallback;
}

// =============================================================================
// API Functions
// =============================================================================

export async function getAuthMethods(
	customFetch: typeof globalThis.fetch = fetch
): Promise<AuthMethodsResponse> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/methods`, {
		credentials: 'include'
	});
	return response.json() as Promise<AuthMethodsResponse>;
}

export async function setupAdmin(
	data: { username: string; password: string; email?: string },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: AuthTokenResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/setup`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	const result = (await response.json()) as AuthTokenResponse;
	return { data: result };
}

export async function loginLocal(
	data: { username: string; password: string },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: AuthTokenResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/login`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	const result = (await response.json()) as AuthTokenResponse;
	return { data: result };
}

/**
 * Authenticate via an external provider.
 *
 * @param method - Provider method name (e.g., "plex", "jellyfin")
 * @param credentials - Provider-specific credentials
 */
export async function loginExternal(
	method: string,
	credentials: Record<string, string>,
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: AuthTokenResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/login/${method}`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ credentials }),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	const result = (await response.json()) as AuthTokenResponse;
	return { data: result };
}

export async function refreshToken(
	token: string,
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: AuthTokenResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/refresh`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ refresh_token: token }),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	const result = (await response.json()) as AuthTokenResponse;
	return { data: result };
}

export async function logout(
	token?: string,
	customFetch: typeof globalThis.fetch = fetch
): Promise<void> {
	await customFetch(`${API_BASE_URL}/api/auth/logout`, {
		method: 'POST',
		...(token
			? {
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ refresh_token: token })
				}
			: {}),
		credentials: 'include'
	});
}

export async function getMe(
	customFetch: typeof globalThis.fetch = fetch
): Promise<AdminMeResponse | null> {
	try {
		const response = await customFetch(`${API_BASE_URL}/api/auth/me`, {
			credentials: 'include'
		});
		if (!response.ok) return null;
		return (await response.json()) as AdminMeResponse;
	} catch {
		return null;
	}
}
