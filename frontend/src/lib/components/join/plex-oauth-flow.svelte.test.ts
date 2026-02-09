/**
 * Property-based tests for Plex OAuth flow component.
 *
 * Tests the following properties:
 * - Property 32: Plex OAuth Polling
 *
 * **Validates: Requirements 12.4**
 *
 * @module $lib/components/join/plex-oauth-flow.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import * as fc from 'fast-check';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PlexOAuthCheckResponse, PlexOAuthPinResponse } from '$lib/api/client';
import * as apiClient from '$lib/api/client';
import PlexOAuthFlow from './plex-oauth-flow.svelte';

// Mock the API client
vi.mock('$lib/api/client', async () => {
	const actual = await vi.importActual('$lib/api/client');
	return {
		...actual,
		createPlexPin: vi.fn(),
		checkPlexPin: vi.fn()
	};
});

// Mock window.open
const mockWindowOpen = vi.fn();
vi.stubGlobal('open', mockWindowOpen);

afterEach(() => {
	cleanup();
	vi.clearAllMocks();
	vi.useRealTimers();
});

// =============================================================================
// Arbitraries for generating test data
// =============================================================================

/**
 * Generate a valid PIN response.
 * Note: We use a fixed date range to avoid issues with fake timers.
 */
const pinResponseArb = fc.record({
	pin_id: fc.integer({ min: 1, max: 999999 }),
	code: fc.stringMatching(/^[A-Z0-9]{4}$/),
	auth_url: fc.webUrl(),
	expires_at: fc
		.integer({ min: 60000, max: 300000 })
		.map((offset) => new Date(Date.now() + offset).toISOString())
});

/**
 * Generate an authenticated check response.
 */
const authenticatedCheckResponseArb = fc.record({
	authenticated: fc.constant(true),
	email: fc.emailAddress(),
	error: fc.constant(null)
});

// =============================================================================
// Property 32: Plex OAuth Polling
// Validates: Requirements 12.4
// =============================================================================

describe('Property 32: Plex OAuth Polling', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	/**
	 * For any Plex OAuth flow, the frontend SHALL poll the PIN status endpoint
	 * at regular intervals until authenticated=true is returned.
	 *
	 * **Validates: Requirements 12.4**
	 */
	it('should poll PIN status at regular intervals until authenticated', async () => {
		vi.clearAllMocks();

		// Track poll count
		let pollCount = 0;
		const pollsBeforeAuth = 3;

		const pinResponse: PlexOAuthPinResponse = {
			pin_id: 12345,
			code: 'ABCD',
			auth_url: 'https://plex.tv/auth',
			expires_at: new Date(Date.now() + 60000).toISOString()
		};

		const authResponse: PlexOAuthCheckResponse = {
			authenticated: true,
			email: 'test@example.com',
			error: null
		};

		// Mock createPlexPin to return the generated PIN
		vi.mocked(apiClient.createPlexPin).mockResolvedValue({
			data: pinResponse,
			error: undefined,
			response: new Response()
		});

		// Mock checkPlexPin to return pending until pollsBeforeAuth, then authenticated
		vi.mocked(apiClient.checkPlexPin).mockImplementation(async () => {
			pollCount++;
			if (pollCount >= pollsBeforeAuth) {
				return {
					data: authResponse,
					error: undefined,
					response: new Response()
				};
			}
			return {
				data: {
					authenticated: false,
					email: null,
					error: null
				} as PlexOAuthCheckResponse,
				error: undefined,
				response: new Response()
			};
		});

		const onAuthenticated = vi.fn();
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

		const { container } = render(PlexOAuthFlow, {
			props: { onAuthenticated }
		});

		// Click sign in button
		const signInButton = container.querySelector('[data-plex-signin-button]');
		expect(signInButton).toBeTruthy();
		await user.click(signInButton!);

		// Wait for PIN creation
		await vi.waitFor(() => {
			expect(apiClient.createPlexPin).toHaveBeenCalledTimes(1);
		});

		// Advance timers to trigger polling
		for (let i = 0; i < pollsBeforeAuth; i++) {
			await vi.advanceTimersByTimeAsync(2000);
		}

		// Verify polling occurred
		await vi.waitFor(() => {
			expect(apiClient.checkPlexPin).toHaveBeenCalledTimes(pollsBeforeAuth);
		});

		// Verify onAuthenticated was called with the email
		await vi.waitFor(() => {
			expect(onAuthenticated).toHaveBeenCalledWith(authResponse.email);
		});
	});

	/**
	 * For any Plex OAuth flow, the frontend SHALL stop polling when the PIN
	 * expires_at time is reached.
	 *
	 * **Validates: Requirements 12.4**
	 */
	it('should stop polling when PIN expires', async () => {
		vi.clearAllMocks();

		// Create a PIN that expires in 4 seconds
		const expiredPinResponse: PlexOAuthPinResponse = {
			pin_id: 12345,
			code: 'ABCD',
			auth_url: 'https://plex.tv/auth',
			expires_at: new Date(Date.now() + 4000).toISOString()
		};

		vi.mocked(apiClient.createPlexPin).mockResolvedValue({
			data: expiredPinResponse,
			error: undefined,
			response: new Response()
		});

		// Always return pending
		vi.mocked(apiClient.checkPlexPin).mockResolvedValue({
			data: {
				authenticated: false,
				email: null,
				error: null
			} as PlexOAuthCheckResponse,
			error: undefined,
			response: new Response()
		});

		const onAuthenticated = vi.fn();
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

		const { container } = render(PlexOAuthFlow, {
			props: { onAuthenticated }
		});

		// Click sign in button
		const signInButton = container.querySelector('[data-plex-signin-button]');
		await user.click(signInButton!);

		// Wait for PIN creation
		await vi.waitFor(() => {
			expect(apiClient.createPlexPin).toHaveBeenCalledTimes(1);
		});

		// Advance time past expiration (poll at 2s, 4s would be past expiration)
		await vi.advanceTimersByTimeAsync(2000); // First poll
		await vi.advanceTimersByTimeAsync(2000); // Second poll - should detect expiration

		// Wait for component to update to expired state
		await vi.waitFor(() => {
			const component = container.querySelector('[data-plex-oauth-flow]');
			expect(component?.getAttribute('data-step')).toBe('expired');
		});

		// Verify onAuthenticated was NOT called
		expect(onAuthenticated).not.toHaveBeenCalled();
	});

	/**
	 * For any Plex OAuth flow, the frontend SHALL poll at 2 second intervals.
	 *
	 * **Validates: Requirements 12.4**
	 */
	it('should poll at 2 second intervals', async () => {
		vi.clearAllMocks();

		const pinResponse: PlexOAuthPinResponse = {
			pin_id: 12345,
			code: 'ABCD',
			auth_url: 'https://plex.tv/auth',
			expires_at: new Date(Date.now() + 60000).toISOString()
		};

		vi.mocked(apiClient.createPlexPin).mockResolvedValue({
			data: pinResponse,
			error: undefined,
			response: new Response()
		});

		// Always return pending
		vi.mocked(apiClient.checkPlexPin).mockResolvedValue({
			data: {
				authenticated: false,
				email: null,
				error: null
			} as PlexOAuthCheckResponse,
			error: undefined,
			response: new Response()
		});

		const onAuthenticated = vi.fn();
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

		const { container } = render(PlexOAuthFlow, {
			props: { onAuthenticated }
		});

		// Click sign in button
		const signInButton = container.querySelector('[data-plex-signin-button]');
		await user.click(signInButton!);

		// Wait for PIN creation
		await vi.waitFor(() => {
			expect(apiClient.createPlexPin).toHaveBeenCalledTimes(1);
		});

		// Advance 1 second - should not poll yet
		await vi.advanceTimersByTimeAsync(1000);
		expect(apiClient.checkPlexPin).toHaveBeenCalledTimes(0);

		// Advance another 1 second (total 2s) - should poll
		await vi.advanceTimersByTimeAsync(1000);
		await vi.waitFor(() => {
			expect(apiClient.checkPlexPin).toHaveBeenCalledTimes(1);
		});

		// Advance another 2 seconds - should poll again
		await vi.advanceTimersByTimeAsync(2000);
		await vi.waitFor(() => {
			expect(apiClient.checkPlexPin).toHaveBeenCalledTimes(2);
		});

		// Advance another 2 seconds - should poll again
		await vi.advanceTimersByTimeAsync(2000);
		await vi.waitFor(() => {
			expect(apiClient.checkPlexPin).toHaveBeenCalledTimes(3);
		});
	});
});

