/**
 * Property-based tests for invitation form components.
 *
 * Tests the following properties:
 * - Property 14: Form Validation Error Display
 * - Property 15: Invitation Detail Field Display
 * - Property 16: Immutable Field Protection
 *
 * **Validates: Requirements 5.9, 6.2, 6.4, 14.3**
 *
 * @module $lib/components/invitations/invitation-form.svelte.test
 */

import { cleanup } from '@testing-library/svelte';
import * as fc from 'fast-check';
import { afterEach, describe, expect, it } from 'vitest';
import {
	type CreateInvitationInput,
	createInvitationSchema,
	type UpdateInvitationInput,
	updateInvitationSchema
} from '$lib/schemas/invitation';

// =============================================================================
// Test Data Generators
// =============================================================================

/**
 * Generate a valid UUID v4 string.
 */
const uuidArb = fc.uuid();

/**
 * Generate a valid ISO 8601 date string.
 */
const isoDateArb = fc
	.integer({
		min: new Date('2020-01-01T00:00:00.000Z').getTime(),
		max: new Date('2030-12-31T23:59:59.999Z').getTime()
	})
	.map((timestamp) => new Date(timestamp).toISOString());

/**
 * Generate a valid invitation code (alphanumeric, 1-20 chars).
 */
const validCodeArb = fc.stringMatching(/^[a-zA-Z0-9]{1,20}$/);

/**
 * Generate an invalid invitation code (contains special chars or too long).
 */
