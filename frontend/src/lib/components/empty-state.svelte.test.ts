/**
 * Property-based tests for EmptyState component.
 *
 * Tests the following property:
 * - Property 38: Empty State Display
 *
 * @module $lib/components/empty-state.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it, vi } from 'vitest';
import EmptyState from './empty-state.svelte';

// =============================================================================
// Property 38: Empty State Display
// =============================================================================

describe('Property 38: Empty State Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any list view with zero items, the UI SHALL display an empty state
	 * message with helpful guidance.
	 */
	it('should display empty state with title for any valid title', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
				(title) => {
					const { container } = render(EmptyState, { props: { title } });
					const emptyState = container.querySelector('[data-empty-state]');

					expect(emptyState).not.toBeNull();

					// Verify the title is displayed
					const heading = emptyState?.querySelector('h3');
					expect(heading).not.toBeNull();
					expect(heading?.textContent).toBe(title);

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any empty state with a description, the UI SHALL display the
	 * description as helpful guidance.
	 */
	it('should display description when provided', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
				fc.string({ minLength: 1, maxLength: 200 }).filter((s) => s.trim().length > 0),
				(title, description) => {
					const { container } = render(EmptyState, {
						props: { title, description }
					});
					const emptyState = container.querySelector('[data-empty-state]');

					expect(emptyState).not.toBeNull();

					// Verify the description is displayed
					const descriptionEl = emptyState?.querySelector('p');
					expect(descriptionEl).not.toBeNull();
					expect(descriptionEl?.textContent).toBe(description);

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any empty state without a description, the UI SHALL NOT display
	 * a description paragraph.
	 */
	it('should not display description when not provided', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
				(title) => {
					const { container } = render(EmptyState, { props: { title } });
					const emptyState = container.querySelector('[data-empty-state]');

					expect(emptyState).not.toBeNull();

					// Verify no description paragraph is present
					const descriptionEl = emptyState?.querySelector('p');
					expect(descriptionEl).toBeNull();

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any empty state with an action, the UI SHALL display an action
	 * button with the correct label.
	 */
	it('should display action button when action is provided', () => {
		fc.assert(
			fc.property(
				// Generate alphanumeric titles to avoid whitespace edge cases
				fc.stringMatching(/^[a-zA-Z][a-zA-Z0-9 ]{0,48}[a-zA-Z0-9]$|^[a-zA-Z]$/),
				fc.stringMatching(/^[a-zA-Z][a-zA-Z0-9 ]{0,28}[a-zA-Z0-9]$|^[a-zA-Z]$/),
				(title, actionLabel) => {
					const mockOnClick = vi.fn();
					const { container } = render(EmptyState, {
						props: {
							title,
							action: { label: actionLabel, onClick: mockOnClick }
						}
					});
					const emptyState = container.querySelector('[data-empty-state]');

					expect(emptyState).not.toBeNull();

					// Verify the action button is displayed with correct label
					const button = emptyState?.querySelector('button');
					expect(button).not.toBeNull();
					expect(button?.textContent?.trim()).toBe(actionLabel.trim());

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any empty state without an action, the UI SHALL NOT display
	 * an action button.
	 */
	it('should not display action button when action is not provided', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
				(title) => {
					const { container } = render(EmptyState, { props: { title } });
					const emptyState = container.querySelector('[data-empty-state]');

					expect(emptyState).not.toBeNull();

					// Verify no button is present
					const button = emptyState?.querySelector('button');
					expect(button).toBeNull();

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any empty state, the UI SHALL include an icon element.
	 */
	it('should display default icon when no custom icon provided', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
				(title) => {
					const { container } = render(EmptyState, { props: { title } });
					const emptyState = container.querySelector('[data-empty-state]');

					expect(emptyState).not.toBeNull();

					// Verify an icon container is present (the div with rounded-full class)
					const iconContainer = emptyState?.querySelector('div.rounded-full');
					expect(iconContainer).not.toBeNull();

					// Verify the default Inbox icon is rendered (SVG element)
					const svg = iconContainer?.querySelector('svg');
					expect(svg).not.toBeNull();

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any empty state, the component SHALL have proper accessibility
	 * attributes including role="status" and aria-label.
	 */
	it('should have proper accessibility attributes', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
				(title) => {
					const { container } = render(EmptyState, { props: { title } });
					const emptyState = container.querySelector('[data-empty-state]');

					expect(emptyState).not.toBeNull();

					// Verify role="status" is set
					expect(emptyState?.getAttribute('role')).toBe('status');

					// Verify aria-label is set to the title
					expect(emptyState?.getAttribute('aria-label')).toBe(title);

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any empty state with both title and description, the UI SHALL
	 * display both elements in the correct order (title first, then description).
	 */
	it('should display title and description in correct order', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
				fc.string({ minLength: 1, maxLength: 200 }).filter((s) => s.trim().length > 0),
				(title, description) => {
					const { container } = render(EmptyState, {
						props: { title, description }
					});
					const emptyState = container.querySelector('[data-empty-state]');

					expect(emptyState).not.toBeNull();

					const heading = emptyState?.querySelector('h3');
					const descriptionEl = emptyState?.querySelector('p');

					expect(heading).not.toBeNull();
					expect(descriptionEl).not.toBeNull();

					// Verify title comes before description in DOM order
					const children = Array.from(emptyState?.children ?? []);
					const headingIndex = children.findIndex((el) => el.tagName === 'H3');
					const descriptionIndex = children.findIndex((el) => el.tagName === 'P');

					expect(headingIndex).toBeLessThan(descriptionIndex);

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any empty state, the component SHALL have consistent styling
	 * with dashed border and centered content.
	 */
	it('should have consistent empty state styling', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
				(title) => {
					const { container } = render(EmptyState, { props: { title } });
					const emptyState = container.querySelector('[data-empty-state]');

					expect(emptyState).not.toBeNull();

					const classList = emptyState?.className ?? '';

					// Verify dashed border styling
					expect(classList).toContain('border-dashed');

					// Verify centered content
					expect(classList).toContain('flex');
					expect(classList).toContain('flex-col');
					expect(classList).toContain('items-center');
					expect(classList).toContain('justify-center');
					expect(classList).toContain('text-center');

					cleanup();
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * Empty state display should be consistent across multiple renders
	 * with the same props.
	 */
	it('should maintain consistent display across renders', () => {
		fc.assert(
			fc.property(
				fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
				fc
					.string({ minLength: 1, maxLength: 200 })
					.filter((s) => s.trim().length > 0)
					.map((s) => s || undefined),
				fc.integer({ min: 2, max: 5 }),
				(title, description, renderCount) => {
					const htmlOutputs: string[] = [];

					for (let i = 0; i < renderCount; i++) {
						const { container } = render(EmptyState, {
							props: { title, description }
						});
						const emptyState = container.querySelector('[data-empty-state]');
						htmlOutputs.push(emptyState?.innerHTML ?? '');
						cleanup();
					}

					// All renders should produce the same HTML
					const firstOutput = htmlOutputs[0];
					for (const output of htmlOutputs) {
						expect(output).toBe(firstOutput);
					}
				}
			),
			{ numRuns: 50 }
		);
	});
});
