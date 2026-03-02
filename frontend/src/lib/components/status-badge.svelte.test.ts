/**
 * Tests for StatusBadge component.
 *
 * Tests that the correct status is rendered with the right label and data attribute.
 *
 * @module $lib/components/status-badge.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it } from 'vitest';
import StatusBadge from './status-badge.svelte';

const allStatuses = fc.oneof(
	fc.constant('active' as const),
	fc.constant('enabled' as const),
	fc.constant('pending' as const),
	fc.constant('limited' as const),
	fc.constant('disabled' as const),
	fc.constant('expired' as const)
);

describe('StatusBadge', () => {
	afterEach(() => {
		cleanup();
	});

	it('should render with correct data-status attribute for any status', () => {
		fc.assert(
			fc.property(allStatuses, (status) => {
				const { container } = render(StatusBadge, { props: { status } });
				const badge = container.querySelector('[data-status-badge]');

				expect(badge).not.toBeNull();
				expect(badge?.getAttribute('data-status')).toBe(status);

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	it('should display capitalized status label by default', () => {
		fc.assert(
			fc.property(allStatuses, (status) => {
				const { container } = render(StatusBadge, { props: { status } });
				const badge = container.querySelector('[data-status-badge]');

				expect(badge).not.toBeNull();

				const expectedLabel = status.charAt(0).toUpperCase() + status.slice(1);
				expect(badge?.textContent?.trim()).toContain(expectedLabel);

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	it('should display custom label when provided', () => {
		fc.assert(
			fc.property(
				allStatuses,
				fc.stringMatching(/^[a-zA-Z][a-zA-Z0-9 ]{0,48}[a-zA-Z0-9]$|^[a-zA-Z]$/),
				(status, customLabel) => {
					const { container } = render(StatusBadge, {
						props: { status, label: customLabel }
					});
					const badge = container.querySelector('[data-status-badge]');

					expect(badge).not.toBeNull();
					expect(badge?.textContent?.trim()).toContain(customLabel.trim());

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	it('should include a status indicator dot', () => {
		fc.assert(
			fc.property(allStatuses, (status) => {
				const { container } = render(StatusBadge, { props: { status } });
				const badge = container.querySelector('[data-status-badge]');
				const dot = badge?.querySelector('span');

				expect(badge).not.toBeNull();
				expect(dot).not.toBeNull();

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});
});
