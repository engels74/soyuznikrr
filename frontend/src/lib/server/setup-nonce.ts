import { randomUUID } from 'node:crypto';

const NONCE_TTL_MS = 10 * 60 * 1000; // 10 minutes

const nonceStore = new Map<string, number>();

function pruneExpired(): void {
	const now = Date.now();
	for (const [nonce, expiry] of nonceStore) {
		if (expiry <= now) {
			nonceStore.delete(nonce);
		}
	}
}

export function createNonce(): string {
	pruneExpired();
	const nonce = randomUUID();
	nonceStore.set(nonce, Date.now() + NONCE_TTL_MS);
	return nonce;
}

export function consumeNonce(nonce: string): boolean {
	const expiry = nonceStore.get(nonce);
	if (expiry === undefined) return false;
	nonceStore.delete(nonce);
	return Date.now() < expiry;
}
