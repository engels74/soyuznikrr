/**
 * Property-based tests for user list components.
 *
 * Tests the following properties:
 * - Property 17: User Field Display
 * - Property 18: User Filter Application
 * - Property 19: User Sort Application
 * - Property 20: User Invitation Code Display
 *
 * @module $lib/components/users/user-list.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it } from 'vitest';
import type {
	IdentityResponse,
	InvitationResponse,
	MediaServerResponse,
	UserDetailResponse
} from '$lib/api/client';
import UserRow from './user-row.svelte';
import UserTable from './user-table.svelte';

// =============================================================================
// Test Data Generators
// =============================================================================

/**
 * Generate a valid UUID v4 string.
 */
const uuidArb = fc.uuid();

/**
 * Generate a valid ISO 8601 date string within a reasonable range.
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
 * Generate a valid username (lowercase, starts with letter).
 */
const usernameArb = fc.stringMatching(/^[a-z][a-z0-9_]{2,31}$/);

/**
 * Generate a valid invitation code (alphanumeric, 1-20 chars).
 */
const invitationCodeArb = fc.stringMatching(/^[a-zA-Z0-9]{1,20}$/);

/**
 * Generate a valid server type.
 */
const serverTypeArb = fc.constantFrom('jellyfin' as const, 'plex' as const);

/**
 * Generate a valid MediaServerResponse object.
 */
const mediaServerResponseArb: fc.Arbitrary<MediaServerResponse> = fc.record({
	id: uuidArb,
	name: fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0),
	server_type: serverTypeArb,
	url: fc.webUrl(),
	enabled: fc.boolean(),
	created_at: isoDateArb,
	updated_at: optionalIsoDateArb
});

/**
 * Generate a valid IdentityResponse object.
 */
const identityResponseArb: fc.Arbitrary<IdentityResponse> = fc.record({
	id: uuidArb,
	display_name: fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0),
	enabled: fc.boolean(),
	created_at: isoDateArb,
	email: fc.oneof(fc.emailAddress(), fc.constant(null)),
	expires_at: optionalIsoDateArb,
	updated_at: optionalIsoDateArb
});

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

/**
 * Generate a valid UserDetailResponse object.
 */
const userDetailResponseArb: fc.Arbitrary<UserDetailResponse> = fc
	.record({
		id: uuidArb,
		identity_id: uuidArb,
		media_server_id: uuidArb,
		external_user_id: fc.string({ minLength: 1, maxLength: 50 }),
		username: usernameArb,
		enabled: fc.boolean(),
		created_at: isoDateArb,
		identity: identityResponseArb,
		media_server: mediaServerResponseArb,
		expires_at: optionalIsoDateArb,
		updated_at: optionalIsoDateArb,
		invitation_id: fc.oneof(uuidArb, fc.constant(null)),
		invitation: fc.oneof(invitationResponseArb, fc.constant(null))
	})
	.map((user) => ({
		...user,
		// Ensure invitation_id and invitation are consistent
		invitation_id: user.invitation ? user.invitation.id : null
	}));

/**
 * Generate a user with a specific invitation.
 */
const userWithInvitationArb = fc
	.record({
		user: userDetailResponseArb,
		invitation: invitationResponseArb
	})
	.map(({ user, invitation }) => ({
		...user,
		invitation_id: invitation.id,
		invitation
	}));

/**
 * Generate a user without an invitation.
 */
const userWithoutInvitationArb = userDetailResponseArb.map((user) => ({
	...user,
	invitation_id: null,
	invitation: null
}));

// =============================================================================
// Property 17: User Field Display
// =============================================================================

