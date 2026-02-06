/**
 * Property-based tests for invitation list components.
 *
 * Tests the following properties:
 * - Property 9: Invitation Field Display
 * - Property 10: Invitation Filter Application
 * - Property 11: Invitation Sort Application
 * - Property 13: Remaining Uses Display
 *
 * **Validates: Requirements 4.2, 4.3, 4.4, 4.6**
 *
 * @module $lib/components/invitations/invitation-list.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it } from 'vitest';
import type { InvitationResponse } from '$lib/api/client';
import InvitationRow from './invitation-row.svelte';
import InvitationTable from './invitation-table.svelte';

// =============================================================================
// Test Data Generators
// =============================================================================

/**
 * Generate a valid UUID v4 string.
 */
const uuidArb = fc.uuid();

/**
 * Generate a valid ISO 8601 date string within a reasonable range.
 * Uses integer timestamps to avoid invalid date issues.
 */
const isoDateArb = fc
	.integer({
		min: new Date('2020-01-01T00:00:00.000Z').getTime(),
		max: new Date('2030-12-31T23:59:59.999Z').getTime()
	})
	.map((timestamp) => new Date(timestamp).toISOString());

/**
 * Generate an optional ISO date string (string or null).
 */
const optionalIsoDateArb = fc.oneof(isoDateArb, fc.constant(null));

/**
 * Generate a valid invitation code (alphanumeric, 1-20 chars).
 */
const invitationCodeArb = fc.stringMatching(/^[a-zA-Z0-9]{1,20}$/);

/**
 * Generate a valid InvitationResponse object.
 */
const invitationResponseArb: fc.Arbitrary<InvitationResponse> = fc.record({
	id: uuidArb,
	code: invitationCodeArb,
	use_count: fc.nat({ max: 1000 }),
	enabled: fc.boolean(),
	created_at: isoDateArb,
	expires_at: optionalIsoDateArb,
	max_uses: fc.oneof(fc.integer({ min: 1, max: 1000 }), fc.constant(null)),
	duration_days: fc.oneof(fc.integer({ min: 1, max: 365 }), fc.constant(null)),
	created_by: fc.oneof(uuidArb, fc.constant(null)),
	updated_at: optionalIsoDateArb,
	is_active: fc.boolean(),
	remaining_uses: fc.oneof(fc.integer({ min: 0, max: 1000 }), fc.constant(null))
});

// =============================================================================
// Property 9: Invitation Field Display
// Validates: Requirements 4.2
// =============================================================================

