/**
 * Property-based tests for Jellyfin registration schema.
 *
 * Tests the following properties:
 * - Property 30: Username Validation
 * - Property 31: Password Validation
 *
 * **Validates: Requirements 11.2, 11.3**
 *
 * @module $lib/schemas/join.test
 */

import * as fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import { jellyfinRegistrationSchema } from './join';

// =============================================================================
// Property 30: Username Validation
// Validates: Requirements 11.2
// =============================================================================

describe('Property 30: Username Validation', () => {
	/**
	 * For any username string, the Zod schema SHALL reject usernames that are
	 * less than 3 characters.
	 *
	 * **Validates: Requirements 11.2**
	 */
	it('should reject usernames shorter than 3 characters', () => {
		fc.assert(
			fc.property(fc.string({ minLength: 0, maxLength: 2 }), (shortUsername) => {
				const result = jellyfinRegistrationSchema.safeParse({
					username: shortUsername,
					password: 'validpassword123'
				});

				expect(result.success).toBe(false);
				if (!result.success) {
					const usernameErrors = result.error.issues.filter(
						(issue) => issue.path[0] === 'username'
					);
					expect(usernameErrors.length).toBeGreaterThan(0);
				}
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any username string, the Zod schema SHALL reject usernames that are
	 * more than 32 characters.
	 *
	 * **Validates: Requirements 11.2**
	 */
	it('should reject usernames longer than 32 characters', () => {
		fc.assert(
			fc.property(
				fc
					.string({ minLength: 33, maxLength: 100 })
					.map((s) => s.toLowerCase().replace(/[^a-z0-9_]/g, 'a')),
				(longUsername) => {
					// Ensure it starts with a letter
					const username = `a${longUsername.slice(1)}`;
					const result = jellyfinRegistrationSchema.safeParse({
						username,
						password: 'validpassword123'
					});

					expect(result.success).toBe(false);
					if (!result.success) {
						const usernameErrors = result.error.issues.filter(
							(issue) => issue.path[0] === 'username'
						);
						expect(usernameErrors.length).toBeGreaterThan(0);
					}
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any username string, the Zod schema SHALL reject usernames that
	 * don't start with a lowercase letter.
	 *
	 * **Validates: Requirements 11.2**
	 */
	it('should reject usernames not starting with a lowercase letter', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					// Starts with number
					fc.stringMatching(/^[0-9][a-z0-9_]{2,31}$/),
					// Starts with underscore
					fc.stringMatching(/^_[a-z0-9_]{2,31}$/),
					// Starts with uppercase
					fc.stringMatching(/^[A-Z][a-z0-9_]{2,31}$/)
				),
				(invalidUsername) => {
					const result = jellyfinRegistrationSchema.safeParse({
						username: invalidUsername,
						password: 'validpassword123'
					});

					expect(result.success).toBe(false);
					if (!result.success) {
						const usernameErrors = result.error.issues.filter(
							(issue) => issue.path[0] === 'username'
						);
						expect(usernameErrors.length).toBeGreaterThan(0);
					}
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any username string, the Zod schema SHALL reject usernames that
	 * contain characters other than lowercase letters, numbers, and underscores.
	 *
	 * **Validates: Requirements 11.2**
	 */
	it('should reject usernames with invalid characters', () => {
		fc.assert(
			fc.property(
				fc
					.oneof(
						// Contains uppercase
						fc.stringMatching(/^[a-z][a-z0-9_]*[A-Z][a-z0-9_]*$/),
						// Contains special characters
						fc.stringMatching(/^[a-z][a-z0-9_]*[@#$%^&*!][a-z0-9_]*$/),
						// Contains spaces
						fc.stringMatching(/^[a-z][a-z0-9_]* [a-z0-9_]*$/),
						// Contains hyphens
						fc.stringMatching(/^[a-z][a-z0-9_]*-[a-z0-9_]*$/)
					)
					.filter((s) => s.length >= 3 && s.length <= 32),
				(invalidUsername) => {
					const result = jellyfinRegistrationSchema.safeParse({
						username: invalidUsername,
						password: 'validpassword123'
					});

					expect(result.success).toBe(false);
					if (!result.success) {
						const usernameErrors = result.error.issues.filter(
							(issue) => issue.path[0] === 'username'
						);
						expect(usernameErrors.length).toBeGreaterThan(0);
					}
				}
			),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any valid username (3-32 chars, lowercase, starts with letter,
	 * alphanumeric + underscores), the Zod schema SHALL accept it.
	 *
	 * **Validates: Requirements 11.2**
	 */
	it('should accept valid usernames', () => {
		fc.assert(
			fc.property(fc.stringMatching(/^[a-z][a-z0-9_]{2,31}$/), (validUsername) => {
				const result = jellyfinRegistrationSchema.safeParse({
					username: validUsername,
					password: 'validpassword123'
				});

				expect(result.success).toBe(true);
			}),
			{ numRuns: 100 }
		);
	});
});

// =============================================================================
// Property 31: Password Validation
// Validates: Requirements 11.3
// =============================================================================

describe('Property 31: Password Validation', () => {
	/**
	 * For any password string shorter than 8 characters, the Zod schema
	 * SHALL reject it with an appropriate error message.
	 *
	 * **Validates: Requirements 11.3**
	 */
	it('should reject passwords shorter than 8 characters', () => {
		fc.assert(
			fc.property(fc.string({ minLength: 0, maxLength: 7 }), (shortPassword) => {
				const result = jellyfinRegistrationSchema.safeParse({
					username: 'validuser',
					password: shortPassword
				});

				expect(result.success).toBe(false);
				if (!result.success) {
					const passwordErrors = result.error.issues.filter(
						(issue) => issue.path[0] === 'password'
					);
					expect(passwordErrors.length).toBeGreaterThan(0);
					// Verify error message mentions minimum length
					expect(passwordErrors.some((e) => e.message.toLowerCase().includes('8'))).toBe(true);
				}
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any password string of 8 or more characters (up to 128), the Zod
	 * schema SHALL accept it.
	 *
	 * **Validates: Requirements 11.3**
	 */
	it('should accept passwords of 8 or more characters', () => {
		fc.assert(
			fc.property(fc.string({ minLength: 8, maxLength: 128 }), (validPassword) => {
				const result = jellyfinRegistrationSchema.safeParse({
					username: 'validuser',
					password: validPassword
				});

				expect(result.success).toBe(true);
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For any password string longer than 128 characters, the Zod schema
	 * SHALL reject it.
	 *
	 * **Validates: Requirements 11.3**
	 */
	it('should reject passwords longer than 128 characters', () => {
		fc.assert(
			fc.property(fc.string({ minLength: 129, maxLength: 200 }), (longPassword) => {
				const result = jellyfinRegistrationSchema.safeParse({
					username: 'validuser',
					password: longPassword
				});

				expect(result.success).toBe(false);
				if (!result.success) {
					const passwordErrors = result.error.issues.filter(
						(issue) => issue.path[0] === 'password'
					);
					expect(passwordErrors.length).toBeGreaterThan(0);
				}
			}),
			{ numRuns: 100 }
		);
	});
});

// =============================================================================
// Email Validation (Optional field)
// =============================================================================

describe('Email Validation', () => {
	/**
	 * For any valid email address (common format), the Zod schema SHALL accept it.
	 * Note: We use a more restrictive email generator that matches common email formats
	 * rather than RFC 5321 which allows special characters that Zod rejects.
	 */
	it('should accept valid email addresses', () => {
		// Generate common email formats (alphanumeric local part + domain)
		// Local part: starts with letter, can contain letters, numbers, dots (not at end)
		const commonEmailArb = fc
			.tuple(
				fc.stringMatching(/^[a-z][a-z0-9]{0,10}$/), // local part (simple, no dots at end)
				fc.stringMatching(/^[a-z][a-z0-9]{0,10}$/), // domain name
				fc.constantFrom('com', 'org', 'net', 'io', 'dev') // TLD
			)
			.map(([local, domain, tld]) => `${local}@${domain}.${tld}`);

		fc.assert(
			fc.property(commonEmailArb, (validEmail) => {
				const result = jellyfinRegistrationSchema.safeParse({
					username: 'validuser',
					password: 'validpassword123',
					email: validEmail
				});

				expect(result.success).toBe(true);
			}),
			{ numRuns: 100 }
		);
	});

	/**
	 * For an empty email string, the Zod schema SHALL accept it (optional field).
	 */
	it('should accept empty email string', () => {
		const result = jellyfinRegistrationSchema.safeParse({
			username: 'validuser',
			password: 'validpassword123',
			email: ''
		});

		expect(result.success).toBe(true);
	});

	/**
	 * For undefined email, the Zod schema SHALL accept it (optional field).
	 */
	it('should accept undefined email', () => {
		const result = jellyfinRegistrationSchema.safeParse({
			username: 'validuser',
			password: 'validpassword123'
		});

		expect(result.success).toBe(true);
	});

	/**
	 * For invalid email formats, the Zod schema SHALL reject them.
	 */
	it('should reject invalid email formats', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					fc.constant('notanemail'),
					fc.constant('missing@domain'),
					fc.constant('@nodomain.com'),
					fc.constant('spaces in@email.com'),
					fc.constant('double@@at.com')
				),
				(invalidEmail) => {
					const result = jellyfinRegistrationSchema.safeParse({
						username: 'validuser',
						password: 'validpassword123',
						email: invalidEmail
					});

					expect(result.success).toBe(false);
					if (!result.success) {
						const emailErrors = result.error.issues.filter((issue) => issue.path[0] === 'email');
						expect(emailErrors.length).toBeGreaterThan(0);
					}
				}
			),
			{ numRuns: 50 }
		);
	});
});
