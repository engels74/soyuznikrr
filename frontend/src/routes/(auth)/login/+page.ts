import { isRedirect, redirect } from '@sveltejs/kit';
import { getAuthMethods, type ProviderAuthInfo } from '$lib/api/auth';
import { isNetworkError } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	try {
		const authMethods = await getAuthMethods(fetch);

		if (authMethods.setup_required) {
			redirect(302, '/setup');
		}

		return {
			methods: authMethods.methods,
			providerAuth: authMethods.provider_auth ?? [],
			backendAvailable: true
		};
	} catch (e) {
		if (isRedirect(e)) throw e;
		const networkError = isNetworkError(e);
		if (!networkError) {
			console.warn('[login loader] unexpected error from getAuthMethods:', e);
		}
		// Only signal unavailability for actual network errors (backend unreachable).
		// Other errors (JSON parse, 500, etc.) should still show the login form.
		return {
			methods: ['local'],
			providerAuth: [] as ProviderAuthInfo[],
			backendAvailable: !networkError
		};
	}
};
