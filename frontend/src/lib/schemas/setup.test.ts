/**
 * Property-based tests for CSRF origin validation schema.
 *
 * Tests the csrfOriginSchema from the onboarding wizard.
 *
 * @module $lib/schemas/setup.test
 */

import * as fc from 'fast-check';
import { describe, expect, it } from 'vitest';
import { csrfOriginSchema } from './setup';

describe('CSRF Origin Validation', () => {
	it('should accept valid HTTP/HTTPS origins', () => {
		const originArb = fc
			.tuple(
				fc.constantFrom('http', 'https'),
				fc.stringMatching(/^[a-z][a-z0-9-]{0,20}\.[a-z]{2,6}$/)
			)
			.map(([protocol, domain]) => `${protocol}://${domain}`);

		fc.assert(
			fc.property(originArb, (origin) => {
				const result = csrfOriginSchema.safeParse({ origin });
				expect(result.success).toBe(true);
			}),
			{ numRuns: 100 }
		);
	});

	it('should reject empty origin strings', () => {
		const result = csrfOriginSchema.safeParse({ origin: '' });
		expect(result.success).toBe(false);
		if (!result.success) {
			const originErrors = result.error.issues.filter((issue) => issue.path[0] === 'origin');
			expect(originErrors.length).toBeGreaterThan(0);
			expect(originErrors.some((e) => e.message === 'Origin is required')).toBe(true);
		}
	});

	it('should reject non-URL strings', () => {
		fc.assert(
			fc.property(
				fc.stringMatching(/^[a-z]{3,20}$/).filter((s) => !s.includes('://')),
				(randomString) => {
					const result = csrfOriginSchema.safeParse({ origin: randomString });
					expect(result.success).toBe(false);
				}
			),
			{ numRuns: 100 }
		);
	});

	it('should reject non-http(s) protocols', () => {
		fc.assert(
			fc.property(fc.constantFrom('ftp://', 'ws://', 'wss://', 'file://', 'ssh://'), (protocol) => {
				const result = csrfOriginSchema.safeParse({
					origin: `${protocol}example.com`
				});
				expect(result.success).toBe(false);
			}),
			{ numRuns: 50 }
		);
	});

	it('should reject origins with trailing slash', () => {
		const result = csrfOriginSchema.safeParse({ origin: 'https://example.com/' });
		expect(result.success).toBe(false);
		if (!result.success) {
			const trailingSlashErrors = result.error.issues.filter(
				(e) => e.message === 'Remove trailing slash'
			);
			expect(trailingSlashErrors.length).toBeGreaterThan(0);
		}
	});

	it('should accept common real-world origins', () => {
		const realOrigins = [
			'http://localhost:3000',
			'http://localhost:8000',
			'https://zondarr.example.com',
			'https://app.mydomain.org',
			'http://192.168.1.100:8080',
			'https://media.home.lab'
		];

		for (const origin of realOrigins) {
			const result = csrfOriginSchema.safeParse({ origin });
			expect(result.success, `Expected '${origin}' to be valid`).toBe(true);
		}
	});
});
