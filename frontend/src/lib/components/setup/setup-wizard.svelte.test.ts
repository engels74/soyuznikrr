import { cleanup, render, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

const { mockGoto } = vi.hoisted(() => ({
	mockGoto: vi.fn()
}));

vi.mock('$app/navigation', () => ({
	goto: mockGoto
}));

vi.mock('$lib/api/auth', async () => {
	const actual = await vi.importActual('$lib/api/auth');
	return {
		...actual,
		setupAdmin: vi.fn(),
		advanceOnboarding: vi.fn()
	};
});

vi.mock('$lib/api/client', async () => {
	const actual = await vi.importActual('$lib/api/client');
	return {
		...actual,
		withErrorHandling: vi.fn(),
		getEnvCredentials: vi.fn(),
		testCsrfOrigin: vi.fn(),
		setCsrfOrigin: vi.fn(),
		testConnection: vi.fn(),
		createServer: vi.fn()
	};
});

import * as authApi from '$lib/api/auth';
import * as apiClient from '$lib/api/client';
import { setProviders } from '$lib/stores/providers.svelte';
import SetupWizard from './setup-wizard.svelte';

function findButton(container: HTMLElement, text: string): HTMLButtonElement | undefined {
	return Array.from(container.querySelectorAll('button')).find((button) =>
		button.textContent?.includes(text)
	) as HTMLButtonElement | undefined;
}

async function submitAdminStep(user: ReturnType<typeof userEvent.setup>, container: HTMLElement) {
	const username = container.querySelector('#setup-username') as HTMLInputElement;
	const password = container.querySelector('#setup-password') as HTMLInputElement;
	const confirmPassword = container.querySelector('#setup-confirm') as HTMLInputElement;

	await user.type(username, 'adminuser');
	await user.type(password, 'this_is_a_secure_password');
	await user.type(confirmPassword, 'this_is_a_secure_password');

	await user.click(findButton(container, 'Create admin account')!);
}

describe('SetupWizard', () => {
	afterEach(() => {
		cleanup();
		vi.resetAllMocks();
	});

	it('shows setup steps in Account -> Security -> Server order', () => {
		const { container } = render(SetupWizard);

		const stepLabels = Array.from(
			container.querySelectorAll('.step-indicator span.text-xs.font-medium.uppercase')
		).map((label) => label.textContent?.trim());

		expect(stepLabels).toEqual(['Account', 'Security', 'Server']);
	});

	it('moves from admin step to the CSRF step after creating an admin', async () => {
		const user = userEvent.setup();
		vi.mocked(authApi.setupAdmin).mockResolvedValue({
			data: { refresh_token: 'token' },
			error: undefined
		});

		const { container } = render(SetupWizard);
		await submitAdminStep(user, container);

		await waitFor(() => {
			expect(container.textContent).toContain('Security Configuration');
		});
	});

	it('navigates to dashboard when server step is skipped after CSRF step', async () => {
		const user = userEvent.setup();
		vi.mocked(authApi.setupAdmin).mockResolvedValue({
			data: { refresh_token: 'token' },
			error: undefined
		});
		vi.mocked(authApi.advanceOnboarding).mockResolvedValue({
			data: {
				onboarding_required: true,
				onboarding_step: 'server'
			},
			error: undefined
		});

		vi.mocked(apiClient.withErrorHandling)
			.mockResolvedValueOnce({
				data: {
					success: true,
					message: 'Origin matches',
					request_origin: 'http://localhost:3000'
				},
				error: undefined
			})
			.mockResolvedValue({
				data: { credentials: [] },
				error: undefined
			});

		const { container } = render(SetupWizard);
		await submitAdminStep(user, container);

		await waitFor(() => {
			expect(container.textContent).toContain('Security Configuration');
		});

		await user.click(findButton(container, 'Test Origin')!);
		await waitFor(() => {
			expect(container.textContent).toContain('Origin matches');
		});

		await user.click(findButton(container, 'Skip for now')!);

		await waitFor(() => {
			expect(container.textContent).toContain('Connect a Media Server');
		});

		await user.click(findButton(container, 'Skip for now')!);
		expect(mockGoto).toHaveBeenCalledWith('/dashboard');
	});

	it('navigates to dashboard without calling advanceOnboarding when server step is completed', async () => {
		// The backend already advances onboarding during server creation
		// (complete_server_step), so the frontend must NOT call the skip endpoint.
		const user = userEvent.setup();

		// Register providers so form validation passes
		setProviders([
			{
				server_type: 'plex',
				display_name: 'Plex',
				color: '#e5a00d',
				icon_svg: ''
			}
		]);

		// Start directly at the server step to isolate the assertion
		vi.mocked(apiClient.withErrorHandling)
			.mockResolvedValueOnce({ data: { credentials: [] }, error: undefined }) // getEnvCredentials
			.mockResolvedValueOnce({
				data: { success: true, server_type: 'plex', server_name: 'My Plex', version: '1.0' },
				error: undefined
			}) // testConnection
			.mockResolvedValueOnce({ data: { id: 'srv-1' }, error: undefined }); // createServer

		const { container } = render(SetupWizard, { props: { initialStep: 'server' } });

		await waitFor(() => {
			expect(container.textContent).toContain('Connect a Media Server');
		});

		// Fill in server name, URL, and API key (canTest requires url + api_key)
		const nameInput = container.querySelector('#server-name') as HTMLInputElement;
		const urlInput = container.querySelector('#server-url') as HTMLInputElement;
		const apiKeyInput = container.querySelector('#server-api-key') as HTMLInputElement;
		await user.type(nameInput, 'Test Server');
		await user.type(urlInput, 'http://localhost:8096');
		await user.type(apiKeyInput, 'test-api-key');
		await user.click(findButton(container, 'Test Connection')!);

		await waitFor(() => {
			expect(container.textContent).toContain('Connected');
		});

		await user.click(findButton(container, 'Add Server & Finish')!);

		await waitFor(() => {
			expect(mockGoto).toHaveBeenCalledWith('/dashboard');
		});

		// The skip/advance endpoint must NOT have been called — backend already advanced
		expect(authApi.advanceOnboarding).not.toHaveBeenCalled();
	});

	it('starts at the security step when initialStep is security', () => {
		const { container } = render(SetupWizard, {
			props: { initialStep: 'security' }
		});

		expect(container.textContent).toContain('Security Configuration');
	});
});
