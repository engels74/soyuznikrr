/**
 * Property-based tests for Admin Layout responsive sidebar.
 *
 * Tests the following property:
 * - Property 8: Responsive Sidebar Collapse
 *
 * Since we can't easily test CSS media queries in jsdom, we focus on:
 * 1. Testing that the mobile menu toggle state works correctly
 * 2. Testing that the sidebar has correct CSS classes for responsive behavior
 * 3. Testing that mobile menu opens/closes correctly
 *
 * @module $lib/components/admin-layout.svelte.test
 */

import { cleanup, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it, vi } from 'vitest';

// Mock the $app/state module
vi.mock('$app/state', () => ({
	page: {
		url: {
			pathname: '/dashboard'
		}
	}
}));

// Mock $app/navigation
vi.mock('$app/navigation', () => ({
	goto: vi.fn()
}));

// Mock auth API
vi.mock('$lib/api/auth', () => ({
	logout: vi.fn(() => Promise.resolve())
}));

// Mock mode-watcher to avoid localStorage issues during module initialization
vi.mock('mode-watcher', () => ({
	ModeWatcher: vi.fn(),
	mode: { current: 'dark' },
	userPrefersMode: { current: 'system' },
	systemPrefersMode: { current: 'dark' },
	modeStorageKey: { current: 'mode-watcher-mode' },
	themeColors: { current: null },
	disableTransitions: { current: false },
	defineConfig: vi.fn(),
	setMode: vi.fn(),
	resetMode: vi.fn(),
	toggleMode: vi.fn()
}));

// Import the test wrapper component that provides children snippet
import AdminLayoutWrapper from './admin-layout-test-wrapper.svelte';

// =============================================================================
// Property 8: Responsive Sidebar Collapse
// =============================================================================

