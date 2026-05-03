/**
 * Tests for the InvitationRow status badge logic.
 *
 * Verifies that "Used up" (max_uses exhausted, client-derivable) is
 * distinguished from the generic "Inactive" branch (server's is_active=false,
 * cause unknown to the client), addressing dogfood ISSUE-004.
 *
 * @module $lib/components/invitations/invitation-row.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import type { InvitationResponse } from '$lib/api/client';
import InvitationRow from './invitation-row.svelte';

afterEach(() => {
	cleanup();
});

const HOUR = 60 * 60 * 1000;

function makeInvitation(overrides: Partial<InvitationResponse> = {}): InvitationResponse {
	return {
		id: '00000000-0000-0000-0000-000000000001',
		code: 'TESTCODE',
		use_count: 0,
		enabled: true,
		created_at: new Date(Date.now() - 24 * HOUR).toISOString(),
		expires_at: new Date(Date.now() + 24 * HOUR).toISOString(),
		max_uses: null,
		duration_days: null,
		created_by: null,
		updated_at: null,
		is_active: true,
		remaining_uses: null,
		...overrides
	};
}

function getStatusInfo(invitation: InvitationResponse): {
	status: string | null;
	label: string;
} {
	const { container } = render(InvitationRow, { props: { invitation } });
	const badge = container.querySelector('[data-status-badge]');
	return {
		status: badge?.getAttribute('data-status') ?? null,
		label: badge?.textContent?.trim() ?? ''
	};
}

describe('InvitationRow status badge', () => {
	it('should label disabled invitations "Disabled"', () => {
		const inv = makeInvitation({ enabled: false, is_active: false });
		const info = getStatusInfo(inv);
		expect(info.status).toBe('disabled');
		expect(info.label).toContain('Disabled');
	});

	it('should label a fully-used max_uses=1 invitation "Used up" (not "Expired")', () => {
		// max_uses reached but expiry is still in the future — distinguishes the
		// reason for non-redeemability from a date-based expiry.
		const inv = makeInvitation({
			max_uses: 1,
			use_count: 1,
			remaining_uses: 0,
			is_active: false,
			expires_at: new Date(Date.now() + 24 * HOUR).toISOString()
		});
		const info = getStatusInfo(inv);
		expect(info.status).toBe('expired');
		expect(info.label).toContain('Used up');
		expect(info.label).not.toContain('Expired');
	});

	it('should label a server-inactive invitation "Inactive"', () => {
		// The server's is_active boolean is the source of truth for whether an
		// invitation is redeemable. The UI does not guess the cause (e.g.
		// date-expiry vs. other server-side reasons) because the response only
		// exposes the boolean, not a reason field. Use "Used up" only when
		// max_uses is exhausted (a client-derivable signal).
		const inv = makeInvitation({
			max_uses: null,
			use_count: 5,
			remaining_uses: null,
			is_active: false,
			expires_at: new Date(Date.now() - 24 * HOUR).toISOString()
		});
		const info = getStatusInfo(inv);
		expect(info.status).toBe('expired');
		expect(info.label).toContain('Inactive');
		expect(info.label).not.toContain('Used up');
	});

	it('should label a healthy invitation "Active"', () => {
		const inv = makeInvitation({
			max_uses: 10,
			use_count: 1,
			remaining_uses: 9,
			is_active: true,
			expires_at: new Date(Date.now() + 30 * 24 * HOUR).toISOString()
		});
		const info = getStatusInfo(inv);
		expect(info.status).toBe('active');
		expect(info.label).toContain('Active');
	});

	it('should label an invitation with few remaining uses "Limited"', () => {
		const inv = makeInvitation({
			max_uses: 10,
			use_count: 8,
			remaining_uses: 2,
			is_active: true,
			expires_at: new Date(Date.now() + 24 * HOUR).toISOString()
		});
		const info = getStatusInfo(inv);
		expect(info.status).toBe('limited');
		expect(info.label).toContain('Limited');
	});

	it('should keep an unlimited invitation "Active" regardless of use_count', () => {
		// remaining_uses=null means no max_uses → never "Used up".
		const inv = makeInvitation({
			max_uses: null,
			use_count: 100,
			remaining_uses: null,
			is_active: true,
			expires_at: new Date(Date.now() + 30 * 24 * HOUR).toISOString()
		});
		const info = getStatusInfo(inv);
		expect(info.status).toBe('active');
		expect(info.label).toContain('Active');
	});
});
