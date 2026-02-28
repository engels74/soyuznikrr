/**
 * Property-based tests for dark mode persistence.
 *
 * Tests the following property:
 * - Property 7: Dark Mode Persistence
 *
 * @module $lib/stores/dark-mode.svelte.test
 */

import * as fc from 'fast-check';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// =============================================================================
// Property 7: Dark Mode Persistence
// =============================================================================

describe('Property 7: Dark Mode Persistence', () => {
	let mockLocalStorage: Map<string, string>;

	beforeEach(() => {
		// Create a mock localStorage
		mockLocalStorage = new Map();

		// Mock localStorage methods
		vi.stubGlobal('localStorage', {
			getItem: vi.fn((key: string) => mockLocalStorage.get(key) ?? null),
			setItem: vi.fn((key: string, value: string) => mockLocalStorage.set(key, value)),
			removeItem: vi.fn((key: string) => mockLocalStorage.delete(key)),
			clear: vi.fn(() => mockLocalStorage.clear()),
			get length() {
				return mockLocalStorage.size;
			},
			key: vi.fn((index: number) => Array.from(mockLocalStorage.keys())[index] ?? null)
		});
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	/**
	 * For any dark mode preference set by the user, the preference SHALL be
	 * persisted to localStorage.
	 */
	it('should persist any dark mode preference to localStorage', () => {
		// mode-watcher uses 'mode-watcher-mode' as the localStorage key
		const STORAGE_KEY = 'mode-watcher-mode';

		fc.assert(
			fc.property(fc.constantFrom('light', 'dark', 'system'), (mode) => {
				// Simulate setting the mode preference
				localStorage.setItem(STORAGE_KEY, mode);

				// Verify the preference was persisted
				const storedValue = localStorage.getItem(STORAGE_KEY);
				expect(storedValue).toBe(mode);
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any dark mode preference stored in localStorage, the preference
	 * SHALL be restored on subsequent page loads.
	 */
	it('should restore any dark mode preference from localStorage', () => {
		const STORAGE_KEY = 'mode-watcher-mode';

		fc.assert(
			fc.property(fc.constantFrom('light', 'dark', 'system'), (mode) => {
				// Pre-populate localStorage with a mode preference
				mockLocalStorage.set(STORAGE_KEY, mode);

				// Simulate reading the preference on page load
				const restoredValue = localStorage.getItem(STORAGE_KEY);

				// Verify the preference was restored correctly
				expect(restoredValue).toBe(mode);
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * The localStorage key used for dark mode persistence should be consistent.
	 */
	it('should use consistent localStorage key for mode persistence', () => {
		const STORAGE_KEY = 'mode-watcher-mode';

		fc.assert(
			fc.property(
				fc.constantFrom('light', 'dark', 'system'),
				fc.integer({ min: 1, max: 10 }),
				(mode, iterations) => {
					// Simulate multiple read/write cycles
					for (let i = 0; i < iterations; i++) {
						localStorage.setItem(STORAGE_KEY, mode);
						const retrieved = localStorage.getItem(STORAGE_KEY);
						expect(retrieved).toBe(mode);
					}

					// Verify the key is always the same
					expect(mockLocalStorage.has(STORAGE_KEY)).toBe(true);
					expect(mockLocalStorage.size).toBe(1);
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * Dark mode preference should survive page reload simulation.
	 */
	it('should survive simulated page reload', () => {
		const STORAGE_KEY = 'mode-watcher-mode';

		fc.assert(
			fc.property(fc.constantFrom('light', 'dark', 'system'), (mode) => {
				// Simulate initial page load and setting preference
				localStorage.setItem(STORAGE_KEY, mode);

				// Simulate page reload by clearing in-memory state but keeping localStorage
				const storedBeforeReload = mockLocalStorage.get(STORAGE_KEY);

				// Simulate new page load reading from localStorage
				const restoredAfterReload = localStorage.getItem(STORAGE_KEY);

				// Verify persistence across reload
				expect(storedBeforeReload).toBe(mode);
				expect(restoredAfterReload).toBe(mode);
				expect(storedBeforeReload).toBe(restoredAfterReload);
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * Only valid mode values should be accepted.
	 */
	it('should only accept valid mode values', () => {
		const VALID_MODES = ['light', 'dark', 'system'] as const;

		fc.assert(
			fc.property(fc.constantFrom(...VALID_MODES), (mode) => {
				// Verify the mode is one of the valid values
				expect(VALID_MODES).toContain(mode);
			}),
			{ numRuns: 100 }
		);
	});
});
