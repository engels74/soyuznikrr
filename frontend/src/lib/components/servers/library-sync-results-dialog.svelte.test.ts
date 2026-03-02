/**
 * Tests for LibrarySyncResultsDialog component.
 *
 * @module $lib/components/servers/library-sync-results-dialog.svelte.test
 */

import { cleanup, render, waitFor } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { LibrarySyncResult } from '$lib/api/client';
import LibrarySyncResultsDialog from './library-sync-results-dialog.svelte';

const isoDateArb = fc
	.integer({ min: 1577836800000, max: 1924905600000 })
	.map((ts) => new Date(ts).toISOString());

const librarySyncResultArb: fc.Arbitrary<LibrarySyncResult> = fc.record({
	server_id: fc.uuid(),
	server_name: fc.string({ minLength: 1, maxLength: 64 }).filter((s) => s.trim().length > 0),
	synced_at: isoDateArb,
	total_libraries: fc.nat({ max: 500 }),
	added_count: fc.nat({ max: 100 }),
	updated_count: fc.nat({ max: 100 }),
	removed_count: fc.nat({ max: 100 })
});

describe('LibrarySyncResultsDialog', () => {
	afterEach(() => {
		cleanup();
	});

	it('renders all summary counts with correct values', async () => {
		await fc.assert(
			fc.asyncProperty(librarySyncResultArb, async (result) => {
				const onClose = vi.fn();
				render(LibrarySyncResultsDialog, {
					props: { open: true, result, onClose }
				});

				await waitFor(() => {
					const dialog = document.querySelector('[role="dialog"]');
					expect(dialog).not.toBeNull();
				});

				const totalEl = document.querySelector('[data-library-sync-total]');
				const addedEl = document.querySelector('[data-library-sync-added]');
				const updatedEl = document.querySelector('[data-library-sync-updated]');
				const removedEl = document.querySelector('[data-library-sync-removed]');

				expect(totalEl).not.toBeNull();
				expect(addedEl).not.toBeNull();
				expect(updatedEl).not.toBeNull();
				expect(removedEl).not.toBeNull();

				expect(totalEl!.textContent).toContain(String(result.total_libraries));
				expect(addedEl!.textContent).toContain(String(result.added_count));
				expect(updatedEl!.textContent).toContain(String(result.updated_count));
				expect(removedEl!.textContent).toContain(String(result.removed_count));

				cleanup();
			}),
			{ numRuns: 30 }
		);
	});
});
