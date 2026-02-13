import { createScopedClient } from '$lib/api/client';
import type { components } from '$lib/api/types';
import type { LayoutServerLoad } from './$types';

type ProviderMeta = components['schemas']['ProviderMetadataResponse'];

export const load: LayoutServerLoad = async ({ locals, fetch }) => {
	const client = createScopedClient(fetch);

	let providers: ProviderMeta[] = [];
	try {
		const { data } = await client.GET('/api/v1/providers');
		providers = data ?? [];
	} catch {
		// Backend unreachable — degrade gracefully so the login page still loads
	}

	return {
		user: locals.user,
		providers
	};
};
