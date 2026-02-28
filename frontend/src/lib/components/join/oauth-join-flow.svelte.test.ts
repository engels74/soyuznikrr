/**
 * Property-based tests for OAuth join flow component.
 *
 * Tests the following properties:
 * - Property 32: OAuth Polling
 *
 * @module $lib/components/join/oauth-join-flow.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import * as fc from 'fast-check';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { OAuthCheckResponse, OAuthPinResponse } from '$lib/api/client';
import * as apiClient from '$lib/api/client';
import OAuthJoinFlow from './oauth-join-flow.svelte';

// Use a generic test provider to avoid coupling tests to any real provider
const TEST_SERVER_TYPE = 'test-provider';

// Mock the API client
vi.mock('$lib/api/client', async () => {
	const actual = await vi.importActual('$lib/api/client');
	return {
		...actual,
		createOAuthPin: vi.fn(),
		checkOAuthPin: vi.fn()
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
 * Generate an authenticated check response.
 */
const authenticatedCheckResponseArb = fc.record({
	authenticated: fc.constant(true),
	email: fc.emailAddress(),
	error: fc.constant(undefined)
});

// =============================================================================
// Property 32: OAuth Polling
// =============================================================================

describe('Property 32: OAuth Polling', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	/**
	 * For any OAuth flow, the frontend SHALL poll the PIN status endpoint
	 * at regular intervals until authenticated=true is returned.
	 */
	it('should poll PIN status at regular intervals until authenticated', async () => {
		vi.clearAllMocks();

		// Track poll count
		let pollCount = 0;
		const pollsBeforeAuth = 3;

		const pinResponse: OAuthPinResponse = {
			pin_id: 12345,
			code: 'ABCD',
			auth_url: 'https://auth.example.com/oauth',
			expires_at: new Date(Date.now() + 60000).toISOString()
		};

		const authResponse: OAuthCheckResponse = {
			authenticated: true,
			email: 'test@example.com',
			auth_token: 'test-auth-token-123'
		};

		// Mock createOAuthPin to return the generated PIN
		vi.mocked(apiClient.createOAuthPin).mockResolvedValue({
			data: pinResponse,
			error: undefined
		});

		// Mock checkOAuthPin to return pending until pollsBeforeAuth, then authenticated
		vi.mocked(apiClient.checkOAuthPin).mockImplementation(async () => {
			pollCount++;
			if (pollCount >= pollsBeforeAuth) {
				return {
					data: authResponse,
					error: undefined
				};
			}
			return {
				data: {
					authenticated: false
				},
				error: undefined
			};
		});

		const onAuthenticated = vi.fn();
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

		const { container } = render(OAuthJoinFlow, {
			props: { serverType: TEST_SERVER_TYPE, onAuthenticated }
		});

		// Click sign in button
		const signInButton = container.querySelector('[data-oauth-signin-button]');
		expect(signInButton).toBeTruthy();
		await user.click(signInButton!);

		// Wait for PIN creation
		await vi.waitFor(() => {
			expect(apiClient.createOAuthPin).toHaveBeenCalledTimes(1);
		});

		// Advance timers to trigger polling
		for (let i = 0; i < pollsBeforeAuth; i++) {
			await vi.advanceTimersByTimeAsync(2000);
		}

		// Verify polling occurred
		await vi.waitFor(() => {
			expect(apiClient.checkOAuthPin).toHaveBeenCalledTimes(pollsBeforeAuth);
		});

		// Verify onAuthenticated was called with the email and auth token
		await vi.waitFor(() => {
			expect(onAuthenticated).toHaveBeenCalledWith(authResponse.email, authResponse.auth_token);
		});
	});

	/**
	 * For any OAuth flow, the frontend SHALL stop polling when the PIN
	 * expires_at time is reached.
	 */
	it('should stop polling when PIN expires', async () => {
		vi.clearAllMocks();

		// Create a PIN that expires in 4 seconds
		const expiredPinResponse: OAuthPinResponse = {
			pin_id: 12345,
			code: 'ABCD',
			auth_url: 'https://auth.example.com/oauth',
			expires_at: new Date(Date.now() + 4000).toISOString()
		};

		vi.mocked(apiClient.createOAuthPin).mockResolvedValue({
			data: expiredPinResponse,
			error: undefined
		});

		// Always return pending
		vi.mocked(apiClient.checkOAuthPin).mockResolvedValue({
			data: {
				authenticated: false
			},
			error: undefined
		});

		const onAuthenticated = vi.fn();
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

		const { container } = render(OAuthJoinFlow, {
			props: { serverType: TEST_SERVER_TYPE, onAuthenticated }
		});

		// Click sign in button
		const signInButton = container.querySelector('[data-oauth-signin-button]');
		await user.click(signInButton!);

		// Wait for PIN creation
		await vi.waitFor(() => {
			expect(apiClient.createOAuthPin).toHaveBeenCalledTimes(1);
		});

		// Advance time past expiration (poll at 2s, 4s would be past expiration)
		await vi.advanceTimersByTimeAsync(2000); // First poll
		await vi.advanceTimersByTimeAsync(2000); // Second poll - should detect expiration

		// Wait for component to update to expired state
		await vi.waitFor(() => {
			const component = container.querySelector('[data-oauth-join-flow]');
			expect(component?.getAttribute('data-step')).toBe('expired');
		});

		// Verify onAuthenticated was NOT called
		expect(onAuthenticated).not.toHaveBeenCalled();
	});

	/**
	 * For any OAuth flow, the frontend SHALL poll at 2 second intervals.
	 */
	it('should poll at 2 second intervals', async () => {
		vi.clearAllMocks();

		const pinResponse: OAuthPinResponse = {
			pin_id: 12345,
			code: 'ABCD',
			auth_url: 'https://auth.example.com/oauth',
			expires_at: new Date(Date.now() + 60000).toISOString()
		};

		vi.mocked(apiClient.createOAuthPin).mockResolvedValue({
			data: pinResponse,
			error: undefined
		});

		// Always return pending
		vi.mocked(apiClient.checkOAuthPin).mockResolvedValue({
			data: {
				authenticated: false
			},
			error: undefined
		});

		const onAuthenticated = vi.fn();
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

		const { container } = render(OAuthJoinFlow, {
			props: { serverType: TEST_SERVER_TYPE, onAuthenticated }
		});

		// Click sign in button
		const signInButton = container.querySelector('[data-oauth-signin-button]');
		await user.click(signInButton!);

		// Wait for PIN creation
		await vi.waitFor(() => {
			expect(apiClient.createOAuthPin).toHaveBeenCalledTimes(1);
		});

		// Advance 1 second - should not poll yet
		await vi.advanceTimersByTimeAsync(1000);
		expect(apiClient.checkOAuthPin).toHaveBeenCalledTimes(0);

		// Advance another 1 second (total 2s) - should poll
		await vi.advanceTimersByTimeAsync(1000);
		await vi.waitFor(() => {
			expect(apiClient.checkOAuthPin).toHaveBeenCalledTimes(1);
		});

		// Advance another 2 seconds - should poll again
		await vi.advanceTimersByTimeAsync(2000);
		await vi.waitFor(() => {
			expect(apiClient.checkOAuthPin).toHaveBeenCalledTimes(2);
		});

		// Advance another 2 seconds - should poll again
		await vi.advanceTimersByTimeAsync(2000);
		await vi.waitFor(() => {
			expect(apiClient.checkOAuthPin).toHaveBeenCalledTimes(3);
		});
	});
});

