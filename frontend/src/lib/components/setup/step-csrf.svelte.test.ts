/**
 * Component tests for StepCsrf with API mocking.
 *
 * Tests rendering, validation, and API interaction.
 *
 * @module $lib/components/setup/step-csrf.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('$lib/api/client', async () => {
	const actual = await vi.importActual('$lib/api/client');
	return {
		...actual,
		setCsrfOrigin: vi.fn(),
		withErrorHandling: vi.fn()
	};
});

import * as apiClient from '$lib/api/client';
import StepCsrf from './step-csrf.svelte';

afterEach(() => {
	cleanup();
	vi.clearAllMocks();
});

describe('Step CSRF Component', () => {
	it('should render security configuration card', () => {
		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		expect(container.textContent).toContain('Security Configuration');
		expect(container.textContent).toContain('CSRF protection');
		expect(container.querySelector('input[type="url"]')).toBeTruthy();
	});

	it('should auto-populate origin with window.location.origin', () => {
		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		const input = container.querySelector('input[type="url"]') as HTMLInputElement;
		expect(input).toBeTruthy();
		expect(input.value).toBe(window.location.origin);
	});

	it('should render Skip and Save buttons', () => {
		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		const buttons = container.querySelectorAll('button');
		const buttonTexts = Array.from(buttons).map((b) => b.textContent?.trim());
		expect(buttonTexts.some((t) => t?.includes('Skip'))).toBe(true);
		expect(buttonTexts.some((t) => t?.includes('Save'))).toBe(true);
	});

	it('should call onSkip when Skip clicked', async () => {
		const onSkip = vi.fn();
		const user = userEvent.setup();
		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip }
		});

		const skipButton = Array.from(container.querySelectorAll('button')).find((b) =>
			b.textContent?.includes('Skip')
		);
		expect(skipButton).toBeTruthy();
		await user.click(skipButton!);

		expect(onSkip).toHaveBeenCalledTimes(1);
	});

	it('should show validation error for empty origin', async () => {
		const user = userEvent.setup();
		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		// Clear the auto-populated input
		const input = container.querySelector('input[type="url"]') as HTMLInputElement;
		await user.clear(input);

		// Submit the form
		const submitButton = Array.from(container.querySelectorAll('button')).find((b) =>
			b.textContent?.includes('Save')
		);
		await user.click(submitButton!);

		// Should show a validation error (Zod chain may show "Origin is required" or "Must be a valid URL")
		const errorText = container.querySelector('.text-red-400');
		expect(errorText).toBeTruthy();
	});

	it('should show validation error for trailing slash', async () => {
		const user = userEvent.setup();
		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		const input = container.querySelector('input[type="url"]') as HTMLInputElement;
		await user.clear(input);
		await user.type(input, 'https://example.com/');

		const submitButton = Array.from(container.querySelectorAll('button')).find((b) =>
			b.textContent?.includes('Save')
		);
		await user.click(submitButton!);

		expect(container.textContent).toContain('Remove trailing slash');
	});

	it('should call API and onComplete on success', async () => {
		const onComplete = vi.fn();
		const user = userEvent.setup();

		vi.mocked(apiClient.withErrorHandling).mockResolvedValue({
			data: { csrf_origin: 'https://app.example.com', is_locked: false },
			error: undefined
		});

		const { container } = render(StepCsrf, {
			props: { onComplete, onSkip: vi.fn() }
		});

		// Input is auto-populated with window.location.origin (http://localhost:3000)
		const submitButton = Array.from(container.querySelectorAll('button')).find((b) =>
			b.textContent?.includes('Save')
		);
		await user.click(submitButton!);

		// withErrorHandling should have been called
		expect(apiClient.withErrorHandling).toHaveBeenCalledTimes(1);

		// onComplete should have been called
		expect(onComplete).toHaveBeenCalledTimes(1);
	});

	it('should display server error on API failure', async () => {
		const user = userEvent.setup();

		vi.mocked(apiClient.withErrorHandling).mockResolvedValue({
			data: undefined,
			error: { detail: 'Server unavailable', error_code: 'INTERNAL_ERROR' }
		});

		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		const submitButton = Array.from(container.querySelectorAll('button')).find((b) =>
			b.textContent?.includes('Save')
		);
		await user.click(submitButton!);

		// Should display server error
		expect(container.textContent).toContain('Server unavailable');
	});

	it('should display CSRF info callout', () => {
		const { container } = render(StepCsrf, {
			props: { onComplete: vi.fn(), onSkip: vi.fn() }
		});

		expect(container.textContent).toContain(
			'CSRF protection prevents unauthorized requests from other websites'
		);
	});
});
