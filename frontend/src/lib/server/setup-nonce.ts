import { randomUUID } from 'node:crypto';

const NONCE_TTL_MS = 10 * 60 * 1000; // 10 minutes

interface NonceEntry {
	expiry: number;
	validated: boolean;
}

const nonceStore = new Map<string, NonceEntry>();

function pruneExpired(): void {
	const now = Date.now();
	for (const [nonce, entry] of nonceStore) {
		if (entry.expiry <= now) {
			nonceStore.delete(nonce);
		}
	}
}

export function createNonce(): string {
	pruneExpired();
	const nonce = randomUUID();
	nonceStore.set(nonce, { expiry: Date.now() + NONCE_TTL_MS, validated: false });
	return nonce;
}

export function createValidatedNonce(): string {
	pruneExpired();
	const nonce = randomUUID();
	nonceStore.set(nonce, { expiry: Date.now() + NONCE_TTL_MS, validated: true });
	return nonce;
}

export function consumeNonce(nonce: string): boolean {
	const entry = nonceStore.get(nonce);
	if (entry === undefined) return false;
	nonceStore.delete(nonce);
	return Date.now() < entry.expiry && entry.validated;
}
