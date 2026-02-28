/**
 * Property-based tests for loading and error states.
 *
 * Tests the following properties:
 * - Property 35: Loading State Display
 * - Property 36: API Error Toast Display
 *
 * @module $lib/components/loading-error-states.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ErrorState from './error-state.svelte';

// =============================================================================
// Property 35: Loading State Display
// =============================================================================

describe('Property 35: Loading State Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any data fetching operation, the UI SHALL display a skeleton loader
	 * or loading spinner while the request is pending.
	 *
	 * This test verifies that skeleton components have the correct structure
	 * and animation classes for loading indication.
	 */
	it('should display skeleton loaders with animation during loading', async () => {
		// Import skeleton dynamically to test its structure
		const { default: Skeleton } = await import('./ui/skeleton/skeleton.svelte');

		fc.assert(
			fc.property(
				// Generate various class combinations that might be passed to skeleton
				fc.option(fc.constantFrom('h-4', 'h-5', 'h-6', 'h-8', 'w-24', 'w-32', 'w-48'), {
					nil: undefined
				}),
				(additionalClass) => {
					const { container } = render(Skeleton, {
						props: { class: additionalClass }
					});

					const skeleton = container.querySelector('[data-slot="skeleton"]');

					expect(skeleton).not.toBeNull();

					// Verify skeleton has animation class for loading indication
					expect(skeleton?.className).toContain('animate-pulse');

					// Verify skeleton has rounded styling
					expect(skeleton?.className).toContain('rounded-md');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any loading state, skeleton loaders SHALL have consistent styling
	 * that indicates loading is in progress.
	 */
	it('should maintain consistent skeleton styling across renders', async () => {
		const { default: Skeleton } = await import('./ui/skeleton/skeleton.svelte');

		fc.assert(
			fc.property(fc.integer({ min: 2, max: 5 }), (renderCount) => {
				const classNames: string[] = [];

				for (let i = 0; i < renderCount; i++) {
					const { container } = render(Skeleton);
					const skeleton = container.querySelector('[data-slot="skeleton"]');
					classNames.push(skeleton?.className ?? '');
					cleanup();
				}

				// All renders should produce consistent base classes
				for (const className of classNames) {
					// Check that all have the same base classes
					expect(className).toContain('animate-pulse');
					expect(className).toContain('rounded-md');
				}
			}),
			{ numRuns: 20 }
		);
	});

	/**
	 * For any list skeleton, the skeleton SHALL display multiple placeholder
	 * rows to indicate loading content.
	 */
	it('should display multiple skeleton rows in list skeletons', async () => {
		// Test invitation list skeleton
		const { default: InvitationListSkeleton } = await import(
			'./invitations/invitation-list-skeleton.svelte'
		);

		const { container } = render(InvitationListSkeleton);

		// Should have multiple skeleton elements (5 rows as per implementation)
		const skeletons = container.querySelectorAll('[data-slot="skeleton"]');
		expect(skeletons.length).toBeGreaterThan(0);

		// Should have table structure
		const table = container.querySelector('table');
		expect(table).not.toBeNull();

		cleanup();
	});

	/**
	 * For any card-based skeleton, the skeleton SHALL display placeholder
	 * cards with appropriate structure.
	 */
	it('should display skeleton cards in server list skeleton', async () => {
		const { default: ServerListSkeleton } = await import('./servers/server-list-skeleton.svelte');

		const { container } = render(ServerListSkeleton);

		// Should have multiple skeleton elements
		const skeletons = container.querySelectorAll('[data-slot="skeleton"]');
		expect(skeletons.length).toBeGreaterThan(0);

		cleanup();
	});
});

// =============================================================================
// Property 36: API Error Toast Display
// =============================================================================

describe('Property 36: API Error Toast Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any failed API request, the UI SHALL display an error state
	 * with the error message from the response.
	 */
	it('should display error message for any error string', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
				(errorMessage) => {
					const { container } = render(ErrorState, {
						props: { message: errorMessage }
					});

					const errorState = container.querySelector('[data-error-state]');

					expect(errorState).not.toBeNull();

					// Verify the error message is displayed
					const messageEl = errorState?.querySelector('p');
					expect(messageEl).not.toBeNull();
					expect(messageEl?.textContent).toBe(errorMessage);

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any error state, the UI SHALL display a title indicating
	 * something went wrong.
	 */
	it('should display error title for any error', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
				fc.option(
					fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
					{ nil: undefined }
				),
				(errorMessage, customTitle) => {
					const { container } = render(ErrorState, {
						props: {
							message: errorMessage,
							title: customTitle
						}
					});

					const errorState = container.querySelector('[data-error-state]');

					expect(errorState).not.toBeNull();

					// Verify the title is displayed
					const titleEl = errorState?.querySelector('h3');
					expect(titleEl).not.toBeNull();

					// Should show custom title or default
					const expectedTitle = customTitle ?? 'Something went wrong';
					expect(titleEl?.textContent).toBe(expectedTitle);

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any error state with retry callback, the UI SHALL display
	 * a retry button.
	 */
	it('should display retry button when onRetry is provided', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
				(errorMessage) => {
					const mockRetry = vi.fn();
					const { container } = render(ErrorState, {
						props: {
							message: errorMessage,
							onRetry: mockRetry
						}
					});

					const errorState = container.querySelector('[data-error-state]');

					expect(errorState).not.toBeNull();

					// Verify retry button is present
					const retryButton = errorState?.querySelector('button');
					expect(retryButton).not.toBeNull();
					expect(retryButton?.textContent).toContain('Try again');

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any error state without retry callback, the UI SHALL NOT
	 * display a retry button.
	 */
	it('should not display retry button when onRetry is not provided', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
				(errorMessage) => {
					const { container } = render(ErrorState, {
						props: { message: errorMessage }
					});

					const errorState = container.querySelector('[data-error-state]');

					expect(errorState).not.toBeNull();

					// Verify no retry button is present
					const retryButton = errorState?.querySelector('button');
					expect(retryButton).toBeNull();

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any error state, the component SHALL have proper accessibility
	 * attributes including role="alert" and aria-live.
	 */
	it('should have proper accessibility attributes for error states', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
				(errorMessage) => {
					const { container } = render(ErrorState, {
						props: { message: errorMessage }
					});

					const errorState = container.querySelector('[data-error-state]');

					expect(errorState).not.toBeNull();

					// Verify role="alert" is set for screen readers
					expect(errorState?.getAttribute('role')).toBe('alert');

					// Verify aria-live is set for dynamic content
					expect(errorState?.getAttribute('aria-live')).toBe('polite');

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any error state, the component SHALL have consistent error
	 * styling with rose/red color scheme.
	 */
	it('should have consistent error styling', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
				(errorMessage) => {
					const { container } = render(ErrorState, {
						props: { message: errorMessage }
					});

					const errorState = container.querySelector('[data-error-state]');

					expect(errorState).not.toBeNull();

					const classList = errorState?.className ?? '';

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
	 * Error state display should be consistent across multiple renders
	 * with the same props.
	 */
	it('should maintain consistent display across renders', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
				fc.integer({ min: 2, max: 5 }),
				(errorMessage, renderCount) => {
					const htmlOutputs: string[] = [];

					for (let i = 0; i < renderCount; i++) {
						const { container } = render(ErrorState, {
							props: { message: errorMessage }
						});
						const errorState = container.querySelector('[data-error-state]');
						htmlOutputs.push(errorState?.innerHTML ?? '');
						cleanup();
					}

					// All renders should produce the same HTML
					const firstOutput = htmlOutputs[0];
					for (const output of htmlOutputs) {
						expect(output).toBe(firstOutput);
					}
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any error state, the icon container SHALL have rose/red
	 * color styling to indicate error.
	 */
	it('should display error icon with appropriate styling', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
				(errorMessage) => {
					const { container } = render(ErrorState, {
						props: { message: errorMessage }
					});

					const errorState = container.querySelector('[data-error-state]');

					expect(errorState).not.toBeNull();

					// Find the icon container (div with rounded-full class)
					const iconContainer = errorState?.querySelector('div.rounded-full');
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
});
