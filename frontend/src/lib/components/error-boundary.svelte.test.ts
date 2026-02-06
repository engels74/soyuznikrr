/**
 * Property-based tests for error boundary component.
 *
 * Tests the following properties:
 * - Property 11: Error Boundary Containment
 * - Property 12: Error Message Safety
 *
 * **Validates: Requirements 5.4, 5.5**
 *
 * @module $lib/components/error-boundary.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import * as fc from 'fast-check';
import { tick } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ErrorBoundaryWrapper from './error-boundary-test-wrapper.svelte';

// =============================================================================
// Property 11: Error Boundary Containment
// Validates: Requirements 5.4
// =============================================================================

describe('Property 11: Error Boundary Containment', () => {
	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	/**
	 * For any error boundary in its initial state (no error), the boundary
	 * SHALL render its children content normally.
	 *
	 * **Validates: Requirements 5.4**
	 */
	it('should render children when no error has occurred', () => {
		fc.assert(
			fc.property(fc.integer({ min: 1, max: 100 }), (renderCount) => {
				for (let i = 0; i < Math.min(renderCount, 5); i++) {
					const { container } = render(ErrorBoundaryWrapper);

					// Error boundary should not show error state initially
					const errorAlert = container.querySelector('[role="alert"]');
					expect(errorAlert).toBeNull();

					// Children should be rendered
					const testContent = container.querySelector('[data-testid="test-content"]');
					expect(testContent).not.toBeNull();
					expect(testContent?.textContent).toBe('Test Content');

					cleanup();
				}
			}),
			{ numRuns: 20 }
		);
	});

	/**
	 * For any error caught by the error boundary, the boundary SHALL
	 * display a fallback UI instead of crashing the application.
	 *
	 * **Validates: Requirements 5.4**
	 */
	it('should display fallback UI when error is set via handleError', async () => {
		await fc.assert(
			fc.asyncProperty(
				fc.string({ minLength: 1, maxLength: 200 }).filter((s) => s.trim().length > 0),
				async (errorMessage) => {
					const { container, component } = render(ErrorBoundaryWrapper);

					// Simulate an error being caught
					const error = new Error(errorMessage);
					component.triggerError(error);
					await tick();

					// Should display error UI
					const errorAlert = container.querySelector('[role="alert"]');
					expect(errorAlert).not.toBeNull();

					// Should have "Try again" button
					const retryButton = container.querySelector('button');
					expect(retryButton).not.toBeNull();
					expect(retryButton?.textContent).toContain('Try again');

					// Children should NOT be rendered when error is shown
					const testContent = container.querySelector('[data-testid="test-content"]');
					expect(testContent).toBeNull();

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any error boundary showing an error, clicking the reset button
	 * SHALL clear the error state and re-render children.
	 *
	 * **Validates: Requirements 5.4**
	 */
	it('should reset error state when reset button is clicked', async () => {
		const user = userEvent.setup();

		const { container, component } = render(ErrorBoundaryWrapper);

		// Set an error
		component.triggerError(new Error('Test error'));
		await tick();

		// Verify error state is shown
		let errorAlert = container.querySelector('[role="alert"]');
		expect(errorAlert).not.toBeNull();

		// Children should not be visible
		let testContent = container.querySelector('[data-testid="test-content"]');
		expect(testContent).toBeNull();

		// Click reset button
		const resetButton = container.querySelector('button');
		expect(resetButton).not.toBeNull();
		await user.click(resetButton!);

		// Error state should be cleared
		errorAlert = container.querySelector('[role="alert"]');
		expect(errorAlert).toBeNull();

		// Children should be visible again
		testContent = container.querySelector('[data-testid="test-content"]');
		expect(testContent).not.toBeNull();
	});

	/**
	 * For any error boundary, the error state SHALL have proper accessibility
	 * attributes including role="alert" and aria-live.
	 *
	 * **Validates: Requirements 5.4**
	 */
	it('should have proper accessibility attributes when showing error', async () => {
		await fc.assert(
			fc.asyncProperty(
				fc.string({ minLength: 1, maxLength: 200 }).filter((s) => s.trim().length > 0),
				async (errorMessage) => {
					const { container, component } = render(ErrorBoundaryWrapper);

					component.triggerError(new Error(errorMessage));
					await tick();

					const errorAlert = container.querySelector('[role="alert"]');
					expect(errorAlert).not.toBeNull();
					expect(errorAlert?.getAttribute('role')).toBe('alert');
					expect(errorAlert?.getAttribute('aria-live')).toBe('polite');

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any error boundary, the error UI SHALL have consistent styling
	 * with rose/red color scheme to indicate error state.
	 *
	 * **Validates: Requirements 5.4**
	 */
	it('should have consistent error styling', async () => {
		await fc.assert(
			fc.asyncProperty(
				fc.string({ minLength: 1, maxLength: 200 }).filter((s) => s.trim().length > 0),
				async (errorMessage) => {
					const { container, component } = render(ErrorBoundaryWrapper);

					component.triggerError(new Error(errorMessage));
					await tick();

					const errorAlert = container.querySelector('[role="alert"]');
					expect(errorAlert).not.toBeNull();

					const classList = errorAlert?.className ?? '';

					// Verify error styling with rose color scheme
					expect(classList).toContain('border-rose-500/30');
					expect(classList).toContain('bg-rose-500/5');

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any error boundary, the error icon SHALL be displayed with
	 * appropriate rose/red styling.
	 *
	 * **Validates: Requirements 5.4**
	 */
	it('should display error icon with appropriate styling', async () => {
		await fc.assert(
			fc.asyncProperty(
				fc.string({ minLength: 1, maxLength: 200 }).filter((s) => s.trim().length > 0),
				async (errorMessage) => {
					const { container, component } = render(ErrorBoundaryWrapper);

					component.triggerError(new Error(errorMessage));
					await tick();

					const errorAlert = container.querySelector('[role="alert"]');
					expect(errorAlert).not.toBeNull();

					// Find the icon container
					const iconContainer = errorAlert?.querySelector('div.rounded-full');
					expect(iconContainer).not.toBeNull();

					// Verify icon container has rose color styling
					expect(iconContainer?.className).toContain('bg-rose-500/15');
					expect(iconContainer?.className).toContain('text-rose-400');

					// Verify SVG icon is present
					const svg = iconContainer?.querySelector('svg');
					expect(svg).not.toBeNull();

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any error boundary, the error message displayed SHALL be a
	 * generic user-friendly message, not the raw error message.
	 *
	 * **Validates: Requirements 5.4, 5.5**
	 */
	it('should display generic error message regardless of actual error', async () => {
		await fc.assert(
			fc.asyncProperty(fc.string({ minLength: 1, maxLength: 500 }), async (errorMessage) => {
				const { container, component } = render(ErrorBoundaryWrapper);

				component.triggerError(new Error(errorMessage));
				await tick();

				const errorAlert = container.querySelector('[role="alert"]');
				expect(errorAlert).not.toBeNull();

				// Should show generic message, not the actual error
				const heading = errorAlert?.querySelector('h3');
				expect(heading?.textContent).toBe('Something went wrong');

				const description = errorAlert?.querySelector('p');
				expect(description?.textContent).toBe('An unexpected error occurred. Please try again.');

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any error boundary, errors SHALL be logged to console for debugging
	 * while showing safe UI to users.
	 *
	 * **Validates: Requirements 5.4**
	 */
	it('should log errors to console for debugging', async () => {
		const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

		await fc.assert(
			fc.asyncProperty(
				fc.string({ minLength: 1, maxLength: 200 }).filter((s) => s.trim().length > 0),
				async (errorMessage) => {
					consoleSpy.mockClear();

					const { component } = render(ErrorBoundaryWrapper);
					const error = new Error(errorMessage);

					component.triggerError(error);
					await tick();

					// Should log the error for debugging
					expect(consoleSpy).toHaveBeenCalledWith('Error boundary caught:', error);

					cleanup();
				}
			),
			{ numRuns: 100 }
		);

		consoleSpy.mockRestore();
	});
});

// =============================================================================
// Property 12: Error Message Safety
// Validates: Requirements 5.5
// =============================================================================

describe('Property 12: Error Message Safety', () => {
	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	// Generator for unsafe error messages containing internal details
	const unsafeErrorArb = fc.oneof(
		fc.constant('Error at functionName (file.ts:10:5)'),
		fc.constant('    at Object.handler (/src/api/handler.ts:42:15)'),
		fc.constant('TypeError: Cannot read property of undefined\n    at processRequest'),
		fc.constant('File "/backend/src/main.py", line 42, in handler'),
		fc.constant('Traceback (most recent call last):'),
		fc.constant('INTERNAL_ERROR: Database connection failed'),
		fc.constant('DATABASE_ERROR: SQL syntax error near SELECT'),
		fc.constant('/node_modules/express/lib/router.js:123:45'),
		fc.constant('Error: TypeError: at Object.handler'),
		fc.constant('SELECT * FROM users WHERE id = 1; DROP TABLE users;--')
	);

	/**
	 * For any error containing stack traces, file paths, or internal details,
	 * the error boundary SHALL NOT expose these details to users.
	 *
	 * **Validates: Requirements 5.5**
	 */
	it('should not expose stack traces in error UI', async () => {
		await fc.assert(
			fc.asyncProperty(unsafeErrorArb, async (unsafeMessage) => {
				const { container, component } = render(ErrorBoundaryWrapper);

				component.triggerError(new Error(unsafeMessage));
				await tick();

				const errorAlert = container.querySelector('[role="alert"]');
				expect(errorAlert).not.toBeNull();

				// Get all text content from the error UI
				const textContent = errorAlert?.textContent ?? '';

				// Should NOT contain any unsafe patterns
				expect(textContent).not.toContain('.ts:');
				expect(textContent).not.toContain('.js:');
				expect(textContent).not.toContain('.py:');
				expect(textContent).not.toContain('/src/');
				expect(textContent).not.toContain('/backend/');
				expect(textContent).not.toContain('/node_modules/');
				expect(textContent).not.toContain('Traceback');
				expect(textContent).not.toContain('INTERNAL_ERROR');
				expect(textContent).not.toContain('DATABASE_ERROR');
				expect(textContent).not.toContain('SQL');
				expect(textContent).not.toContain('at Object.');
				expect(textContent).not.toContain('at function');

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any error containing file paths, the error boundary SHALL NOT
	 * expose file system structure to users.
	 *
	 * **Validates: Requirements 5.5**
	 */
	it('should not expose file paths in error UI', async () => {
		const filePathErrors = [
			'/home/user/project/src/api/handler.ts',
			'C:\\Users\\dev\\project\\src\\main.js',
			'./src/components/Button.svelte',
			'../../../backend/src/main.py',
			'/var/www/app/node_modules/express/index.js'
		];

		for (const filePath of filePathErrors) {
			const { container, component } = render(ErrorBoundaryWrapper);

			component.triggerError(new Error(`Error in ${filePath}`));
			await tick();

			const errorAlert = container.querySelector('[role="alert"]');
			const textContent = errorAlert?.textContent ?? '';

			// Should NOT contain file paths
			expect(textContent).not.toContain(filePath);
			expect(textContent).not.toContain('/src/');
			expect(textContent).not.toContain('\\src\\');

			cleanup();
		}
	});

	/**
	 * For any error containing SQL queries, the error boundary SHALL NOT
	 * expose database structure to users.
	 *
	 * **Validates: Requirements 5.5**
	 */
	it('should not expose SQL queries in error UI', async () => {
		const sqlErrors = [
			'SELECT * FROM users WHERE id = 1',
			'INSERT INTO sessions VALUES (1, "token")',
			'UPDATE users SET password = "hash" WHERE id = 1',
			'DELETE FROM invitations WHERE expired = true',
			'SQL syntax error near SELECT'
		];

		for (const sqlError of sqlErrors) {
			const { container, component } = render(ErrorBoundaryWrapper);

			component.triggerError(new Error(sqlError));
			await tick();

			const errorAlert = container.querySelector('[role="alert"]');
			const textContent = errorAlert?.textContent ?? '';

			// Should NOT contain SQL keywords
			expect(textContent).not.toContain('SELECT');
			expect(textContent).not.toContain('INSERT');
			expect(textContent).not.toContain('UPDATE');
			expect(textContent).not.toContain('DELETE');
			expect(textContent).not.toContain('FROM');
			expect(textContent).not.toContain('WHERE');

			cleanup();
		}
	});

	/**
	 * For any error, the error boundary SHALL only display a generic,
	 * user-friendly message that does not reveal implementation details.
	 *
	 * **Validates: Requirements 5.5**
	 */
	it('should always display generic user-friendly message', async () => {
		await fc.assert(
			fc.asyncProperty(
				// Use longer strings that won't naturally appear in the generic message
				fc
					.string({ minLength: 10, maxLength: 200 })
					.filter((s) => {
						const trimmed = s.trim();
						// Filter out strings that could naturally appear in the generic message
						return (
							trimmed.length >= 10 &&
							!trimmed.includes('Something went wrong') &&
							!trimmed.includes('unexpected error') &&
							!trimmed.includes('Please try again') &&
							!trimmed.includes('Try again')
						);
					}),
				async (errorMessage) => {
					const { container, component } = render(ErrorBoundaryWrapper);

					component.triggerError(new Error(errorMessage));
					await tick();

					const errorAlert = container.querySelector('[role="alert"]');
					expect(errorAlert).not.toBeNull();

					// Should show generic title
					const heading = errorAlert?.querySelector('h3');
					expect(heading?.textContent).toBe('Something went wrong');

					// Should show generic description
					const description = errorAlert?.querySelector('p');
					expect(description?.textContent).toBe('An unexpected error occurred. Please try again.');

					// The actual error message should NOT appear in the UI
					const textContent = errorAlert?.textContent ?? '';
					expect(textContent).not.toContain(errorMessage);

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});
});