describe('Property 17: User Field Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any user in the list view, the rendered output SHALL contain
	 * username, media_server name, enabled status, expires_at (if set),
	 * and created_at.
	 */
	it('should display all required user fields', () => {
		fc.assert(
			fc.property(userDetailResponseArb, (user) => {
				const { container } = render(UserRow, { props: { user } });
				const row = container.querySelector('[data-user-row]');

				expect(row).not.toBeNull();

				// Verify username is displayed
				const usernameEl = row?.querySelector('[data-user-username]');
				expect(usernameEl).not.toBeNull();
				expect(usernameEl?.textContent).toBe(user.username);

				// Verify server name is displayed
				const serverEl = row?.querySelector('[data-user-server]');
				expect(serverEl).not.toBeNull();
				expect(serverEl?.textContent).toContain(user.media_server.name);

				// Verify status badge is present (reflects enabled status)
				const statusBadge = row?.querySelector('[data-status-badge]');
				expect(statusBadge).not.toBeNull();

				// Verify created_at is displayed
				const createdEl = row?.querySelector('[data-user-created]');
				expect(createdEl).not.toBeNull();

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any user, the server type badge SHALL be displayed with the provider label.
	 */
	it('should display server type badge with correct styling', () => {
		fc.assert(
			fc.property(userDetailResponseArb, (user) => {
				const { container } = render(UserRow, { props: { user } });
				const row = container.querySelector('[data-user-row]');

				expect(row).not.toBeNull();

				// Find the server type badge (contains 'plex' or 'jellyfin')
				const serverTypeText = user.media_server.server_type;
				const badges = row?.querySelectorAll('span') ?? [];
				let foundBadge = false;

				for (const badge of badges) {
					if (badge.textContent?.toLowerCase().includes(serverTypeText)) {
						foundBadge = true;
						break;
					}
				}

				expect(foundBadge).toBe(true);

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any disabled user, the status badge SHALL show "Disabled" status.
	 */
	it('should show disabled status for disabled users', () => {
		fc.assert(
			fc.property(
				userDetailResponseArb.map((user) => ({ ...user, enabled: false })),
				(user) => {
					const { container } = render(UserRow, { props: { user } });
					const statusBadge = container.querySelector('[data-status-badge]');

					expect(statusBadge).not.toBeNull();
					expect(statusBadge?.getAttribute('data-status')).toBe('disabled');

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any enabled user without expiration, the status badge SHALL show
	 * "Active" status.
	 */
	it('should show active status for enabled users without expiration', () => {
		fc.assert(
			fc.property(
				userDetailResponseArb.map((user) => ({
					...user,
					enabled: true,
					expires_at: null
				})),
				(user) => {
					const { container } = render(UserRow, { props: { user } });
					const statusBadge = container.querySelector('[data-status-badge]');

					expect(statusBadge).not.toBeNull();
					expect(statusBadge?.getAttribute('data-status')).toBe('active');

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});
});

// =============================================================================
// Property 18: User Filter Application
// =============================================================================

describe('Property 18: User Filter Application', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any combination of server_id, invitation_id, enabled, and expired
	 * filter values, the user list SHALL only display users matching all
	 * specified filter criteria.
	 *
	 * Note: This tests the filter logic at the component level. The actual
	 * filtering happens server-side, but we verify the UI correctly displays
	 * filtered results.
	 */
	it('should display only users matching enabled filter', () => {
		fc.assert(
			fc.property(
				fc.array(userDetailResponseArb, { minLength: 1, maxLength: 10 }),
				fc.boolean(),
				(users, enabledFilter) => {
					// Filter users based on enabled status
					const filteredUsers = users.filter((user) => user.enabled === enabledFilter);

					// Skip if no users match the filter
					if (filteredUsers.length === 0) return;

					const { container } = render(UserTable, {
						props: { users: filteredUsers }
					});
					const rows = container.querySelectorAll('[data-user-row]');

					// All displayed rows should match the filter
					expect(rows.length).toBe(filteredUsers.length);

					// Verify each row corresponds to a filtered user
					for (const user of filteredUsers) {
						const row = container.querySelector(`[data-user-id="${user.id}"]`);
						expect(row).not.toBeNull();
					}

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any server_id filter, the user list SHALL only display users
	 * from that server.
	 */
	it('should display only users matching server_id filter', () => {
		fc.assert(
			fc.property(fc.array(userDetailResponseArb, { minLength: 2, maxLength: 10 }), (users) => {
				// Pick a random server_id from the users
				const targetServerId = users[0]?.media_server_id;
				if (!targetServerId) return;

				// Filter users by server_id
				const filteredUsers = users.filter((user) => user.media_server_id === targetServerId);

				// Skip if no users match
				if (filteredUsers.length === 0) return;

				const { container } = render(UserTable, {
					props: { users: filteredUsers }
				});
				const rows = container.querySelectorAll('[data-user-row]');

				// All displayed rows should be from the target server
				expect(rows.length).toBe(filteredUsers.length);

				cleanup();
			}),
			{ numRuns: 50 }
		);
	});
});

// =============================================================================
// Property 19: User Sort Application
// =============================================================================

describe('Property 19: User Sort Application', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any sort_by value (created_at, username, expires_at) and sort_order
	 * (asc, desc), the user list SHALL be ordered according to the specified
	 * sort parameters.
	 *
	 * Note: Sorting happens server-side. This test verifies the UI correctly
	 * displays pre-sorted data in the order received.
	 */
	it('should display users in the order provided (sorted by created_at)', () => {
		fc.assert(
			fc.property(
				fc.array(userDetailResponseArb, { minLength: 2, maxLength: 10 }),
				fc.constantFrom('asc' as const, 'desc' as const),
				(users, sortOrder) => {
					// Sort users by created_at
					const sortedUsers = [...users].sort((a, b) => {
						const dateA = new Date(a.created_at).getTime();
						const dateB = new Date(b.created_at).getTime();
						return sortOrder === 'asc' ? dateA - dateB : dateB - dateA;
					});

					const { container } = render(UserTable, {
						props: { users: sortedUsers }
					});
					const rows = container.querySelectorAll('[data-user-row]');

					// Verify rows are in the expected order
					expect(rows.length).toBe(sortedUsers.length);

					for (let i = 0; i < sortedUsers.length; i++) {
						const expectedId = sortedUsers[i]?.id;
						const actualId = rows[i]?.getAttribute('data-user-id');
						expect(actualId).toBe(expectedId);
					}

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For users sorted by username, the list SHALL maintain the specified
	 * sort order.
	 */
	it('should display users in the order provided (sorted by username)', () => {
		fc.assert(
			fc.property(
				fc.array(userDetailResponseArb, { minLength: 2, maxLength: 10 }),
				fc.constantFrom('asc' as const, 'desc' as const),
				(users, sortOrder) => {
					// Sort users by username
					const sortedUsers = [...users].sort((a, b) => {
						const comparison = a.username.localeCompare(b.username);
						return sortOrder === 'asc' ? comparison : -comparison;
					});

					const { container } = render(UserTable, {
						props: { users: sortedUsers }
					});
					const rows = container.querySelectorAll('[data-user-row]');

					// Verify rows are in the expected order
					expect(rows.length).toBe(sortedUsers.length);

					for (let i = 0; i < sortedUsers.length; i++) {
						const expectedId = sortedUsers[i]?.id;
						const actualId = rows[i]?.getAttribute('data-user-id');
						expect(actualId).toBe(expectedId);
					}

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	}, 15_000);
});

// =============================================================================
// Property 20: User Invitation Code Display
// =============================================================================

describe('Property 20: User Invitation Code Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any user with a non-null invitation relationship, the user display
	 * SHALL show the source invitation code.
	 */
	it('should display invitation code when user has invitation', () => {
		fc.assert(
			fc.property(userWithInvitationArb, (user) => {
				const { container } = render(UserRow, { props: { user } });
				const invitationEl = container.querySelector('[data-user-invitation]');

				expect(invitationEl).not.toBeNull();
				expect(invitationEl?.textContent).toBe(user.invitation?.code);

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any user without an invitation relationship, the user display
	 * SHALL NOT show an invitation code (or show a placeholder).
	 */
	it('should not display invitation code when user has no invitation', () => {
		fc.assert(
			fc.property(userWithoutInvitationArb, (user) => {
				const { container } = render(UserRow, { props: { user } });
				const invitationEl = container.querySelector('[data-user-invitation]');

				// Should not have invitation element
				expect(invitationEl).toBeNull();

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any user with an invitation, the invitation code SHALL be displayed
	 * in monospace font.
	 */
	it('should display invitation code in monospace font', () => {
		fc.assert(
			fc.property(userWithInvitationArb, (user) => {
				const { container } = render(UserRow, { props: { user } });
				const invitationEl = container.querySelector('[data-user-invitation]');

				expect(invitationEl).not.toBeNull();

				// Verify monospace font class is applied
				expect(invitationEl?.className).toContain('font-mono');

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any user with an invitation, the invitation code display SHALL be
	 * consistent across multiple renders.
	 */
	it('should maintain consistent invitation code display across renders', () => {
		fc.assert(
			fc.property(userWithInvitationArb, fc.integer({ min: 2, max: 5 }), (user, renderCount) => {
				const invitationCodes: string[] = [];

				for (let i = 0; i < renderCount; i++) {
					const { container } = render(UserRow, { props: { user } });
					const invitationEl = container.querySelector('[data-user-invitation]');
					invitationCodes.push(invitationEl?.textContent ?? '');
					cleanup();
				}

				// All renders should produce the same invitation code
				const firstCode = invitationCodes[0];
				for (const code of invitationCodes) {
					expect(code).toBe(firstCode);
				}
			}),
			{ numRuns: 50 }
		);
	});
});
