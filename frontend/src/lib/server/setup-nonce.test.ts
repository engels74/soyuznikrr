import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { consumeNonce, createNonce, createValidatedNonce } from './setup-nonce';

describe('setup-nonce', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	describe('createNonce', () => {
		it('returns a string', () => {
			const nonce = createNonce();
			expect(typeof nonce).toBe('string');
			expect(nonce.length).toBeGreaterThan(0);
		});

		it('returns unique values on each call', () => {
			const a = createNonce();
			const b = createNonce();
			expect(a).not.toBe(b);
		});
	});

	describe('createValidatedNonce', () => {
		it('returns a string', () => {
			const nonce = createValidatedNonce();
			expect(typeof nonce).toBe('string');
			expect(nonce.length).toBeGreaterThan(0);
		});

		it('returns unique values on each call', () => {
			const a = createValidatedNonce();
			const b = createValidatedNonce();
			expect(a).not.toBe(b);
		});
	});

	describe('consumeNonce', () => {
		it('returns true for a validated nonce', () => {
			const nonce = createValidatedNonce();
			expect(consumeNonce(nonce)).toBe(true);
		});

		it('returns false for a non-validated nonce', () => {
			const nonce = createNonce();
			expect(consumeNonce(nonce)).toBe(false);
		});

		it('returns false for an unknown nonce', () => {
			expect(consumeNonce('nonexistent-nonce')).toBe(false);
		});

		it('is single-use — second consume returns false', () => {
			const nonce = createValidatedNonce();
			expect(consumeNonce(nonce)).toBe(true);
			expect(consumeNonce(nonce)).toBe(false);
		});

		it('returns false for an expired validated nonce', () => {
			const nonce = createValidatedNonce();

			// Advance past TTL (10 minutes = 600_000 ms)
			vi.advanceTimersByTime(600_001);

			expect(consumeNonce(nonce)).toBe(false);
		});

		it('returns true for a validated nonce just before expiry', () => {
			const nonce = createValidatedNonce();

			// Advance to just under the TTL
			vi.advanceTimersByTime(599_999);

			expect(consumeNonce(nonce)).toBe(true);
		});
	});

	describe('cleanup', () => {
		it('removes expired entries when creating new nonces', () => {
			// Create a nonce that will expire
			const oldNonce = createValidatedNonce();

			// Advance past TTL
			vi.advanceTimersByTime(600_001);

			// Create a new nonce — this should trigger cleanup of the old one
			const newNonce = createValidatedNonce();

			// Old nonce should be cleaned up (expired)
			expect(consumeNonce(oldNonce)).toBe(false);
			// New nonce should still be valid
			expect(consumeNonce(newNonce)).toBe(true);
		});
	});
});
