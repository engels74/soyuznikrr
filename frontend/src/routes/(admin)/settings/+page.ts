/**
 * Settings page load function.
 *
 * Fetches all settings, about info, and admin profile in parallel.
 */

import { getMe } from '$lib/api/auth';
import { getAbout, getAllSettings } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [settingsResult, aboutResult, me] = await Promise.all([
		getAllSettings(fetch),
		getAbout(fetch),
		getMe(fetch)
	]);

	return {
		settings: settingsResult.data ?? null,
		about: aboutResult.data ?? null,
		me
	};
};