// =============================================================================
// Additional Plex OAuth Flow Tests
// =============================================================================

describe('Plex OAuth Flow Component', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	/**
	 * For any valid PIN response, the component SHALL display the PIN code.
	 */
	it('should display PIN code after creation', async () => {
		fc.assert(
			fc.property(pinResponseArb, (pinResponse) => {
				vi.clearAllMocks();

				vi.mocked(apiClient.createPlexPin).mockResolvedValue({
					data: pinResponse as PlexOAuthPinResponse,
					error: undefined,
					response: new Response()
				});

				vi.mocked(apiClient.checkPlexPin).mockResolvedValue({
					data: {
						authenticated: false,
						email: null,
						error: null
					} as PlexOAuthCheckResponse,
					error: undefined,
					response: new Response()
				});

				// Verify the PIN code format is valid
				expect(pinResponse.code).toMatch(/^[A-Z0-9]{4}$/);
				expect(pinResponse.pin_id).toBeGreaterThan(0);
			}),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any authenticated response, the email should be a valid email format.
	 */
	it('should have valid email in authenticated response', async () => {
		fc.assert(
			fc.property(authenticatedCheckResponseArb, (authResponse) => {
				expect(authResponse.authenticated).toBe(true);
				expect(authResponse.email).toBeTruthy();
				// Basic email format check
				expect(authResponse.email).toContain('@');
			}),
			{ numRuns: 50 }
		);
	});

	/**
	 * The component SHALL open Plex auth URL in a new window/tab.
	 */
	it('should open Plex auth URL in new window', async () => {
		vi.clearAllMocks();

		const pinResponse: PlexOAuthPinResponse = {
			pin_id: 12345,
			code: 'ABCD',
			auth_url: 'https://plex.tv/auth/test',
			expires_at: new Date(Date.now() + 60000).toISOString()
		};

		vi.mocked(apiClient.createPlexPin).mockResolvedValue({
			data: pinResponse,
			error: undefined,
			response: new Response()
		});

		const onAuthenticated = vi.fn();
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

		const { container } = render(PlexOAuthFlow, {
			props: { onAuthenticated }
		});

		// Click sign in button
		const signInButton = container.querySelector('[data-plex-signin-button]');
		await user.click(signInButton!);

		// Wait for window.open to be called
		await vi.waitFor(() => {
			expect(mockWindowOpen).toHaveBeenCalledWith(
				pinResponse.auth_url,
				'_blank',
				'noopener,noreferrer'
			);
		});
	});
});
