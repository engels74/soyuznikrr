/**
 * Property-based tests for ServerCard component.
 *
 * Tests the following property:
 * - Property 25: Server Field Display
 *
 * **Validates: Requirements 9.2**
 *
 * @module $lib/components/servers/server-card.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { MediaServerWithLibrariesResponse } from '$lib/api/client';
import ServerCard from './server-card.svelte';

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
 * Arbitrary for generating valid library responses.
 */
const libraryResponseArb = fc.record({
	id: fc.uuid(),
	name: fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0),
	library_type: fc.constantFrom('movies', 'tvshows', 'music', 'photos'),
	external_id: fc.string({ minLength: 1, maxLength: 20 }),
	created_at: isoDateArb,
	updated_at: fc.option(isoDateArb, { nil: null })
});

/**
 * Arbitrary for generating valid server responses.
 */
const serverResponseArb: fc.Arbitrary<MediaServerWithLibrariesResponse> = fc.record({
	id: fc.uuid(),
	name: fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0),
	server_type: fc.constantFrom('jellyfin' as const, 'plex' as const),
	url: fc.webUrl(),
	enabled: fc.boolean(),
	created_at: isoDateArb,
	updated_at: fc.option(isoDateArb, { nil: null }),
	libraries: fc.array(libraryResponseArb, { minLength: 0, maxLength: 10 })
});

// =============================================================================
// Property 25: Server Field Display
// Validates: Requirements 9.2
// =============================================================================