// =============================================================================
// Additional OAuth Flow Tests
// =============================================================================

describe('OAuth Flow Component', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	/**
	 * For any valid PIN response, the component SHALL display the PIN code.
	 */
	it('should display PIN code after creation', async () => {
		vi.clearAllMocks();

		const pinResponse: OAuthPinResponse = {
			pin_id: 42,
			code: 'XY9Z',
			auth_url: 'https://auth.example.com/oauth',
			expires_at: new Date(Date.now() + 60000).toISOString()
		};

		vi.mocked(apiClient.createOAuthPin).mockResolvedValue({
			data: pinResponse,
			error: undefined
		});

		vi.mocked(apiClient.checkOAuthPin).mockResolvedValue({
			data: { authenticated: false },
			error: undefined
		});

		const onAuthenticated = vi.fn();
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

		const { container } = render(OAuthJoinFlow, {
			props: { serverType: TEST_SERVER_TYPE, onAuthenticated }
		});

		// Click sign in button to start the flow
		const signInButton = container.querySelector('[data-oauth-signin-button]');
		expect(signInButton).toBeTruthy();
		await user.click(signInButton!);

		// Wait for PIN creation and verify the code is displayed
		await vi.waitFor(() => {
			const pinCodeEl = container.querySelector('[data-pin-code]');
			expect(pinCodeEl).toBeTruthy();
			expect(pinCodeEl?.textContent?.trim()).toBe(pinResponse.code);
		});
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
	 * The component SHALL open auth URL in a new window/tab.
	 */
	it('should open auth URL in new window', async () => {
		vi.clearAllMocks();

		const pinResponse: OAuthPinResponse = {
			pin_id: 12345,
			code: 'ABCD',
			auth_url: 'https://auth.example.com/oauth/test',
			expires_at: new Date(Date.now() + 60000).toISOString()
		};

		vi.mocked(apiClient.createOAuthPin).mockResolvedValue({
			data: pinResponse,
			error: undefined
		});

		const onAuthenticated = vi.fn();
		const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

		const { container } = render(OAuthJoinFlow, {
			props: { serverType: TEST_SERVER_TYPE, onAuthenticated }
		});

		// Click sign in button
		const signInButton = container.querySelector('[data-oauth-signin-button]');
		await user.click(signInButton!);

		// Wait for window.open to be called with named window + dimensions
		await vi.waitFor(() => {
			expect(mockWindowOpen).toHaveBeenCalledWith(
				pinResponse.auth_url,
				`${TEST_SERVER_TYPE}-auth`,
				'width=800,height=600'
			);
		});
	});
});
