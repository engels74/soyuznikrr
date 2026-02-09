/**
 * Property-based tests for Join Page code validation.
 *
 * Tests the following properties:
 * - Property 27: Valid Code Display
 * - Property 28: Invalid Code Error Display
 * - Property 29: Duration Display
 *
 * **Validates: Requirements 10.2, 10.3, 10.4**
 *
 * @module routes/(public)/join/[code]/join-page.svelte.test
 */

import { cleanup, render } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it } from 'vitest';
import type {
	InvitationValidationResponse,
	LibraryResponse,
	MediaServerResponse
} from '$lib/api/client';
import JoinPageTestWrapper from './join-page-test-wrapper.svelte';

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
 * Arbitrary for generating valid invitation codes.
 */
const invitationCodeArb = fc.stringMatching(/^[a-zA-Z0-9]{4,20}$/);

/**
 * Arbitrary for generating valid media server responses.
 */
const mediaServerResponseArb: fc.Arbitrary<MediaServerResponse> = fc.record({
	id: fc.uuid(),
	name: fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0),
	server_type: fc.constantFrom('jellyfin' as const, 'plex' as const),
	url: fc.webUrl(),
	enabled: fc.boolean(),
	created_at: isoDateArb,
	updated_at: fc.option(isoDateArb, { nil: null })
});

/**
 * Arbitrary for generating valid library responses.
 */
const libraryResponseArb: fc.Arbitrary<LibraryResponse> = fc.record({
	id: fc.uuid(),
	name: fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0),
	library_type: fc.constantFrom('movies', 'tvshows', 'music', 'photos'),
	external_id: fc.string({ minLength: 1, maxLength: 20 }),
	created_at: isoDateArb,
	updated_at: fc.option(isoDateArb, { nil: null })
});

/**
 * Arbitrary for generating valid invitation validation responses.
 */
const validValidationResponseArb: fc.Arbitrary<InvitationValidationResponse> = fc.record({
	valid: fc.constant(true),
	failure_reason: fc.constant(null),
	target_servers: fc.array(mediaServerResponseArb, {
		minLength: 1,
		maxLength: 5
	}),
	allowed_libraries: fc.option(fc.array(libraryResponseArb, { minLength: 0, maxLength: 10 }), {
		nil: null
	}),
	duration_days: fc.option(fc.integer({ min: 1, max: 365 }), { nil: null })
});

/**
 * Arbitrary for generating invalid invitation validation responses.
 */
const invalidValidationResponseArb: fc.Arbitrary<InvitationValidationResponse> = fc.record({
	valid: fc.constant(false),
	failure_reason: fc.constantFrom('not_found', 'disabled', 'expired', 'max_uses_reached'),
	target_servers: fc.constant(null),
	allowed_libraries: fc.constant(null),
	duration_days: fc.constant(null)
});

// =============================================================================
// Property 27: Valid Code Display
// Validates: Requirements 10.2
// =============================================================================

