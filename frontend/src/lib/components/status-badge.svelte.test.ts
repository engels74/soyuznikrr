/**
 * Property-based tests for StatusBadge component.
 *
 * Tests the following property:
 * - Property 12: Status Badge Color Mapping
 *
 * @module $lib/components/status-badge.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it } from 'vitest';
import StatusBadge from './status-badge.svelte';

// =============================================================================
// Property 12: Status Badge Color Mapping
// =============================================================================

describe('Property 12: Status Badge Color Mapping', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any status value (active/enabled → green, pending/limited → amber,
	 * disabled/expired → red), the StatusBadge component SHALL apply the
	 * correct color class.
	 */
	it('should apply correct color class for any status value', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					fc.constant('active' as const),
					fc.constant('enabled' as const),
					fc.constant('pending' as const),
					fc.constant('limited' as const),
					fc.constant('disabled' as const),
					fc.constant('expired' as const)
				),
				(status) => {
					const { container } = render(StatusBadge, { props: { status } });
					const badge = container.querySelector('[data-status-badge]');

					expect(badge).not.toBeNull();

					// Verify the data-status attribute is set correctly
					expect(badge?.getAttribute('data-status')).toBe(status);

					// Check for the correct color classes based on status
					// The component uses tailwind-variants which generates classes like:
					// - Green (active/enabled): bg-emerald-500/15, text-emerald-400, border-emerald-500/30
					// - Amber (pending/limited): bg-amber-500/15, text-amber-400, border-amber-500/30
					// - Red (disabled/expired): bg-rose-500/15, text-rose-400, border-rose-500/30

					const classList = badge?.className ?? '';

					if (status === 'active' || status === 'enabled') {
						// Green status colors
						expect(classList).toContain('text-emerald-400');
						expect(classList).toContain('border-emerald-500/30');
					} else if (status === 'pending' || status === 'limited') {
						// Amber status colors
						expect(classList).toContain('text-amber-400');
						expect(classList).toContain('border-amber-500/30');
					} else {
						// Red status colors (disabled/expired)
						expect(classList).toContain('text-rose-400');
						expect(classList).toContain('border-rose-500/30');
					}

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any green status (active/enabled), the StatusBadge SHALL display
	 * emerald/green color styling.
	 */
	it('should apply green color for active/enabled statuses', () => {
		fc.assert(
			fc.property(fc.constantFrom('active' as const, 'enabled' as const), (status) => {
				const { container } = render(StatusBadge, { props: { status } });
				const badge = container.querySelector('[data-status-badge]');
				const dot = badge?.querySelector('span.rounded-full');

				expect(badge).not.toBeNull();

				// Verify badge has emerald text color
				expect(badge?.className).toContain('text-emerald-400');

				// Verify the status indicator dot has emerald background
				expect(dot?.className).toContain('bg-emerald-400');

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any amber status (pending/limited), the StatusBadge SHALL display
	 * amber color styling.
	 */
	it('should apply amber color for pending/limited statuses', () => {
		fc.assert(
			fc.property(fc.constantFrom('pending' as const, 'limited' as const), (status) => {
				const { container } = render(StatusBadge, { props: { status } });
				const badge = container.querySelector('[data-status-badge]');
				const dot = badge?.querySelector('span.rounded-full');

				expect(badge).not.toBeNull();

				// Verify badge has amber text color
				expect(badge?.className).toContain('text-amber-400');

				// Verify the status indicator dot has amber background
				expect(dot?.className).toContain('bg-amber-400');

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any red status (disabled/expired), the StatusBadge SHALL display
	 * rose/red color styling.
	 */
	it('should apply red color for disabled/expired statuses', () => {
		fc.assert(
			fc.property(fc.constantFrom('disabled' as const, 'expired' as const), (status) => {
				const { container } = render(StatusBadge, { props: { status } });
				const badge = container.querySelector('[data-status-badge]');
				const dot = badge?.querySelector('span.rounded-full');

				expect(badge).not.toBeNull();

				// Verify badge has rose text color
				expect(badge?.className).toContain('text-rose-400');

				// Verify the status indicator dot has rose background
				expect(dot?.className).toContain('bg-rose-400');

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any status value, the StatusBadge SHALL display the correct label
	 * (capitalized status name by default).
	 */
	it('should display capitalized status label by default', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					fc.constant('active' as const),
					fc.constant('enabled' as const),
					fc.constant('pending' as const),
					fc.constant('limited' as const),
					fc.constant('disabled' as const),
					fc.constant('expired' as const)
				),
				(status) => {
					const { container } = render(StatusBadge, { props: { status } });
					const badge = container.querySelector('[data-status-badge]');

					expect(badge).not.toBeNull();

					// Expected label is capitalized status
					const expectedLabel = status.charAt(0).toUpperCase() + status.slice(1);
					expect(badge?.textContent?.trim()).toContain(expectedLabel);

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any status value with a custom label, the StatusBadge SHALL display
	 * the custom label instead of the default.
	 */
	it('should display custom label when provided', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					fc.constant('active' as const),
					fc.constant('enabled' as const),
					fc.constant('pending' as const),
					fc.constant('limited' as const),
					fc.constant('disabled' as const),
					fc.constant('expired' as const)
				),
				// Generate alphanumeric labels to avoid whitespace edge cases
				fc.stringMatching(/^[a-zA-Z][a-zA-Z0-9 ]{0,48}[a-zA-Z0-9]$|^[a-zA-Z]$/),
				(status, customLabel) => {
					const { container } = render(StatusBadge, {
						props: { status, label: customLabel }
					});
					const badge = container.querySelector('[data-status-badge]');

					expect(badge).not.toBeNull();

					// Should display custom label (trimmed comparison)
					expect(badge?.textContent?.trim()).toContain(customLabel.trim());

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any status value, the StatusBadge SHALL include a status indicator dot
	 * with a glow effect matching the status color.
	 */
	it('should include status indicator dot with glow effect', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					fc.constant('active' as const),
					fc.constant('enabled' as const),
					fc.constant('pending' as const),
					fc.constant('limited' as const),
					fc.constant('disabled' as const),
					fc.constant('expired' as const)
				),
				(status) => {
					const { container } = render(StatusBadge, { props: { status } });
					const badge = container.querySelector('[data-status-badge]');
					const dot = badge?.querySelector('span.rounded-full');

					expect(badge).not.toBeNull();
					expect(dot).not.toBeNull();

					// Verify dot has size classes
					expect(dot?.className).toContain('size-1.5');

					// Verify dot has shadow/glow effect
					expect(dot?.className).toContain('shadow-');

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * StatusBadge color mapping should be consistent across multiple renders.
	 */
	it('should maintain consistent color mapping across renders', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					fc.constant('active' as const),
					fc.constant('enabled' as const),
					fc.constant('pending' as const),
					fc.constant('limited' as const),
					fc.constant('disabled' as const),
					fc.constant('expired' as const)
				),
				fc.integer({ min: 2, max: 5 }),
				(status, renderCount) => {
					const classNames: string[] = [];

					for (let i = 0; i < renderCount; i++) {
						const { container } = render(StatusBadge, { props: { status } });
						const badge = container.querySelector('[data-status-badge]');
						classNames.push(badge?.className ?? '');
						cleanup();
					}

					// All renders should produce the same class names
					const firstClassName = classNames[0];
					for (const className of classNames) {
						expect(className).toBe(firstClassName);
					}
				}
			),
			{ numRuns: 50 }
		);
	});
});
