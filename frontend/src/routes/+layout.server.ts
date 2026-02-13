import { createScopedClient } from '$lib/api/client';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals, fetch }) => {
	const client = createScopedClient(fetch);
	const { data: providers } = await client.GET('/api/v1/providers');

	return {
		user: locals.user,
		providers: providers ?? []
	};
};