describe('Property 8: Responsive Sidebar Collapse', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any viewport width below the mobile breakpoint (768px), the sidebar
	 * navigation SHALL collapse into a mobile-friendly menu.
	 *
	 * Since jsdom doesn't support CSS media queries, we test the structural
	 * requirements: the desktop sidebar has md:flex (hidden on mobile),
	 * and the mobile sidebar has md:hidden (visible on mobile).
	 */
	it('should have desktop sidebar with md:flex class (hidden on mobile by default)', () => {
		const { container } = render(AdminLayoutWrapper);

		// Find the desktop sidebar - it should have md:flex and hidden classes
		const desktopSidebar = container.querySelector('aside.hidden.md\\:flex');

		expect(desktopSidebar).not.toBeNull();
		expect(desktopSidebar?.className).toContain('hidden');
		expect(desktopSidebar?.className).toContain('md:flex');
	});

	/**
	 * The mobile sidebar SHALL have md:hidden class to be hidden on desktop.
	 */
	it('should have mobile sidebar with md:hidden class (visible on mobile only)', () => {
		const { container } = render(AdminLayoutWrapper);

		// Find the mobile sidebar - it should have md:hidden class
		const mobileSidebar = container.querySelector('aside.md\\:hidden');

		expect(mobileSidebar).not.toBeNull();
		expect(mobileSidebar?.className).toContain('md:hidden');
	});

	/**
	 * The mobile header SHALL be visible only on mobile (md:hidden class).
	 */
	it('should have mobile header with md:hidden class', () => {
		const { container } = render(AdminLayoutWrapper);

		// Find the mobile header - it should have md:hidden class
		const mobileHeader = container.querySelector('header.md\\:hidden');

		expect(mobileHeader).not.toBeNull();
		expect(mobileHeader?.className).toContain('md:hidden');
	});

	/**
	 * The desktop header SHALL be visible only on desktop (hidden md:flex classes).
	 */
	it('should have desktop header with hidden md:flex classes', () => {
		const { container } = render(AdminLayoutWrapper);

		// Find the desktop header - it should have hidden and md:flex classes
		const desktopHeader = container.querySelector('header.hidden.md\\:flex');

		expect(desktopHeader).not.toBeNull();
		expect(desktopHeader?.className).toContain('hidden');
		expect(desktopHeader?.className).toContain('md:flex');
	});

	/**
	 * For any initial render, the mobile sidebar SHALL be hidden (translated off-screen).
	 */
	it('should have mobile sidebar hidden by default (translated off-screen)', () => {
		const { container } = render(AdminLayoutWrapper);

		// Find the mobile sidebar
		const mobileSidebar = container.querySelector('aside.md\\:hidden');

		expect(mobileSidebar).not.toBeNull();
		// When closed, the sidebar should have -translate-x-full class
		expect(mobileSidebar?.className).toContain('-translate-x-full');
		// And should NOT have translate-x-0 class
		expect(mobileSidebar?.className).not.toContain('translate-x-0');
	});

	/**
	 * For any click on the mobile menu button, the mobile sidebar SHALL toggle
	 * its visibility state.
	 */
	it('should toggle mobile sidebar visibility when menu button is clicked', async () => {
		const user = userEvent.setup();
		const { container } = render(AdminLayoutWrapper);

		// Find the mobile menu button by its aria-label
		const menuButton = screen.getByRole('button', { name: /open menu/i });
		expect(menuButton).not.toBeNull();

		// Initially, sidebar should be hidden
		let mobileSidebar = container.querySelector('aside.md\\:hidden');
		expect(mobileSidebar?.className).toContain('-translate-x-full');

		// Click to open
		await user.click(menuButton);

		// After click, sidebar should be visible
		mobileSidebar = container.querySelector('aside.md\\:hidden');
		expect(mobileSidebar?.className).toContain('translate-x-0');
		expect(mobileSidebar?.className).not.toContain('-translate-x-full');

		// Find the close button in the header (the actual button element, not the overlay)
		const closeButton = container.querySelector('header button[aria-label="Close menu"]');
		expect(closeButton).not.toBeNull();

		// Click to close
		await user.click(closeButton!);

		// After second click, sidebar should be hidden again
		mobileSidebar = container.querySelector('aside.md\\:hidden');
		expect(mobileSidebar?.className).toContain('-translate-x-full');
	});

	/**
	 * For any number of toggle operations, the mobile sidebar state SHALL
	 * alternate correctly between open and closed.
	 */
	it('should correctly alternate sidebar state for any number of toggles', async () => {
		const user = userEvent.setup();

		await fc.assert(
			fc.asyncProperty(fc.integer({ min: 1, max: 10 }), async (toggleCount) => {
				cleanup();
				const { container } = render(AdminLayoutWrapper);

				for (let i = 0; i < toggleCount; i++) {
					const isCurrentlyOpen = i % 2 === 1;

					// Use container.querySelector to find the specific button in the header
					const menuButton = isCurrentlyOpen
						? container.querySelector('header button[aria-label="Close menu"]')
						: container.querySelector('header button[aria-label="Open menu"]');

					expect(menuButton).not.toBeNull();
					await user.click(menuButton!);

					const mobileSidebar = container.querySelector('aside.md\\:hidden');
					const shouldBeOpen = i % 2 === 0; // After click, state flips

					if (shouldBeOpen) {
						expect(mobileSidebar?.className).toContain('translate-x-0');
					} else {
						expect(mobileSidebar?.className).toContain('-translate-x-full');
					}
				}
			}),
			{ numRuns: 20 }
		);
	});

	/**
	 * The mobile menu button SHALL have proper aria-expanded attribute
	 * reflecting the current menu state.
	 */
	it('should have correct aria-expanded attribute on menu button', async () => {
		const user = userEvent.setup();
		const { container } = render(AdminLayoutWrapper);

		// Initially, aria-expanded should be false
		const menuButton = container.querySelector('header button[aria-label="Open menu"]');
		expect(menuButton).not.toBeNull();
		expect(menuButton?.getAttribute('aria-expanded')).toBe('false');

		// Click to open
		await user.click(menuButton!);

		// After opening, aria-expanded should be true
		const closeButton = container.querySelector('header button[aria-label="Close menu"]');
		expect(closeButton).not.toBeNull();
		expect(closeButton?.getAttribute('aria-expanded')).toBe('true');
	});

	/**
	 * For any click on the mobile overlay, the mobile sidebar SHALL close.
	 */
	it('should close mobile sidebar when overlay is clicked', async () => {
		const user = userEvent.setup();
		const { container } = render(AdminLayoutWrapper);

		// Open the menu first
		const menuButton = screen.getByRole('button', { name: /open menu/i });
		await user.click(menuButton);

		// Verify sidebar is open
		let mobileSidebar = container.querySelector('aside.md\\:hidden');
		expect(mobileSidebar?.className).toContain('translate-x-0');

		// Find and click the overlay
		const overlay = container.querySelector('div.fixed.inset-0.z-40');
		expect(overlay).not.toBeNull();
		await user.click(overlay!);

		// Verify sidebar is closed
		mobileSidebar = container.querySelector('aside.md\\:hidden');
		expect(mobileSidebar?.className).toContain('-translate-x-full');
	});

	/**
	 * The mobile sidebar SHALL have proper transition classes for smooth animation.
	 */
	it('should have transition classes for smooth animation', () => {
		const { container } = render(AdminLayoutWrapper);

		const mobileSidebar = container.querySelector('aside.md\\:hidden');

		expect(mobileSidebar).not.toBeNull();
		expect(mobileSidebar?.className).toContain('transition-transform');
		expect(mobileSidebar?.className).toContain('duration-200');
		expect(mobileSidebar?.className).toContain('ease-in-out');
	});

	/**
	 * The mobile sidebar SHALL have a fixed width of 64 (w-64 = 16rem = 256px).
	 */
	it('should have fixed width for mobile sidebar', () => {
		const { container } = render(AdminLayoutWrapper);

		const mobileSidebar = container.querySelector('aside.md\\:hidden');

		expect(mobileSidebar).not.toBeNull();
		expect(mobileSidebar?.className).toContain('w-64');
	});

	/**
	 * The desktop sidebar SHALL have a fixed width of 64 (md:w-64 = 16rem = 256px).
	 */
	it('should have fixed width for desktop sidebar', () => {
		const { container } = render(AdminLayoutWrapper);

		const desktopSidebar = container.querySelector('aside.hidden.md\\:flex');

		expect(desktopSidebar).not.toBeNull();
		expect(desktopSidebar?.className).toContain('md:w-64');
	});

	/**
	 * Both sidebars SHALL contain navigation with aria-label="Main navigation".
	 */
	it('should have accessible navigation in both sidebars', () => {
		const { container } = render(AdminLayoutWrapper);

		// Find all nav elements with aria-label
		const navElements = container.querySelectorAll('nav[aria-label="Main navigation"]');

		// Should have 2 nav elements (one in mobile sidebar, one in desktop sidebar)
		expect(navElements.length).toBe(2);
	});

	/**
	 * For any responsive layout, the main content area SHALL have proper
	 * margin to account for the desktop sidebar (md:ml-64).
	 */
	it('should have proper margin on main content for desktop sidebar', () => {
		const { container } = render(AdminLayoutWrapper);

		// Find the main content wrapper div
		const contentWrapper = container.querySelector('div.flex-1.md\\:ml-64');

		expect(contentWrapper).not.toBeNull();
		expect(contentWrapper?.className).toContain('md:ml-64');
	});

	/**
	 * Property test: For any sequence of open/close operations, the sidebar
	 * state SHALL always be consistent with the number of toggles.
	 */
	it('should maintain consistent state for any sequence of operations', async () => {
		const user = userEvent.setup();

		await fc.assert(
			fc.asyncProperty(
				fc.array(fc.boolean(), { minLength: 1, maxLength: 10 }),
				async (operations) => {
					cleanup();
					const { container } = render(AdminLayoutWrapper);

					let expectedOpen = false;

					for (const shouldToggle of operations) {
						if (shouldToggle) {
							// Use container.querySelector to find the specific button in the header
							const menuButton = expectedOpen
								? container.querySelector('header button[aria-label="Close menu"]')
								: container.querySelector('header button[aria-label="Open menu"]');

							expect(menuButton).not.toBeNull();
							await user.click(menuButton!);
							expectedOpen = !expectedOpen;
						}

						const mobileSidebar = container.querySelector('aside.md\\:hidden');

						if (expectedOpen) {
							expect(mobileSidebar?.className).toContain('translate-x-0');
						} else {
							expect(mobileSidebar?.className).toContain('-translate-x-full');
						}
					}
				}
			),
			{ numRuns: 20 }
		);
	});
});
