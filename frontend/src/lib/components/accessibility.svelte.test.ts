/**
 * Property-based tests for accessibility compliance.
 *
 * Tests the following property:
 * - Property 34: Accessibility Compliance
 *
 * Tests keyboard navigation and ARIA attributes to meet WCAG 2.1 AA compliance.
 *
 * @module $lib/components/accessibility.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ConfirmDialog from './confirm-dialog.svelte';
import EmptyState from './empty-state.svelte';
import ErrorState from './error-state.svelte';
import StatusBadge from './status-badge.svelte';

// =============================================================================
// Property 34: Accessibility Compliance
// =============================================================================

describe('Property 34: Accessibility Compliance', () => {
	afterEach(() => {
		cleanup();
	});

	// =========================================================================
	// ARIA Attributes Tests
	// =========================================================================

	describe('ARIA Attributes', () => {
		/**
		 * For any interactive element, the element SHALL have appropriate
		 * ARIA attributes for screen reader accessibility.
		 */
		it('should have role="status" on empty state for screen readers', () => {
			fc.assert(
				fc.property(
					fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
					(title) => {
						const { container } = render(EmptyState, { props: { title } });
						const emptyState = container.querySelector('[data-empty-state]');

						expect(emptyState).not.toBeNull();

						// Verify role="status" for screen readers
						expect(emptyState?.getAttribute('role')).toBe('status');

						// Verify aria-label is set
						expect(emptyState?.getAttribute('aria-label')).toBe(title);

						cleanup();
					}
				),
				{ numRuns: 50 }
			);
		});

		/**
		 * For any error state, the element SHALL have role="alert" and
		 * aria-live for dynamic content announcements.
		 */
		it('should have role="alert" and aria-live on error state', () => {
			fc.assert(
				fc.property(
					fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
					(message) => {
						const { container } = render(ErrorState, { props: { message } });
						const errorState = container.querySelector('[data-error-state]');

						expect(errorState).not.toBeNull();

						// Verify role="alert" for immediate announcement
						expect(errorState?.getAttribute('role')).toBe('alert');

						// Verify aria-live for dynamic updates
						expect(errorState?.getAttribute('aria-live')).toBe('polite');

						cleanup();
					}
				),
				{ numRuns: 50 }
			);
		});

		/**
		 * For any status badge, the element SHALL have appropriate
		 * data attributes for status identification.
		 */
		it('should have data-status attribute on status badges', () => {
			fc.assert(
				fc.property(
					fc.constantFrom(
						'active' as const,
						'enabled' as const,
						'pending' as const,
						'limited' as const,
						'disabled' as const,
						'expired' as const
					),
					(status) => {
						const { container } = render(StatusBadge, { props: { status } });
						const badge = container.querySelector('[data-status-badge]');

						expect(badge).not.toBeNull();

						// Verify data-status attribute is set for identification
						expect(badge?.getAttribute('data-status')).toBe(status);

						cleanup();
					}
				),
				{ numRuns: 50 }
			);
		});
	});

	// =========================================================================
	// Keyboard Navigation Tests
	// =========================================================================

	describe('Keyboard Navigation', () => {
		/**
		 * For any button element, the button SHALL be focusable and
		 * have appropriate type attribute.
		 */
		it('should have focusable buttons in empty state', () => {
			fc.assert(
				fc.property(
					fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
					fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0),
					(title, actionLabel) => {
						const mockOnClick = vi.fn();
						const { container } = render(EmptyState, {
							props: {
								title,
								action: { label: actionLabel, onClick: mockOnClick }
							}
						});

						const button = container.querySelector('button');

						expect(button).not.toBeNull();

						// Verify button is not disabled (focusable)
						expect(button?.disabled).toBeFalsy();

						// Verify button has type attribute
						expect(button?.getAttribute('type')).toBe('button');

						cleanup();
					}
				),
				{ numRuns: 50 }
			);
		});

		/**
		 * For any retry button in error state, the button SHALL be
		 * focusable and have appropriate type attribute.
		 */
		it('should have focusable retry button in error state', () => {
			fc.assert(
				fc.property(
					fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
					(message) => {
						const mockRetry = vi.fn();
						const { container } = render(ErrorState, {
							props: { message, onRetry: mockRetry }
						});

						const button = container.querySelector('button');

						expect(button).not.toBeNull();

						// Verify button is not disabled (focusable)
						expect(button?.disabled).toBeFalsy();

						cleanup();
					}
				),
				{ numRuns: 50 }
			);
		});
	});

	// =========================================================================
	// Form Accessibility Tests
	// =========================================================================

	describe('Form Accessibility', () => {
		/**
		 * For any form with validation errors, the errors SHALL be
		 * associated with their respective fields for screen readers.
		 */
		it('should have data-field-error attributes for validation errors', async () => {
			// Test the Jellyfin registration form
			const { default: RegistrationForm } = await import('./join/registration-form.svelte');

			const mockSubmit = vi.fn();
			const { container } = render(RegistrationForm, {
				props: {
					formData: { username: '', password: '', email: '' },
					errors: {
						username: ['Username is required'],
						password: ['Password is required']
					},
					submitting: false,
					onSubmit: mockSubmit
				}
			});

			// Verify error elements have data-field-error attributes
			const usernameError = container.querySelector('[data-field-error="username"]');
			const passwordError = container.querySelector('[data-field-error="password"]');

			expect(usernameError).not.toBeNull();
			expect(passwordError).not.toBeNull();

			// Verify error messages are displayed
			expect(usernameError?.textContent).toContain('Username is required');
			expect(passwordError?.textContent).toContain('Password is required');

			cleanup();
		});

		/**
		 * For any form input, the input SHALL have appropriate
		 * autocomplete attributes for accessibility.
		 */
		it('should have autocomplete attributes on form inputs', async () => {
			const { default: RegistrationForm } = await import('./join/registration-form.svelte');

			const mockSubmit = vi.fn();
			const { container } = render(RegistrationForm, {
				props: {
					formData: { username: '', password: '', email: '' },
					errors: {},
					submitting: false,
					onSubmit: mockSubmit
				}
			});

			// Find inputs by data attributes
			const usernameInput = container.querySelector('[data-field-username]');
			const passwordInput = container.querySelector('[data-field-password]');
			const emailInput = container.querySelector('[data-field-email]');

			expect(usernameInput).not.toBeNull();
			expect(passwordInput).not.toBeNull();
			expect(emailInput).not.toBeNull();

			// Verify autocomplete attributes
			expect(usernameInput?.getAttribute('autocomplete')).toBe('username');
			expect(passwordInput?.getAttribute('autocomplete')).toBe('new-password');
			expect(emailInput?.getAttribute('autocomplete')).toBe('email');

			cleanup();
		});

		/**
		 * For any password toggle button, the button SHALL have
		 * aria-label for screen reader accessibility.
		 */
		it('should have aria-label on password visibility toggle', async () => {
			const { default: RegistrationForm } = await import('./join/registration-form.svelte');

			const mockSubmit = vi.fn();
			const { container } = render(RegistrationForm, {
				props: {
					formData: { username: '', password: '', email: '' },
					errors: {},
					submitting: false,
					onSubmit: mockSubmit
				}
			});

			// Find the password visibility toggle button
			const toggleButton = container.querySelector('button[aria-label]');

			expect(toggleButton).not.toBeNull();

			// Verify aria-label is set
			const ariaLabel = toggleButton?.getAttribute('aria-label');
			expect(ariaLabel).toBeTruthy();
			expect(['Show password', 'Hide password']).toContain(ariaLabel);

			cleanup();
		});
	});

	// =========================================================================
	// Dialog Accessibility Tests
	// =========================================================================

	describe('Dialog Accessibility', () => {
		/**
		 * For any confirm dialog, the dialog SHALL have appropriate
		 * title and description for screen readers.
		 */
		it('should have title and description in confirm dialog', () => {
			fc.assert(
				fc.property(
					fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
					fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
					(title, description) => {
						const mockConfirm = vi.fn();
						const mockCancel = vi.fn();

						render(ConfirmDialog, {
							props: {
								open: true,
								title,
								description,
								onConfirm: mockConfirm,
								onCancel: mockCancel
							}
						});

						// Dialog content should be rendered when open
						// Note: Dialog uses portal, so we check document.body
						// The dialog should render title and description
						// (exact selectors depend on shadcn-svelte implementation)
						expect(document.body.textContent).toContain(title);
						expect(document.body.textContent).toContain(description);

						cleanup();
					}
				),
				{ numRuns: 20 }
			);
		});
	});

	// =========================================================================
	// Color Contrast Tests
	// =========================================================================

	describe('Color Contrast', () => {
		/**
		 * For any status badge, the badge SHALL use distinct colors
		 * for different statuses to aid visual identification.
		 */
		it('should use distinct colors for different status values', () => {
			const statusColors: Record<string, string[]> = {};

			const statuses = ['active', 'enabled', 'pending', 'limited', 'disabled', 'expired'] as const;

			for (const status of statuses) {
				const { container } = render(StatusBadge, { props: { status } });
				const badge = container.querySelector('[data-status-badge]');
				statusColors[status] = (badge?.className ?? '').split(' ');
				cleanup();
			}

			// Green statuses should have emerald classes
			const activeColors = statusColors.active ?? [];
			const enabledColors = statusColors.enabled ?? [];
			expect(activeColors.some((c) => c.includes('emerald'))).toBe(true);
			expect(enabledColors.some((c) => c.includes('emerald'))).toBe(true);

			// Amber statuses should have amber classes
			const pendingColors = statusColors.pending ?? [];
			const limitedColors = statusColors.limited ?? [];
			expect(pendingColors.some((c) => c.includes('amber'))).toBe(true);
			expect(limitedColors.some((c) => c.includes('amber'))).toBe(true);

			// Red statuses should have rose classes
			const disabledColors = statusColors.disabled ?? [];
			const expiredColors = statusColors.expired ?? [];
			expect(disabledColors.some((c) => c.includes('rose'))).toBe(true);
			expect(expiredColors.some((c) => c.includes('rose'))).toBe(true);
		});

		/**
		 * For any error state, the error SHALL use rose/red colors
		 * to indicate error condition visually.
		 */
		it('should use rose colors for error states', () => {
			fc.assert(
				fc.property(
					fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
					(message) => {
						const { container } = render(ErrorState, { props: { message } });
						const errorState = container.querySelector('[data-error-state]');

						expect(errorState).not.toBeNull();

						const classList = errorState?.className ?? '';

						// Verify rose color scheme for error indication
						expect(classList).toContain('rose');

						cleanup();
					}
				),
				{ numRuns: 50 }
			);
		});
	});

	// =========================================================================
	// Focus Management Tests
	// =========================================================================

	describe('Focus Management', () => {
		/**
		 * For any interactive component, focus styles SHALL be visible
		 * for keyboard navigation.
		 */
		it('should have focus-visible styles on buttons', async () => {
			const { default: Button } = await import('./ui/button/button.svelte');

			const { container } = render(Button, {
				props: { children: undefined }
			});

			const button = container.querySelector('button');

			expect(button).not.toBeNull();

			// Verify focus-visible classes are present in button styles
			const classList = button?.className ?? '';
			expect(classList).toContain('focus-visible');

			cleanup();
		});
	});

	// =========================================================================
	// Semantic HTML Tests
	// =========================================================================

	describe('Semantic HTML', () => {
		/**
		 * For any heading in components, the heading SHALL use
		 * appropriate heading level (h1-h6).
		 */
		it('should use semantic heading elements', () => {
			fc.assert(
				fc.property(
					fc.string({ minLength: 1, maxLength: 100 }).filter((s) => s.trim().length > 0),
					(title) => {
						const { container } = render(EmptyState, { props: { title } });

						// Verify heading element is used
						const heading = container.querySelector('h3');
						expect(heading).not.toBeNull();
						expect(heading?.textContent).toBe(title);

						cleanup();
					}
				),
				{ numRuns: 50 }
			);
		});

		/**
		 * For any error state, the error message SHALL use
		 * paragraph element for proper semantics.
		 */
		it('should use semantic paragraph elements for messages', () => {
			fc.assert(
				fc.property(
					fc.string({ minLength: 1, maxLength: 500 }).filter((s) => s.trim().length > 0),
					(message) => {
						const { container } = render(ErrorState, { props: { message } });

						// Verify paragraph element is used for message
						const paragraph = container.querySelector('p');
						expect(paragraph).not.toBeNull();
						expect(paragraph?.textContent).toBe(message);

						cleanup();
					}
				),
				{ numRuns: 50 }
			);
		});
	});
});