describe('Property 25: Server Field Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any server in the list view, the rendered output SHALL contain
	 * name, server_type, url, enabled status, and library count.
	 *
	 * **Validates: Requirements 9.2**
	 */
	it('should display all required server fields', () => {
		fc.assert(
			fc.property(serverResponseArb, (server) => {
				const mockOnViewDetails = vi.fn();
				const { container } = render(ServerCard, {
					props: { server, onViewDetails: mockOnViewDetails }
				});

				const card = container.querySelector('[data-server-card]');
				expect(card).not.toBeNull();

				// Verify server ID is set as data attribute
				expect(card?.getAttribute('data-server-id')).toBe(server.id);

				// Verify name is displayed
				const nameField = card?.querySelector('[data-field="name"]');
				expect(nameField).not.toBeNull();
				expect(nameField?.textContent).toBe(server.name);

				// Verify server_type is displayed
				const typeField = card?.querySelector('[data-field="server_type"]');
				expect(typeField).not.toBeNull();
				const expectedType = server.server_type === 'plex' ? 'Plex' : 'Jellyfin';
				expect(typeField?.textContent).toBe(expectedType);

				// Verify URL is displayed
				const urlField = card?.querySelector('[data-field="url"]');
				expect(urlField).not.toBeNull();
				expect(urlField?.textContent).toBe(server.url);

				// Verify enabled status is displayed
				const enabledField = card?.querySelector('[data-field="enabled"]');
				expect(enabledField).not.toBeNull();
				// The status badge should be inside the enabled field wrapper
				const statusBadge = enabledField?.querySelector('[data-status-badge]');
				expect(statusBadge).not.toBeNull();

				// Verify library count is displayed
				const libraryCountField = card?.querySelector('[data-field="library_count"]');
				expect(libraryCountField).not.toBeNull();
				const expectedCount =
					server.libraries.length === 1 ? '1 library' : `${server.libraries.length} libraries`;
				expect(libraryCountField?.textContent).toBe(expectedCount);

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any server with enabled=true, the status badge SHALL show 'active' status.
	 *
	 * **Validates: Requirements 9.2**
	 */
	it('should display active status for enabled servers', () => {
		fc.assert(
			fc.property(
				serverResponseArb.map((s) => ({ ...s, enabled: true })),
				(server) => {
					const mockOnViewDetails = vi.fn();
					const { container } = render(ServerCard, {
						props: { server, onViewDetails: mockOnViewDetails }
					});

					const card = container.querySelector('[data-server-card]');
					const statusBadge = card?.querySelector('[data-status-badge]');

					expect(statusBadge).not.toBeNull();
					expect(statusBadge?.getAttribute('data-status')).toBe('active');
					expect(statusBadge?.textContent?.trim()).toContain('Enabled');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any server with enabled=false, the status badge SHALL show 'disabled' status.
	 *
	 * **Validates: Requirements 9.2**
	 */
	it('should display disabled status for disabled servers', () => {
		fc.assert(
			fc.property(
				serverResponseArb.map((s) => ({ ...s, enabled: false })),
				(server) => {
					const mockOnViewDetails = vi.fn();
					const { container } = render(ServerCard, {
						props: { server, onViewDetails: mockOnViewDetails }
					});

					const card = container.querySelector('[data-server-card]');
					const statusBadge = card?.querySelector('[data-status-badge]');

					expect(statusBadge).not.toBeNull();
					expect(statusBadge?.getAttribute('data-status')).toBe('disabled');
					expect(statusBadge?.textContent?.trim()).toContain('Disabled');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any Plex server, the type badge SHALL have amber styling.
	 *
	 * **Validates: Requirements 9.2**
	 */
	it('should display amber styling for Plex servers', () => {
		fc.assert(
			fc.property(
				serverResponseArb.map((s) => ({ ...s, server_type: 'plex' as const })),
				(server) => {
					const mockOnViewDetails = vi.fn();
					const { container } = render(ServerCard, {
						props: { server, onViewDetails: mockOnViewDetails }
					});

					const card = container.querySelector('[data-server-card]');
					const typeField = card?.querySelector('[data-field="server_type"]');

					expect(typeField).not.toBeNull();
					expect(typeField?.className).toContain('text-amber-400');
					expect(typeField?.className).toContain('border-amber-500/30');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any Jellyfin server, the type badge SHALL have purple styling.
	 *
	 * **Validates: Requirements 9.2**
	 */
	it('should display purple styling for Jellyfin servers', () => {
		fc.assert(
			fc.property(
				serverResponseArb.map((s) => ({
					...s,
					server_type: 'jellyfin' as const
				})),
				(server) => {
					const mockOnViewDetails = vi.fn();
					const { container } = render(ServerCard, {
						props: { server, onViewDetails: mockOnViewDetails }
					});

					const card = container.querySelector('[data-server-card]');
					const typeField = card?.querySelector('[data-field="server_type"]');

					expect(typeField).not.toBeNull();
					expect(typeField?.className).toContain('text-purple-400');
					expect(typeField?.className).toContain('border-purple-500/30');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any server with zero libraries, the library count SHALL display "0 libraries".
	 *
	 * **Validates: Requirements 9.2**
	 */
	it('should display correct count for servers with no libraries', () => {
		fc.assert(
			fc.property(
				serverResponseArb.map((s) => ({ ...s, libraries: [] })),
				(server) => {
					const mockOnViewDetails = vi.fn();
					const { container } = render(ServerCard, {
						props: { server, onViewDetails: mockOnViewDetails }
					});

					const card = container.querySelector('[data-server-card]');
					const libraryCountField = card?.querySelector('[data-field="library_count"]');

					expect(libraryCountField).not.toBeNull();
					expect(libraryCountField?.textContent).toBe('0 libraries');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any server with exactly one library, the library count SHALL display "1 library" (singular).
	 *
	 * **Validates: Requirements 9.2**
	 */
	it('should display singular form for servers with one library', () => {
		fc.assert(
			fc.property(
				serverResponseArb.chain((s) =>
					libraryResponseArb.map((lib) => ({ ...s, libraries: [lib] }))
				),
				(server) => {
					const mockOnViewDetails = vi.fn();
					const { container } = render(ServerCard, {
						props: { server, onViewDetails: mockOnViewDetails }
					});

					const card = container.querySelector('[data-server-card]');
					const libraryCountField = card?.querySelector('[data-field="library_count"]');

					expect(libraryCountField).not.toBeNull();
					expect(libraryCountField?.textContent).toBe('1 library');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * Server field display should be consistent across multiple renders.
	 *
	 * **Validates: Requirements 9.2**
	 */
	it('should maintain consistent display across renders', () => {
		fc.assert(
			fc.property(serverResponseArb, fc.integer({ min: 2, max: 5 }), (server, renderCount) => {
				const htmlOutputs: string[] = [];
				const mockOnViewDetails = vi.fn();

				for (let i = 0; i < renderCount; i++) {
					const { container } = render(ServerCard, {
						props: { server, onViewDetails: mockOnViewDetails }
					});
					const card = container.querySelector('[data-server-card]');
					htmlOutputs.push(card?.innerHTML ?? '');
					cleanup();
				}

				// All renders should produce the same HTML
				const firstOutput = htmlOutputs[0];
				for (const output of htmlOutputs) {
					expect(output).toBe(firstOutput);
				}
			}),
			{ numRuns: 50 }
		);
	});
});
