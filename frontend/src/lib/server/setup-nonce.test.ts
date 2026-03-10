import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { consumeNonce, createNonce } from './setup-nonce';

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

	describe('consumeNonce', () => {
		it('returns true for a valid nonce', () => {
			const nonce = createNonce();
			expect(consumeNonce(nonce)).toBe(true);
		});

		it('returns false for an unknown nonce', () => {
			expect(consumeNonce('nonexistent-nonce')).toBe(false);
		});

		it('is single-use — second consume returns false', () => {
			const nonce = createNonce();
			expect(consumeNonce(nonce)).toBe(true);
			expect(consumeNonce(nonce)).toBe(false);
		});

		it('returns false for an expired nonce', () => {
			const nonce = createNonce();

			// Advance past TTL (10 minutes = 600_000 ms)
			vi.advanceTimersByTime(600_001);

			expect(consumeNonce(nonce)).toBe(false);
		});

		it('returns true for a nonce just before expiry', () => {
			const nonce = createNonce();

			// Advance to just under the TTL
			vi.advanceTimersByTime(599_999);

			expect(consumeNonce(nonce)).toBe(true);
		});
	});

	describe('cleanup', () => {
		it('removes expired entries when creating new nonces', () => {
			// Create a nonce that will expire
			const oldNonce = createNonce();

			// Advance past TTL
			vi.advanceTimersByTime(600_001);

			// Create a new nonce — this should trigger cleanup of the old one
			const newNonce = createNonce();

			// Old nonce should be cleaned up (expired)
			expect(consumeNonce(oldNonce)).toBe(false);
			// New nonce should still be valid
			expect(consumeNonce(newNonce)).toBe(true);
		});
	});
});