describe('Property 27: Valid Code Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any valid invitation code, the validation page SHALL display
	 * the target_servers and allowed_libraries from the validation response.
	 *
	 * **Validates: Requirements 10.2**
	 */
	it('should display target servers for valid codes', () => {
		fc.assert(
			fc.property(invitationCodeArb, validValidationResponseArb, (code, validation) => {
				const { container } = render(JoinPageTestWrapper, {
					props: { code, validation, error: null }
				});

				const page = container.querySelector('[data-join-page]');
				expect(page).not.toBeNull();

				// Should show valid code card
				const validCard = container.querySelector('[data-valid-code]');
				expect(validCard).not.toBeNull();

				// Should display the code
				const codeDisplay = container.querySelector('[data-code]');
				expect(codeDisplay).not.toBeNull();
				expect(codeDisplay?.textContent).toBe(code);

				// Should display target servers section
				const targetServers = container.querySelector('[data-target-servers]');
				expect(targetServers).not.toBeNull();

				// Should display each server
				for (const server of validation.target_servers ?? []) {
					const serverItem = container.querySelector(`[data-server-item="${server.id}"]`);
					expect(serverItem).not.toBeNull();

					const serverName = serverItem?.querySelector('[data-server-name]');
					expect(serverName?.textContent).toBe(server.name);

					const serverType = serverItem?.querySelector('[data-server-type]');
					expect(serverType?.textContent).toBe(server.server_type);
				}

				cleanup();
			}),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any valid invitation code with allowed libraries, the validation page
	 * SHALL display the allowed_libraries from the validation response.
	 *
	 * **Validates: Requirements 10.2**
	 */
	it('should display allowed libraries when specified', () => {
		fc.assert(
			fc.property(
				invitationCodeArb,
				validValidationResponseArb.chain((v) =>
					fc.array(libraryResponseArb, { minLength: 1, maxLength: 5 }).map((libs) => ({
						...v,
						allowed_libraries: libs
					}))
				),
				(code, validation) => {
					const { container } = render(JoinPageTestWrapper, {
						props: { code, validation, error: null }
					});

					// Should display allowed libraries section
					const allowedLibraries = container.querySelector('[data-allowed-libraries]');
					expect(allowedLibraries).not.toBeNull();

					// Should display each library
					for (const library of validation.allowed_libraries ?? []) {
						const libraryItem = container.querySelector(`[data-library-item="${library.id}"]`);
						expect(libraryItem).not.toBeNull();
						expect(libraryItem?.textContent).toBe(library.name);
					}

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any valid invitation code without specific libraries, the validation page
	 * SHALL display a message indicating access to all libraries.
	 *
	 * **Validates: Requirements 10.2**
	 */
	it('should display all libraries message when no specific libraries', () => {
		fc.assert(
			fc.property(
				invitationCodeArb,
				validValidationResponseArb.map((v) => ({
					...v,
					allowed_libraries: null
				})),
				(code, validation) => {
					const { container } = render(JoinPageTestWrapper, {
						props: { code, validation, error: null }
					});

					// Should not display specific libraries section
					const allowedLibraries = container.querySelector('[data-allowed-libraries]');
					expect(allowedLibraries).toBeNull();

					// Should display all libraries message
					const allLibraries = container.querySelector('[data-all-libraries]');
					expect(allLibraries).not.toBeNull();
					expect(allLibraries?.textContent).toContain('all libraries');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});
});

// =============================================================================
// Property 28: Invalid Code Error Display
// Validates: Requirements 10.3
// =============================================================================

describe('Property 28: Invalid Code Error Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any invalid invitation code with a failure_reason (not_found, disabled,
	 * expired, max_uses_reached), the validation page SHALL display a user-friendly
	 * error message corresponding to the failure reason.
	 *
	 * **Validates: Requirements 10.3**
	 */
	it('should display appropriate error message for each failure reason', () => {
		fc.assert(
			fc.property(invitationCodeArb, invalidValidationResponseArb, (code, validation) => {
				const { container } = render(JoinPageTestWrapper, {
					props: { code, validation, error: null }
				});

				const page = container.querySelector('[data-join-page]');
				expect(page).not.toBeNull();

				// Should show invalid code card
				const invalidCard = container.querySelector('[data-invalid-code]');
				expect(invalidCard).not.toBeNull();

				// Should display the code
				const codeDisplay = container.querySelector('[data-code]');
				expect(codeDisplay).not.toBeNull();
				expect(codeDisplay?.textContent).toBe(code);

				// Should display failure reason as data attribute
				const failureElement = container.querySelector('[data-failure-reason]');
				expect(failureElement).not.toBeNull();
				expect(failureElement?.getAttribute('data-failure-reason')).toBe(validation.failure_reason);

				// Should display appropriate error message based on failure reason
				const errorMessage = failureElement?.textContent ?? '';
				switch (validation.failure_reason) {
					case 'not_found':
						expect(errorMessage).toContain('does not exist');
						break;
					case 'disabled':
						expect(errorMessage).toContain('disabled');
						break;
					case 'expired':
						expect(errorMessage).toContain('expired');
						break;
					case 'max_uses_reached':
						expect(errorMessage).toContain('maximum number of uses');
						break;
				}

				cleanup();
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any invalid code with 'not_found' failure reason, the error message
	 * SHALL indicate the code does not exist.
	 *
	 * **Validates: Requirements 10.3**
	 */
	it('should display not found message for not_found failure', () => {
		fc.assert(
			fc.property(
				invitationCodeArb,
				invalidValidationResponseArb.map((v) => ({
					...v,
					failure_reason: 'not_found'
				})),
				(code, validation) => {
					const { container } = render(JoinPageTestWrapper, {
						props: { code, validation, error: null }
					});

					const failureElement = container.querySelector('[data-failure-reason="not_found"]');
					expect(failureElement).not.toBeNull();
					expect(failureElement?.textContent).toContain('does not exist');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any invalid code with 'disabled' failure reason, the error message
	 * SHALL indicate the invitation has been disabled.
	 *
	 * **Validates: Requirements 10.3**
	 */
	it('should display disabled message for disabled failure', () => {
		fc.assert(
			fc.property(
				invitationCodeArb,
				invalidValidationResponseArb.map((v) => ({
					...v,
					failure_reason: 'disabled'
				})),
				(code, validation) => {
					const { container } = render(JoinPageTestWrapper, {
						props: { code, validation, error: null }
					});

					const failureElement = container.querySelector('[data-failure-reason="disabled"]');
					expect(failureElement).not.toBeNull();
					expect(failureElement?.textContent).toContain('disabled');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any invalid code with 'expired' failure reason, the error message
	 * SHALL indicate the invitation has expired.
	 *
	 * **Validates: Requirements 10.3**
	 */
	it('should display expired message for expired failure', () => {
		fc.assert(
			fc.property(
				invitationCodeArb,
				invalidValidationResponseArb.map((v) => ({
					...v,
					failure_reason: 'expired'
				})),
				(code, validation) => {
					const { container } = render(JoinPageTestWrapper, {
						props: { code, validation, error: null }
					});

					const failureElement = container.querySelector('[data-failure-reason="expired"]');
					expect(failureElement).not.toBeNull();
					expect(failureElement?.textContent).toContain('expired');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any invalid code with 'max_uses_reached' failure reason, the error message
	 * SHALL indicate the invitation has reached its maximum uses.
	 *
	 * **Validates: Requirements 10.3**
	 */
	it('should display max uses message for max_uses_reached failure', () => {
		fc.assert(
			fc.property(
				invitationCodeArb,
				invalidValidationResponseArb.map((v) => ({
					...v,
					failure_reason: 'max_uses_reached'
				})),
				(code, validation) => {
					const { container } = render(JoinPageTestWrapper, {
						props: { code, validation, error: null }
					});

					const failureElement = container.querySelector(
						'[data-failure-reason="max_uses_reached"]'
					);
					expect(failureElement).not.toBeNull();
					expect(failureElement?.textContent).toContain('maximum number of uses');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});
});

// =============================================================================
// Property 29: Duration Display
// Validates: Requirements 10.4
// =============================================================================

describe('Property 29: Duration Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any valid invitation with a non-null duration_days value, the validation
	 * page SHALL display the duration indicating how long access will last.
	 *
	 * **Validates: Requirements 10.4**
	 */
	it('should display duration when set', () => {
		fc.assert(
			fc.property(
				invitationCodeArb,
				validValidationResponseArb.chain((v) =>
					fc.integer({ min: 1, max: 365 }).map((days) => ({
						...v,
						duration_days: days
					}))
				),
				(code, validation) => {
					const { container } = render(JoinPageTestWrapper, {
						props: { code, validation, error: null }
					});

					// Should display duration section
					const durationDisplay = container.querySelector('[data-duration-display]');
					expect(durationDisplay).not.toBeNull();

					// Should display the correct number of days
					const durationValue = container.querySelector('[data-duration-value]');
					expect(durationValue).not.toBeNull();
					expect(durationValue?.textContent).toBe(String(validation.duration_days));

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any valid invitation without duration_days (null), the validation page
	 * SHALL NOT display the duration section.
	 *
	 * **Validates: Requirements 10.4**
	 */
	it('should not display duration when not set', () => {
		fc.assert(
			fc.property(
				invitationCodeArb,
				validValidationResponseArb.map((v) => ({
					...v,
					duration_days: null
				})),
				(code, validation) => {
					const { container } = render(JoinPageTestWrapper, {
						props: { code, validation, error: null }
					});

					// Should NOT display duration section
					const durationDisplay = container.querySelector('[data-duration-display]');
					expect(durationDisplay).toBeNull();

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any valid invitation with duration_days, the duration display SHALL
	 * include the word "days" to indicate the unit.
	 *
	 * **Validates: Requirements 10.4**
	 */
	it('should display days unit in duration message', () => {
		fc.assert(
			fc.property(
				invitationCodeArb,
				validValidationResponseArb.chain((v) =>
					fc.integer({ min: 1, max: 365 }).map((days) => ({
						...v,
						duration_days: days
					}))
				),
				(code, validation) => {
					const { container } = render(JoinPageTestWrapper, {
						props: { code, validation, error: null }
					});

					const durationDisplay = container.querySelector('[data-duration-display]');
					expect(durationDisplay).not.toBeNull();
					expect(durationDisplay?.textContent).toContain('days');

					cleanup();
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * Duration display should be consistent across multiple renders.
	 *
	 * **Validates: Requirements 10.4**
	 */
	it('should maintain consistent duration display across renders', () => {
		fc.assert(
			fc.property(
				invitationCodeArb,
				validValidationResponseArb.chain((v) =>
					fc.integer({ min: 1, max: 365 }).map((days) => ({
						...v,
						duration_days: days
					}))
				),
				fc.integer({ min: 2, max: 5 }),
				(code, validation, renderCount) => {
					const durationTexts: string[] = [];

					for (let i = 0; i < renderCount; i++) {
						const { container } = render(JoinPageTestWrapper, {
							props: { code, validation, error: null }
						});
						const durationDisplay = container.querySelector('[data-duration-display]');
						durationTexts.push(durationDisplay?.textContent ?? '');
						cleanup();
					}

					// All renders should produce the same duration text
					const firstText = durationTexts[0];
					for (const text of durationTexts) {
						expect(text).toBe(firstText);
					}
				}
			),
			{ numRuns: 30 }
		);
	});
});
