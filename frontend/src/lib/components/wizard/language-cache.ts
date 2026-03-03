/**
 * Shared language data cache.
 *
 * Fetches the ISO 639-1 language list from the backend once and caches
 * the result at module level. Multiple components can call `loadLanguages()`
 * without triggering duplicate requests.
 */
import { getLanguages } from '$lib/api/client';

export interface LanguageItem {
	code: string;
	label: string;
}

let cached: LanguageItem[] | null = null;
let pending: Promise<LanguageItem[]> | null = null;

/**
 * Load and cache the language list. Returns immediately if already cached,
 * otherwise fetches from the API and deduplicates concurrent calls.
 */
export async function loadLanguages(): Promise<LanguageItem[]> {
	if (cached) return cached;
	if (pending) return pending;
	pending = getLanguages().then((result) => {
		if (result.data) {
			cached = result.data.map((l) => ({ code: l.code, label: l.name }));
		} else {
			cached = [];
		}
		pending = null;
		return cached;
	});
	return pending;
}

/**
 * Get cached languages synchronously. Returns empty array if not yet loaded.
 */
export function getCachedLanguages(): LanguageItem[] {
	return cached ?? [];
}

/**
 * Look up a language label by code. Falls back to uppercase code.
 */
export function getLanguageLabel(code: string): string {
	return cached?.find((l) => l.code === code)?.label ?? code.toUpperCase();
}
