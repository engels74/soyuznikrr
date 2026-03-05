import { readFileSync } from 'node:fs';
import { isRedirect, redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { getAuthMethods, getMe, type OnboardingStep } from '$lib/api/auth';
import { isNetworkError } from '$lib/api/errors';
import type { PageServerLoad } from './$types';

function readBootstrapToken(): string | null {
	const filePath = env.BOOTSTRAP_TOKEN_FILE;
	if (!filePath) return null;
	try {
		const content = readFileSync(filePath, 'utf-8').trim();
		return content || null;
	} catch {
		return null;
	}
}

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const authMethods = await getAuthMethods(fetch);

		if (authMethods.setup_required) {
			const bootstrapToken = readBootstrapToken();
			return { onboardingStep: 'account' as OnboardingStep, bootstrapToken };
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
