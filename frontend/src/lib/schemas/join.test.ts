/**
 * Tests for registration schema username validation and sanitizeEmailToUsername.
 *
 * Keeps regex-boundary property tests and sanitizeEmailToUsername behavior tests.
 * Trivial Zod acceptance/rejection tests (password length, email format) removed.
 *
 * @module $lib/schemas/join.test
 */

import * as fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import { registrationSchema, sanitizeEmailToUsername } from './join';

// =============================================================================
// Username Validation — regex boundary tests
// =============================================================================

describe('Username Validation', () => {
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

	it('should reject usernames longer than 32 characters', () => {
		fc.assert(
			fc.property(
				fc
					.string({ minLength: 33, maxLength: 100 })
					.map((s) => s.toLowerCase().replace(/[^a-z0-9_]/g, 'a')),
				(longUsername) => {
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

	it('should reject usernames not starting with a lowercase letter', () => {
		fc.assert(
			fc.property(
				fc.oneof(
					fc.stringMatching(/^[0-9][a-z0-9_]{2,31}$/),
					fc.stringMatching(/^_[a-z0-9_]{2,31}$/),
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

	it('should reject usernames with invalid characters', () => {
		fc.assert(
			fc.property(
				fc
					.oneof(
						fc.stringMatching(/^[a-z][a-z0-9_]*[A-Z][a-z0-9_]*$/),
						fc.stringMatching(/^[a-z][a-z0-9_]*[@#$%^&*!][a-z0-9_]*$/),
						fc.stringMatching(/^[a-z][a-z0-9_]* [a-z0-9_]*$/),
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
});

// =============================================================================
// Password Validation — boundary tests
// =============================================================================

describe('Password Validation', () => {
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
				}
			}),
			{ numRuns: 100 }
		);
	});

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
// Email Validation (Optional field behavior)
// =============================================================================

describe('Email Validation', () => {
	it('should accept empty email string (optional field)', () => {
		const result = registrationSchema.safeParse({
			username: 'validuser',
			password: 'validpassword123',
			email: ''
		});

		expect(result.success).toBe(true);
	});

	it('should accept undefined email (optional field)', () => {
		const result = registrationSchema.safeParse({
			username: 'validuser',
			password: 'validpassword123'
		});

		expect(result.success).toBe(true);
	});

	it('should accept valid email addresses', () => {
		const commonEmailArb = fc
			.tuple(
				fc.stringMatching(/^[a-z][a-z0-9]{0,10}$/),
				fc.stringMatching(/^[a-z][a-z0-9]{0,10}$/),
				fc.constantFrom('com', 'org', 'net', 'io', 'dev')
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
		const longLocal = `${'a'.repeat(50)}@example.com`;
		const result = sanitizeEmailToUsername(longLocal);
		expect(result.length).toBeLessThanOrEqual(32);
	});

	it('should collapse consecutive underscores', () => {
		expect(sanitizeEmailToUsername('a..b@example.com')).toBe('a_b');
		expect(sanitizeEmailToUsername('a---b@example.com')).toBe('a_b');
	});

	it('should strip trailing underscores after truncation', () => {
		const email = `${'a'.repeat(31)}.@example.com`;
		const result = sanitizeEmailToUsername(email);
		expect(result).not.toMatch(/_$/);
	});
});