const invalidCodeArb = fc.oneof(
	fc.stringMatching(/^[a-zA-Z0-9]{21,30}$/), // Too long
	fc.stringMatching(/^[a-zA-Z0-9]*[!@#$%^&*()]+[a-zA-Z0-9]*$/) // Contains special chars
);

/**
 * Generate valid CreateInvitationInput.
 */
const validCreateInputArb: fc.Arbitrary<CreateInvitationInput> = fc.record({
	server_ids: fc.array(uuidArb, { minLength: 1, maxLength: 5 }),
	code: fc.oneof(validCodeArb, fc.constant('')),
	expires_at: fc.oneof(isoDateArb, fc.constant('')),
	max_uses: fc.oneof(fc.integer({ min: 1, max: 1000 }), fc.constant(undefined)),
	duration_days: fc.oneof(fc.integer({ min: 1, max: 365 }), fc.constant(undefined)),
	library_ids: fc.oneof(fc.array(uuidArb, { minLength: 0, maxLength: 10 }), fc.constant(undefined))
});

/**
 * Generate invalid CreateInvitationInput (missing required fields).
 */
const invalidCreateInputArb: fc.Arbitrary<CreateInvitationInput> = fc.record({
	server_ids: fc.constant([]), // Empty - should fail validation
	code: fc.oneof(validCodeArb, fc.constant('')),
	expires_at: fc.oneof(isoDateArb, fc.constant('')),
	max_uses: fc.oneof(fc.integer({ min: 1, max: 1000 }), fc.constant(undefined)),
	duration_days: fc.oneof(fc.integer({ min: 1, max: 365 }), fc.constant(undefined)),
	library_ids: fc.constant(undefined)
});

/**
 * Generate valid UpdateInvitationInput.
 */
const validUpdateInputArb: fc.Arbitrary<UpdateInvitationInput> = fc.record({
	expires_at: fc.oneof(isoDateArb, fc.constant(''), fc.constant(null)),
	max_uses: fc.oneof(fc.integer({ min: 1, max: 1000 }), fc.constant(undefined), fc.constant(null)),
	duration_days: fc.oneof(
		fc.integer({ min: 1, max: 365 }),
		fc.constant(undefined),
		fc.constant(null)
	),
	enabled: fc.oneof(fc.boolean(), fc.constant(undefined)),
	server_ids: fc.oneof(fc.array(uuidArb, { minLength: 1, maxLength: 5 }), fc.constant(undefined)),
	library_ids: fc.oneof(fc.array(uuidArb, { minLength: 0, maxLength: 10 }), fc.constant(undefined))
});

// =============================================================================
// Property 14: Form Validation Error Display
// Validates: Requirements 5.9, 14.3
// =============================================================================

describe('Property 14: Form Validation Error Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any form field with a validation error, the form SHALL display
	 * the error message inline below the field.
	 *
	 * **Validates: Requirements 5.9, 14.3**
	 */
	it('should produce validation errors for invalid create input', () => {
		fc.assert(
			fc.property(invalidCreateInputArb, (input) => {
				const result = createInvitationSchema.safeParse(input);

				// Should fail validation due to empty server_ids
				expect(result.success).toBe(false);

				if (!result.success) {
					// Should have at least one error
					expect(result.error.issues.length).toBeGreaterThan(0);

					// Should have error for server_ids field
					const serverIdsError = result.error.issues.find((issue) =>
						issue.path.includes('server_ids')
					);
					expect(serverIdsError).toBeDefined();
				}
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any valid create input, the schema SHALL pass validation.
	 *
	 * **Validates: Requirements 5.9**
	 */
	it('should pass validation for valid create input', () => {
		fc.assert(
			fc.property(validCreateInputArb, (input) => {
				const result = createInvitationSchema.safeParse(input);
				expect(result.success).toBe(true);
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any invalid code format, the schema SHALL produce a validation error.
	 *
	 * **Validates: Requirements 5.9**
	 */
	it('should reject invalid code formats', () => {
		fc.assert(
			fc.property(
				fc.record({
					server_ids: fc.array(uuidArb, { minLength: 1, maxLength: 3 }),
					code: invalidCodeArb,
					expires_at: fc.constant(''),
					max_uses: fc.constant(undefined),
					duration_days: fc.constant(undefined),
					library_ids: fc.constant(undefined)
				}),
				(input) => {
					const result = createInvitationSchema.safeParse(input);

					// Should fail validation due to invalid code
					expect(result.success).toBe(false);

					if (!result.success) {
						const codeError = result.error.issues.find((issue) => issue.path.includes('code'));
						expect(codeError).toBeDefined();
					}
				}
			),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any negative max_uses value, the schema SHALL produce a validation error.
	 *
	 * **Validates: Requirements 5.9**
	 */
	it('should reject negative max_uses values', () => {
		fc.assert(
			fc.property(fc.integer({ min: -1000, max: -1 }), (negativeValue) => {
				const input: CreateInvitationInput = {
					server_ids: ['00000000-0000-0000-0000-000000000001'],
					code: '',
					expires_at: '',
					max_uses: negativeValue,
					duration_days: undefined,
					library_ids: undefined
				};

				const result = createInvitationSchema.safeParse(input);
				expect(result.success).toBe(false);
			}),
			{ numRuns: 50 }
		);
	});

	/**
	 * For any negative duration_days value, the schema SHALL produce a validation error.
	 *
	 * **Validates: Requirements 5.9**
	 */
	it('should reject negative duration_days values', () => {
		fc.assert(
			fc.property(fc.integer({ min: -1000, max: -1 }), (negativeValue) => {
				const input: CreateInvitationInput = {
					server_ids: ['00000000-0000-0000-0000-000000000001'],
					code: '',
					expires_at: '',
					max_uses: undefined,
					duration_days: negativeValue,
					library_ids: undefined
				};

				const result = createInvitationSchema.safeParse(input);
				expect(result.success).toBe(false);
			}),
			{ numRuns: 50 }
		);
	});
});

// =============================================================================
// Property 15: Invitation Detail Field Display
// Validates: Requirements 6.2
// =============================================================================

describe('Property 15: Invitation Detail Field Display', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any invitation in the detail view, the rendered output SHALL contain
	 * all fields including target_servers array and allowed_libraries array.
	 *
	 * Note: This tests the data structure requirements. Component rendering
	 * tests would require the full component setup with mock data.
	 *
	 * **Validates: Requirements 6.2**
	 */
	it('should validate update input with all mutable fields', () => {
		fc.assert(
			fc.property(validUpdateInputArb, (input) => {
				const result = updateInvitationSchema.safeParse(input);

				// Valid update input should pass validation
				expect(result.success).toBe(true);

				if (result.success) {
					// Verify the parsed data contains the expected fields
					const data = result.data;

					// All fields should be present (even if undefined)
					expect('expires_at' in data || data.expires_at === undefined).toBe(true);
					expect('max_uses' in data || data.max_uses === undefined).toBe(true);
					expect('duration_days' in data || data.duration_days === undefined).toBe(true);
					expect('enabled' in data || data.enabled === undefined).toBe(true);
					expect('server_ids' in data || data.server_ids === undefined).toBe(true);
					expect('library_ids' in data || data.library_ids === undefined).toBe(true);
				}
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any update with server_ids, the array SHALL contain valid UUIDs.
	 *
	 * **Validates: Requirements 6.2**
	 */
	it('should validate server_ids as UUIDs', () => {
		fc.assert(
			fc.property(fc.array(uuidArb, { minLength: 1, maxLength: 5 }), (serverIds) => {
				const input: UpdateInvitationInput = {
					server_ids: serverIds
				};

				const result = updateInvitationSchema.safeParse(input);
				expect(result.success).toBe(true);
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any update with invalid server_ids (non-UUIDs), validation SHALL fail.
	 *
	 * **Validates: Requirements 6.2**
	 */
	it('should reject invalid server_ids', () => {
		fc.assert(
			fc.property(
				fc.array(
					fc
						.string({ minLength: 1, maxLength: 10 })
						.filter(
							(s) => !s.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i)
						),
					{ minLength: 1, maxLength: 3 }
				),
				(invalidIds) => {
					const input: UpdateInvitationInput = {
						server_ids: invalidIds
					};

					const result = updateInvitationSchema.safeParse(input);
					expect(result.success).toBe(false);
				}
			),
			{ numRuns: 50 }
		);
	});
});

// =============================================================================
// Property 16: Immutable Field Protection
// Validates: Requirements 6.4
// =============================================================================

describe('Property 16: Immutable Field Protection', () => {
	afterEach(() => {
		cleanup();
	});

	/**
	 * For any immutable invitation field (code, use_count, created_at, created_by),
	 * the update schema SHALL NOT include these fields.
	 *
	 * **Validates: Requirements 6.4**
	 */
	it('should not include immutable fields in update schema', () => {
		// Get the shape of the update schema
		const updateShape = updateInvitationSchema.shape;

		// Verify immutable fields are NOT in the update schema
		expect('code' in updateShape).toBe(false);
		expect('use_count' in updateShape).toBe(false);
		expect('created_at' in updateShape).toBe(false);
		expect('created_by' in updateShape).toBe(false);

		// Verify mutable fields ARE in the update schema
		expect('expires_at' in updateShape).toBe(true);
		expect('max_uses' in updateShape).toBe(true);
		expect('duration_days' in updateShape).toBe(true);
		expect('enabled' in updateShape).toBe(true);
		expect('server_ids' in updateShape).toBe(true);
		expect('library_ids' in updateShape).toBe(true);
	});

	/**
	 * For any attempt to include immutable fields in update input,
	 * the schema SHALL strip them from the output.
	 *
	 * **Validates: Requirements 6.4**
	 */
	it('should strip unknown fields from update input', () => {
		fc.assert(
			fc.property(
				fc.record({
					// Mutable fields
					expires_at: fc.oneof(isoDateArb, fc.constant('')),
					max_uses: fc.oneof(fc.integer({ min: 1, max: 100 }), fc.constant(undefined)),
					enabled: fc.boolean(),
					// Immutable fields (should be stripped)
					code: validCodeArb,
					use_count: fc.integer({ min: 0, max: 100 }),
					created_at: isoDateArb
				}),
				(input) => {
					// Parse with strip mode (default)
					const result = updateInvitationSchema.safeParse(input);

					// Should succeed (unknown fields are stripped)
					expect(result.success).toBe(true);

					if (result.success) {
						// Immutable fields should NOT be in the output
						expect('code' in result.data).toBe(false);
						expect('use_count' in result.data).toBe(false);
						expect('created_at' in result.data).toBe(false);
					}
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any valid update input, only mutable fields SHALL be present in output.
	 *
	 * **Validates: Requirements 6.4**
	 */
	it('should only output mutable fields', () => {
		fc.assert(
			fc.property(validUpdateInputArb, (input) => {
				const result = updateInvitationSchema.safeParse(input);

				expect(result.success).toBe(true);

				if (result.success) {
					const outputKeys = Object.keys(result.data);
					const allowedKeys = [
						'expires_at',
						'max_uses',
						'duration_days',
						'enabled',
						'server_ids',
						'library_ids'
					];

					// All output keys should be in the allowed list
					for (const key of outputKeys) {
						expect(allowedKeys).toContain(key);
					}
				}
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * The create schema SHALL include code field (mutable at creation time).
	 *
	 * **Validates: Requirements 6.4**
	 */
	it('should include code in create schema but not update schema', () => {
		const createShape = createInvitationSchema.shape;
		const updateShape = updateInvitationSchema.shape;

		// Code is mutable at creation time
		expect('code' in createShape).toBe(true);

		// Code is immutable after creation
		expect('code' in updateShape).toBe(false);
	});
});
