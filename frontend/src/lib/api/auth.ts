/**
 * Auth API wrappers for /api/auth/* endpoints.
 *
 * Uses raw fetch since these endpoints are not in the OpenAPI spec.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

// =============================================================================
// Types
// =============================================================================

export interface AuthMethodsResponse {
	methods: string[];
	setup_required: boolean;
}

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

export async function loginPlex(
	authToken: string,
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: AuthTokenResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/login/plex`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ auth_token: authToken }),
		credentials: 'include'
	});
	if (!response.ok) {
		const error = await response.json();
		return { error };
	}
	const result = (await response.json()) as AuthTokenResponse;
	return { data: result };
}

export async function loginJellyfin(
	data: { server_url: string; username: string; password: string },
	customFetch: typeof globalThis.fetch = fetch
): Promise<{ data?: AuthTokenResponse; error?: unknown }> {
	const response = await customFetch(`${API_BASE_URL}/api/auth/login/jellyfin`, {
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
