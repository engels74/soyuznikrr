import { isRedirect, redirect } from '@sveltejs/kit';
import { getAuthMethods, getMe, type OnboardingStep } from '$lib/api/auth';
import { isNetworkError } from '$lib/api/errors';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	try {
		const authMethods = await getAuthMethods(fetch);

		if (authMethods.setup_required) {
			return { onboardingStep: 'account' as OnboardingStep };
		}

		if (!authMethods.onboarding_required) {
			redirect(302, '/login');
		}

		const me = await getMe(fetch);
		if (!me) {
			redirect(302, '/login');
		}

		return { onboardingStep: authMethods.onboarding_step };
	} catch (e) {
		if (isRedirect(e)) throw e;
		if (!isNetworkError(e)) {
			console.warn('[setup loader] unexpected error from getAuthMethods:', e);
		}
		// Backend unreachable or broken — render setup page anyway (submission will fail gracefully)
	}

	return { onboardingStep: 'account' as OnboardingStep };
};
