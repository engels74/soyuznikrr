/**
 * Property-based tests for SyncResultsDialog component.
 *
 * Tests the following property:
 * - Property 26: Sync Result Display
 *
 * **Validates: Requirements 9.6**
 *
 * @module $lib/components/servers/sync-results-dialog.svelte.test
 */

import { cleanup, render, waitFor } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { SyncResult } from '$lib/api/client';
import SyncResultsDialog from './sync-results-dialog.svelte';

// =============================================================================
// Arbitraries for generating test data
// =============================================================================

/**
 * Arbitrary for generating valid ISO date strings.
 */
const isoDateArb = fc
	.integer({ min: 1577836800000, max: 1924905600000 }) // 2020-01-01 to 2030-12-31 in ms
	.map((ts) => new Date(ts).toISOString());

/**
 * Arbitrary for generating valid usernames (unique within array).
 */
const usernameArb = fc
	.string({ minLength: 1, maxLength: 32 })
	.filter((s) => s.trim().length > 0 && /^[a-zA-Z0-9_]+$/.test(s));

/**
 * Arbitrary for generating unique username arrays.
 */
const uniqueUsernamesArb = fc
	.array(usernameArb, { minLength: 0, maxLength: 10 })
	.map((arr) => [...new Set(arr)]);

/**
 * Arbitrary for generating valid sync results.
 */
const syncResultArb: fc.Arbitrary<SyncResult> = fc.record({
	server_id: fc.uuid(),
	server_name: fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0),
	synced_at: isoDateArb,
	orphaned_users: uniqueUsernamesArb,
	stale_users: uniqueUsernamesArb,
	matched_users: fc.nat({ max: 1000 })
});

// =============================================================================
// Property 26: Sync Result Display
// Validates: Requirements 9.6
// =============================================================================

