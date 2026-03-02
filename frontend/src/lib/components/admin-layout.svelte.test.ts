/**
 * Tests for Admin Layout responsive sidebar behavior.
 *
 * Tests mobile menu toggle, overlay close, aria attributes, and
 * accessible navigation. CSS-only structural tests have been removed
 * since they test implementation details rather than behavior.
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

describe('Admin Layout Sidebar Behavior', () => {
	afterEach(() => {
		cleanup();
	});

	it('should have mobile sidebar hidden by default', () => {
		const { container } = render(AdminLayoutWrapper);

		const mobileSidebar = container.querySelector('aside.md\\:hidden');

		expect(mobileSidebar).not.toBeNull();
		// When closed, the sidebar should be translated off-screen
		expect(mobileSidebar?.className).toContain('-translate-x-full');
		expect(mobileSidebar?.className).not.toContain('translate-x-0');
	});

	it('should toggle mobile sidebar visibility when menu button is clicked', async () => {
		const user = userEvent.setup();
		const { container } = render(AdminLayoutWrapper);

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

		// Find and click the close button
		const closeButton = container.querySelector('header button[aria-label="Close menu"]');
		expect(closeButton).not.toBeNull();

		await user.click(closeButton!);

		// After close, sidebar should be hidden again
		mobileSidebar = container.querySelector('aside.md\\:hidden');
		expect(mobileSidebar?.className).toContain('-translate-x-full');
	});

	it('should correctly alternate sidebar state for any number of toggles', async () => {
		const user = userEvent.setup();

		await fc.assert(
			fc.asyncProperty(fc.integer({ min: 1, max: 10 }), async (toggleCount) => {
				cleanup();
				const { container } = render(AdminLayoutWrapper);

				for (let i = 0; i < toggleCount; i++) {
					const isCurrentlyOpen = i % 2 === 1;

					const menuButton = isCurrentlyOpen
						? container.querySelector('header button[aria-label="Close menu"]')
						: container.querySelector('header button[aria-label="Open menu"]');

					expect(menuButton).not.toBeNull();
					await user.click(menuButton!);

					const mobileSidebar = container.querySelector('aside.md\\:hidden');
					const shouldBeOpen = i % 2 === 0;

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

	it('should have correct aria-expanded attribute on menu button', async () => {
		const user = userEvent.setup();
		const { container } = render(AdminLayoutWrapper);

		const menuButton = container.querySelector('header button[aria-label="Open menu"]');
		expect(menuButton).not.toBeNull();
		expect(menuButton?.getAttribute('aria-expanded')).toBe('false');

		await user.click(menuButton!);

		const closeButton = container.querySelector('header button[aria-label="Close menu"]');
		expect(closeButton).not.toBeNull();
		expect(closeButton?.getAttribute('aria-expanded')).toBe('true');
	});

	it('should close mobile sidebar when overlay is clicked', async () => {
		const user = userEvent.setup();
		const { container } = render(AdminLayoutWrapper);

		const menuButton = screen.getByRole('button', { name: /open menu/i });
		await user.click(menuButton);

		let mobileSidebar = container.querySelector('aside.md\\:hidden');
		expect(mobileSidebar?.className).toContain('translate-x-0');

		const overlay = container.querySelector('div.fixed.inset-0.z-40');
		expect(overlay).not.toBeNull();
		await user.click(overlay!);

		mobileSidebar = container.querySelector('aside.md\\:hidden');
		expect(mobileSidebar?.className).toContain('-translate-x-full');
	});

	it('should have accessible navigation in both sidebars', () => {
		const { container } = render(AdminLayoutWrapper);

		const navElements = container.querySelectorAll('nav[aria-label="Main navigation"]');
		expect(navElements.length).toBe(2);
	});

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
