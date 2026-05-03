/**
 * Tests for StatCard component layout safeguards.
 *
 * Asserts the flex container and inner text wrapper have the min-w-0 / gap-3
 * classes that prevent the dashboard from overflowing horizontally on narrow
 * viewports (see ISSUE-003 in the dogfood report).
 *
 * @module $lib/components/dashboard/stat-card.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import StatCardTestHarness from './stat-card-test-harness.svelte';

afterEach(() => {
	cleanup();
});

describe('StatCard', () => {
	it('should apply min-w-0 and gap-3 to the inner flex row', () => {
		const { container } = render(StatCardTestHarness, {
			props: {
				title: 'Active Users',
				value: 42,
				subtitle: 'last 7 days'
			}
		});

		const flexRow = container.querySelector('div.flex.items-start.justify-between');
		expect(flexRow).not.toBeNull();
		expect(flexRow?.classList.contains('min-w-0')).toBe(true);
		expect(flexRow?.classList.contains('gap-3')).toBe(true);
	});

	it('should apply min-w-0 to the title/value text wrapper', () => {
		const { container } = render(StatCardTestHarness, {
			props: {
				title: 'Active Users',
				value: 42
			}
		});

		// The text wrapper is the first child of the flex row, with space-y-1.
		const textWrapper = container.querySelector('div.space-y-1');
		expect(textWrapper).not.toBeNull();
		expect(textWrapper?.classList.contains('min-w-0')).toBe(true);
	});
});
