import { redirect } from '@sveltejs/kit';
import { getAuthMethods } from '$lib/api/auth';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const authMethods = await getAuthMethods(fetch);

	if (authMethods.setup_required) {
		redirect(302, '/setup');
	}

	return {
		methods: authMethods.methods
	};
};