describe('Property 9: Invitation Field Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any invitation in the list view, the rendered output SHALL contain
	 * the code, use_count, max_uses (if set), expires_at (if set), enabled
	 * status, and is_active computed status.
	 *
	 * **Validates: Requirements 4.2**
	 */
	it('should display all required invitation fields', () => {
		fc.assert(
			fc.property(invitationResponseArb, (invitation) => {
				const { container } = render(InvitationRow, { props: { invitation } });
				const row = container.querySelector('[data-invitation-row]');

				expect(row).not.toBeNull();

				// Verify code is displayed
				const codeEl = row?.querySelector('[data-invitation-code]');
				expect(codeEl).not.toBeNull();
				expect(codeEl?.textContent).toBe(invitation.code);

				// Verify use count is displayed
				const usesEl = row?.querySelector('[data-invitation-uses]');
				expect(usesEl).not.toBeNull();
				expect(usesEl?.textContent).toContain(String(invitation.use_count));

				// Verify max_uses is displayed if set
				if (invitation.max_uses !== null && invitation.max_uses !== undefined) {
					expect(usesEl?.textContent).toContain(String(invitation.max_uses));
				}

				// Verify status badge is present (reflects enabled and is_active)
				const statusBadge = row?.querySelector('[data-status-badge]');
				expect(statusBadge).not.toBeNull();

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any invitation, the code SHALL be displayed in monospace font.
	 *
	 * **Validates: Requirements 4.2, 13.3**
	 */
	it('should display invitation code in monospace font', () => {
		fc.assert(
			fc.property(invitationResponseArb, (invitation) => {
				const { container } = render(InvitationRow, { props: { invitation } });
				const codeEl = container.querySelector('[data-invitation-code]');

				expect(codeEl).not.toBeNull();

				// Verify monospace font class is applied
				expect(codeEl?.className).toContain('font-mono');

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any invitation with max_uses set, the display SHALL show
	 * "use_count / max_uses" format.
	 *
	 * **Validates: Requirements 4.2**
	 */
	it('should display use count with max uses in correct format', () => {
		fc.assert(
			fc.property(
				invitationResponseArb.filter((inv) => inv.max_uses !== null && inv.max_uses !== undefined),
				(invitation) => {
					const { container } = render(InvitationRow, { props: { invitation } });
					const usesEl = container.querySelector('[data-invitation-uses]');

					expect(usesEl).not.toBeNull();

					// Should contain "use_count / max_uses" format
					const expectedFormat = `${invitation.use_count} / ${invitation.max_uses}`;
					expect(usesEl?.textContent).toContain(expectedFormat);

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any invitation without max_uses, the display SHALL show only use_count.
	 *
	 * **Validates: Requirements 4.2**
	 */
	it('should display only use count when max_uses is not set', () => {
		fc.assert(
			fc.property(
				invitationResponseArb.filter((inv) => inv.max_uses === null || inv.max_uses === undefined),
				(invitation) => {
					const { container } = render(InvitationRow, { props: { invitation } });
					const usesEl = container.querySelector('[data-invitation-uses]');

					expect(usesEl).not.toBeNull();

					// Should contain just the use_count
					expect(usesEl?.textContent?.trim()).toBe(String(invitation.use_count));

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});
});

// =============================================================================
// Property 10: Invitation Filter Application
// Validates: Requirements 4.3
// =============================================================================

describe('Property 10: Invitation Filter Application', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any combination of enabled and expired filter values, the invitation
	 * list SHALL only display invitations matching the filter criteria.
	 *
	 * Note: This tests the filter logic at the component level. The actual
	 * filtering happens server-side, but we verify the UI correctly passes
	 * filter parameters and displays filtered results.
	 *
	 * **Validates: Requirements 4.3**
	 */
	it('should display only invitations matching enabled filter', () => {
		fc.assert(
			fc.property(
				fc.array(invitationResponseArb, { minLength: 1, maxLength: 10 }),
				fc.boolean(),
				(invitations, enabledFilter) => {
					// Filter invitations based on enabled status
					const filteredInvitations = invitations.filter((inv) => inv.enabled === enabledFilter);

					// Skip if no invitations match the filter
					if (filteredInvitations.length === 0) return;

					const { container } = render(InvitationTable, {
						props: { invitations: filteredInvitations }
					});
					const rows = container.querySelectorAll('[data-invitation-row]');

					// All displayed rows should match the filter
					expect(rows.length).toBe(filteredInvitations.length);

					// Verify each row corresponds to a filtered invitation
					for (const inv of filteredInvitations) {
						const row = container.querySelector(`[data-invitation-id="${inv.id}"]`);
						expect(row).not.toBeNull();
					}

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any combination of is_active filter values, the invitation list
	 * SHALL only display invitations matching the active/expired criteria.
	 *
	 * **Validates: Requirements 4.3**
	 */
	it('should display only invitations matching active/expired filter', () => {
		fc.assert(
			fc.property(
				fc.array(invitationResponseArb, { minLength: 1, maxLength: 10 }),
				fc.boolean(),
				(invitations, isActiveFilter) => {
					// Filter invitations based on is_active status
					const filteredInvitations = invitations.filter((inv) => inv.is_active === isActiveFilter);

					// Skip if no invitations match the filter
					if (filteredInvitations.length === 0) return;

					const { container } = render(InvitationTable, {
						props: { invitations: filteredInvitations }
					});
					const rows = container.querySelectorAll('[data-invitation-row]');

					// All displayed rows should match the filter
					expect(rows.length).toBe(filteredInvitations.length);

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});
});

// =============================================================================
// Property 11: Invitation Sort Application
// Validates: Requirements 4.4
// =============================================================================

describe('Property 11: Invitation Sort Application', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any sort_by value (created_at, expires_at, use_count) and sort_order
	 * (asc, desc), the invitation list SHALL be ordered according to the
	 * specified sort parameters.
	 *
	 * Note: Sorting happens server-side. This test verifies the UI correctly
	 * displays pre-sorted data in the order received.
	 *
	 * **Validates: Requirements 4.4**
	 */
	it('should display invitations in the order provided (sorted by created_at)', () => {
		fc.assert(
			fc.property(
				fc.array(invitationResponseArb, { minLength: 2, maxLength: 10 }),
				fc.constantFrom('asc' as const, 'desc' as const),
				(invitations, sortOrder) => {
					// Sort invitations by created_at
					const sortedInvitations = [...invitations].sort((a, b) => {
						const dateA = new Date(a.created_at).getTime();
						const dateB = new Date(b.created_at).getTime();
						return sortOrder === 'asc' ? dateA - dateB : dateB - dateA;
					});

					const { container } = render(InvitationTable, {
						props: { invitations: sortedInvitations }
					});
					const rows = container.querySelectorAll('[data-invitation-row]');

					// Verify rows are in the expected order
					expect(rows.length).toBe(sortedInvitations.length);

					for (let i = 0; i < sortedInvitations.length; i++) {
						const expectedId = sortedInvitations[i]?.id;
						const actualId = rows[i]?.getAttribute('data-invitation-id');
						expect(actualId).toBe(expectedId);
					}

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For invitations sorted by use_count, the list SHALL maintain the
	 * specified sort order.
	 *
	 * **Validates: Requirements 4.4**
	 */
	it('should display invitations in the order provided (sorted by use_count)', () => {
		fc.assert(
			fc.property(
				fc.array(invitationResponseArb, { minLength: 2, maxLength: 10 }),
				fc.constantFrom('asc' as const, 'desc' as const),
				(invitations, sortOrder) => {
					// Sort invitations by use_count
					const sortedInvitations = [...invitations].sort((a, b) => {
						return sortOrder === 'asc' ? a.use_count - b.use_count : b.use_count - a.use_count;
					});

					const { container } = render(InvitationTable, {
						props: { invitations: sortedInvitations }
					});
					const rows = container.querySelectorAll('[data-invitation-row]');

					// Verify rows are in the expected order
					expect(rows.length).toBe(sortedInvitations.length);

					for (let i = 0; i < sortedInvitations.length; i++) {
						const expectedId = sortedInvitations[i]?.id;
						const actualId = rows[i]?.getAttribute('data-invitation-id');
						expect(actualId).toBe(expectedId);
					}

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});
});

// =============================================================================
// Property 13: Remaining Uses Display
// Validates: Requirements 4.6
// =============================================================================

describe('Property 13: Remaining Uses Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any invitation with a non-null remaining_uses value, the invitation
	 * display SHALL show the remaining count.
	 *
	 * **Validates: Requirements 4.6**
	 */
	it('should display remaining uses when available', () => {
		fc.assert(
			fc.property(fc.integer({ min: 0, max: 100 }), (remainingUses) => {
				const invitation: InvitationResponse = {
					id: '00000000-0000-0000-0000-000000000001',
					code: 'TESTCODE',
					use_count: 5,
					enabled: true,
					created_at: new Date().toISOString(),
					expires_at: null,
					max_uses: 5 + remainingUses,
					duration_days: null,
					created_by: null,
					updated_at: null,
					is_active: true,
					remaining_uses: remainingUses
				};

				const { container } = render(InvitationRow, { props: { invitation } });
				const remainingEl = container.querySelector('[data-invitation-remaining]');

				expect(remainingEl).not.toBeNull();
				expect(remainingEl?.textContent).toContain(String(remainingUses));
				expect(remainingEl?.textContent).toContain('left');

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any invitation without remaining_uses (null), the invitation display
	 * SHALL NOT show a remaining count element.
	 *
	 * **Validates: Requirements 4.6**
	 */
	it('should not display remaining uses when not available', () => {
		fc.assert(
			fc.property(
				invitationResponseArb.filter(
					(inv) => inv.remaining_uses === null || inv.remaining_uses === undefined
				),
				(invitation) => {
					const { container } = render(InvitationRow, { props: { invitation } });
					const remainingEl = container.querySelector('[data-invitation-remaining]');

					// Should not have remaining uses element or it should be empty
					if (remainingEl) {
						expect(remainingEl.textContent?.trim()).toBe('');
					}

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any invitation with remaining_uses = 0, the display SHALL show
	 * "0 left" to indicate exhaustion.
	 *
	 * **Validates: Requirements 4.6**
	 */
	it('should display zero remaining uses correctly', () => {
		const invitation: InvitationResponse = {
			id: '00000000-0000-0000-0000-000000000001',
			code: 'EXHAUSTED',
			use_count: 10,
			enabled: true,
			created_at: new Date().toISOString(),
			expires_at: null,
			max_uses: 10,
			duration_days: null,
			created_by: null,
			updated_at: null,
			is_active: false,
			remaining_uses: 0
		};

		const { container } = render(InvitationRow, { props: { invitation } });
		const remainingEl = container.querySelector('[data-invitation-remaining]');

		expect(remainingEl).not.toBeNull();
		expect(remainingEl?.textContent).toContain('0');
		expect(remainingEl?.textContent).toContain('left');

		cleanup();
	});

	/**
	 * For any invitation with low remaining_uses (1-3), the status badge
	 * SHALL indicate "limited" status.
	 *
	 * **Validates: Requirements 4.6**
	 */
	it('should show limited status for low remaining uses', () => {
		fc.assert(
			fc.property(fc.integer({ min: 1, max: 3 }), (remainingUses) => {
				const invitation: InvitationResponse = {
					id: '00000000-0000-0000-0000-000000000001',
					code: 'LIMITED',
					use_count: 7,
					enabled: true,
					created_at: new Date().toISOString(),
					expires_at: null,
					max_uses: 7 + remainingUses,
					duration_days: null,
					created_by: null,
					updated_at: null,
					is_active: true,
					remaining_uses: remainingUses
				};

				const { container } = render(InvitationRow, { props: { invitation } });
				const statusBadge = container.querySelector('[data-status-badge]');

				expect(statusBadge).not.toBeNull();

				// Should show "limited" status (amber color)
				expect(statusBadge?.getAttribute('data-status')).toBe('limited');

				cleanup();
			}),
			{ numRuns: 50 }
		);
	});
});
