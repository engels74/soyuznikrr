/**
 * Property-based tests for registration schema.
 *
 * Tests the following properties:
 * - Property 30: Username Validation
 * - Property 31: Password Validation
 *
 * @module $lib/schemas/join.test
 */

import * as fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import { registrationSchema, sanitizeEmailToUsername } from './join';

// =============================================================================
// Property 30: Username Validation
// =============================================================================

describe('Property 30: Username Validation', () => {
	/**
	 * For any username string, the Zod schema SHALL reject usernames that are
	 * less than 3 characters.
	 */
	it('should reject usernames shorter than 3 characters', () => {
		fc.assert(
			fc.property(fc.string({ minLength: 0, maxLength: 2 }), (shortUsername) => {
				const result = registrationSchema.safeParse({
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
					const result = registrationSchema.safeParse({
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
					const result = registrationSchema.safeParse({
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
					const result = registrationSchema.safeParse({
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
	 */
	it('should accept valid usernames', () => {
		fc.assert(
			fc.property(fc.stringMatching(/^[a-z][a-z0-9_]{2,31}$/), (validUsername) => {
				const result = registrationSchema.safeParse({
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
// =============================================================================

describe('Property 31: Password Validation', () => {
	/**
	 * For any password string shorter than 8 characters, the Zod schema
	 * SHALL reject it with an appropriate error message.
	 */
	it('should reject passwords shorter than 8 characters', () => {
		fc.assert(
			fc.property(fc.string({ minLength: 0, maxLength: 7 }), (shortPassword) => {
				const result = registrationSchema.safeParse({
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
	 */
	it('should accept passwords of 8 or more characters', () => {
		fc.assert(
			fc.property(fc.string({ minLength: 8, maxLength: 128 }), (validPassword) => {
				const result = registrationSchema.safeParse({
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
	 */
	it('should reject passwords longer than 128 characters', () => {
		fc.assert(
			fc.property(fc.string({ minLength: 129, maxLength: 200 }), (longPassword) => {
				const result = registrationSchema.safeParse({
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
				const result = registrationSchema.safeParse({
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
		const result = registrationSchema.safeParse({
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
		const result = registrationSchema.safeParse({
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
					const result = registrationSchema.safeParse({
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

// =============================================================================
// sanitizeEmailToUsername
// =============================================================================

describe('sanitizeEmailToUsername', () => {
	/**
	 * For any email address, the output SHALL always match the backend
	 * username pattern `^[a-z][a-z0-9_]*$` with length 3-32.
	 */
	it('should always produce a valid username from any email', () => {
		fc.assert(
			fc.property(fc.emailAddress(), (email) => {
				const result = sanitizeEmailToUsername(email);
				expect(result).toMatch(/^[a-z][a-z0-9_]*$/);
				expect(result.length).toBeGreaterThanOrEqual(3);
				expect(result.length).toBeLessThanOrEqual(32);
			}),
			{ numRuns: 200 }
		);
	});

	it('should convert dots and hyphens to underscores', () => {
		expect(sanitizeEmailToUsername('hans.irwin@tmail.link')).toBe('hans_irwin');
		expect(sanitizeEmailToUsername('first-last@example.com')).toBe('first_last');
	});

	it('should handle plus tags', () => {
		expect(sanitizeEmailToUsername('user+tag@example.com')).toBe('user_tag');
	});

	it('should strip leading digits', () => {
		expect(sanitizeEmailToUsername('123abc@example.com')).toBe('abc');
	});

	it('should fallback to "user" when no valid letters remain', () => {
		expect(sanitizeEmailToUsername('123@example.com')).toBe('user');
		expect(sanitizeEmailToUsername('___@example.com')).toBe('user');
	});

	it('should pad short local parts to minimum 3 chars', () => {
		const result = sanitizeEmailToUsername('ab@example.com');
		expect(result.length).toBeGreaterThanOrEqual(3);
		expect(result).toBe('ab_');
	});

	it('should truncate long local parts to 32 chars', () => {
		const longLocal = 'a'.repeat(50) + '@example.com';
		const result = sanitizeEmailToUsername(longLocal);
		expect(result.length).toBeLessThanOrEqual(32);
	});

	it('should collapse consecutive underscores', () => {
		expect(sanitizeEmailToUsername('a..b@example.com')).toBe('a_b');
		expect(sanitizeEmailToUsername('a---b@example.com')).toBe('a_b');
	});

	it('should strip trailing underscores after truncation', () => {
		// 31 a's + dot → 31 a's + underscore → truncated to 32, trailing _ stripped
		const email = 'a'.repeat(31) + '.@example.com';
		const result = sanitizeEmailToUsername(email);
		expect(result).not.toMatch(/_$/);
	});
});