describe('Property 26: Sync Result Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any sync result, the rendered output SHALL contain orphaned_users array,
	 * stale_users array, and matched_users count.
	 *
	 * **Validates: Requirements 9.6**
	 */
	it('should display all sync result fields', async () => {
		await fc.assert(
			fc.asyncProperty(syncResultArb, async (result) => {
				const mockOnClose = vi.fn();
				render(SyncResultsDialog, {
					props: { open: true, result, onClose: mockOnClose }
				});

				// Wait for dialog to render (it uses a portal)
				await waitFor(() => {
					const dialog = document.querySelector('[role="dialog"]');
					expect(dialog).not.toBeNull();
				});

				// Verify matched users section is displayed
				const matchedSection = document.querySelector('[data-sync-matched]');
				expect(matchedSection).not.toBeNull();

				// Verify matched users count is displayed
				const matchedCount = matchedSection?.querySelector('[data-field="matched_users"]');
				expect(matchedCount).not.toBeNull();
				expect(matchedCount?.textContent?.trim()).toBe(String(result.matched_users));

				// Verify orphaned users section is displayed
				const orphanedSection = document.querySelector('[data-sync-orphaned]');
				expect(orphanedSection).not.toBeNull();

				// Verify stale users section is displayed
				const staleSection = document.querySelector('[data-sync-stale]');
				expect(staleSection).not.toBeNull();

				cleanup();
			}),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any sync result with orphaned users, the orphaned users list SHALL
	 * display all usernames.
	 *
	 * **Validates: Requirements 9.6**
	 */
	it('should display all orphaned usernames when present', async () => {
		await fc.assert(
			fc.asyncProperty(
				syncResultArb.filter((r) => r.orphaned_users.length > 0),
				async (result) => {
					const mockOnClose = vi.fn();
					render(SyncResultsDialog, {
						props: { open: true, result, onClose: mockOnClose }
					});

					await waitFor(() => {
						const dialog = document.querySelector('[role="dialog"]');
						expect(dialog).not.toBeNull();
					});

					const orphanedSection = document.querySelector('[data-sync-orphaned]');
					expect(orphanedSection).not.toBeNull();

					const orphanedList = orphanedSection?.querySelector('[data-field="orphaned_users"]');
					expect(orphanedList).not.toBeNull();

					// Verify each orphaned username is displayed
					for (const username of result.orphaned_users) {
						expect(orphanedList?.textContent).toContain(username);
					}

					cleanup();
				}
			),
			{ numRuns: 30 }
		);
	});

	/**
	 * For any sync result with stale users, the stale users list SHALL
	 * display all usernames.
	 *
	 * **Validates: Requirements 9.6**
	 */
	it('should display all stale usernames when present', async () => {
		await fc.assert(
			fc.asyncProperty(
				syncResultArb.filter((r) => r.stale_users.length > 0),
				async (result) => {
					const mockOnClose = vi.fn();
					render(SyncResultsDialog, {
						props: { open: true, result, onClose: mockOnClose }
					});

					await waitFor(() => {
						const dialog = document.querySelector('[role="dialog"]');
						expect(dialog).not.toBeNull();
					});

					const staleSection = document.querySelector('[data-sync-stale]');
					expect(staleSection).not.toBeNull();

					const staleList = staleSection?.querySelector('[data-field="stale_users"]');
					expect(staleList).not.toBeNull();

					// Verify each stale username is displayed
					for (const username of result.stale_users) {
						expect(staleList?.textContent).toContain(username);
					}

					cleanup();
				}
			),
			{ numRuns: 30 }
		);
	});

	/**
	 * For any sync result with no orphaned users, the orphaned users list
	 * SHALL NOT be displayed.
	 *
	 * **Validates: Requirements 9.6**
	 */
	it('should not display orphaned users list when empty', async () => {
		await fc.assert(
			fc.asyncProperty(
				syncResultArb.map((r) => ({ ...r, orphaned_users: [] })),
				async (result) => {
					const mockOnClose = vi.fn();
					render(SyncResultsDialog, {
						props: { open: true, result, onClose: mockOnClose }
					});

					await waitFor(() => {
						const dialog = document.querySelector('[role="dialog"]');
						expect(dialog).not.toBeNull();
					});

					const orphanedSection = document.querySelector('[data-sync-orphaned]');
					expect(orphanedSection).not.toBeNull();

					// The list element should not be present when empty
					const orphanedList = orphanedSection?.querySelector('[data-field="orphaned_users"]');
					expect(orphanedList).toBeNull();

					cleanup();
				}
			),
			{ numRuns: 30 }
		);
	});

	/**
	 * For any sync result with no stale users, the stale users list
	 * SHALL NOT be displayed.
	 *
	 * **Validates: Requirements 9.6**
	 */
	it('should not display stale users list when empty', async () => {
		await fc.assert(
			fc.asyncProperty(
				syncResultArb.map((r) => ({ ...r, stale_users: [] })),
				async (result) => {
					const mockOnClose = vi.fn();
					render(SyncResultsDialog, {
						props: { open: true, result, onClose: mockOnClose }
					});

					await waitFor(() => {
						const dialog = document.querySelector('[role="dialog"]');
						expect(dialog).not.toBeNull();
					});

					const staleSection = document.querySelector('[data-sync-stale]');
					expect(staleSection).not.toBeNull();

					// The list element should not be present when empty
					const staleList = staleSection?.querySelector('[data-field="stale_users"]');
					expect(staleList).toBeNull();

					cleanup();
				}
			),
			{ numRuns: 30 }
		);
	});

	/**
	 * For any sync result with discrepancies (orphaned or stale users),
	 * the dialog SHALL display a warning indicator.
	 *
	 * **Validates: Requirements 9.6**
	 */
	it('should display warning indicator when discrepancies exist', async () => {
		await fc.assert(
			fc.asyncProperty(
				syncResultArb.filter((r) => r.orphaned_users.length > 0 || r.stale_users.length > 0),
				async (result) => {
					const mockOnClose = vi.fn();
					render(SyncResultsDialog, {
						props: { open: true, result, onClose: mockOnClose }
					});

					await waitFor(() => {
						const dialog = document.querySelector('[role="dialog"]');
						expect(dialog).not.toBeNull();
					});

					// The dialog title should contain "Discrepancies Found"
					const dialogContent = document.querySelector('[role="dialog"]')?.textContent ?? '';
					expect(dialogContent).toContain('Discrepancies Found');

					cleanup();
				}
			),
			{ numRuns: 30 }
		);
	});

	/**
	 * For any sync result with no discrepancies (no orphaned or stale users),
	 * the dialog SHALL display a success indicator.
	 *
	 * **Validates: Requirements 9.6**
	 */
	it('should display success indicator when no discrepancies', async () => {
		await fc.assert(
			fc.asyncProperty(
				syncResultArb.map((r) => ({
					...r,
					orphaned_users: [],
					stale_users: []
				})),
				async (result) => {
					const mockOnClose = vi.fn();
					render(SyncResultsDialog, {
						props: { open: true, result, onClose: mockOnClose }
					});

					await waitFor(() => {
						const dialog = document.querySelector('[role="dialog"]');
						expect(dialog).not.toBeNull();
					});

					// The dialog title should contain "All Matched"
					const dialogContent = document.querySelector('[role="dialog"]')?.textContent ?? '';
					expect(dialogContent).toContain('All Matched');

					cleanup();
				}
			),
			{ numRuns: 30 }
		);
	});

	/**
	 * For any sync result, the matched users section SHALL have emerald/green styling.
	 *
	 * **Validates: Requirements 9.6**
	 */
	it('should display matched users with green styling', async () => {
		await fc.assert(
			fc.asyncProperty(syncResultArb, async (result) => {
				const mockOnClose = vi.fn();
				render(SyncResultsDialog, {
					props: { open: true, result, onClose: mockOnClose }
				});

				await waitFor(() => {
					const dialog = document.querySelector('[role="dialog"]');
					expect(dialog).not.toBeNull();
				});

				const matchedSection = document.querySelector('[data-sync-matched]');
				expect(matchedSection).not.toBeNull();

				// Verify green/emerald styling
				expect(matchedSection?.className).toContain('border-emerald-500/30');
				expect(matchedSection?.className).toContain('bg-emerald-500/5');

				cleanup();
			}),
			{ numRuns: 30 }
		);
	});

	/**
	 * For any sync result, the orphaned users section SHALL have amber styling.
	 *
	 * **Validates: Requirements 9.6**
	 */
	it('should display orphaned users with amber styling', async () => {
		await fc.assert(
			fc.asyncProperty(syncResultArb, async (result) => {
				const mockOnClose = vi.fn();
				render(SyncResultsDialog, {
					props: { open: true, result, onClose: mockOnClose }
				});

				await waitFor(() => {
					const dialog = document.querySelector('[role="dialog"]');
					expect(dialog).not.toBeNull();
				});

				const orphanedSection = document.querySelector('[data-sync-orphaned]');
				expect(orphanedSection).not.toBeNull();

				// Verify amber styling
				expect(orphanedSection?.className).toContain('border-amber-500/30');
				expect(orphanedSection?.className).toContain('bg-amber-500/5');

				cleanup();
			}),
			{ numRuns: 30 }
		);
	});

	/**
	 * For any sync result, the stale users section SHALL have rose/red styling.
	 *
	 * **Validates: Requirements 9.6**
	 */
	it('should display stale users with red styling', async () => {
		await fc.assert(
			fc.asyncProperty(syncResultArb, async (result) => {
				const mockOnClose = vi.fn();
				render(SyncResultsDialog, {
					props: { open: true, result, onClose: mockOnClose }
				});

				await waitFor(() => {
					const dialog = document.querySelector('[role="dialog"]');
					expect(dialog).not.toBeNull();
				});

				const staleSection = document.querySelector('[data-sync-stale]');
				expect(staleSection).not.toBeNull();

				// Verify rose/red styling
				expect(staleSection?.className).toContain('border-rose-500/30');
				expect(staleSection?.className).toContain('bg-rose-500/5');

				cleanup();
			}),
			{ numRuns: 30 }
		);
	});
});
