import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('$lib/api/auth', async () => {
	const actual = await vi.importActual('$lib/api/auth');
	return {
		...actual,
		getAuthMethods: vi.fn(),
		getMe: vi.fn()
	};
});

import * as authApi from '$lib/api/auth';
import { load } from './+page.server';

describe('/setup +page.server load', () => {
	afterEach(() => {
		vi.resetAllMocks();
	});

	it('does not expose a bootstrap token when setup is required', async () => {
		const authMethods = {
			methods: [],
			setup_required: true,
			onboarding_required: true,
			onboarding_step: 'account',
			provider_auth: []
		} as Awaited<ReturnType<typeof authApi.getAuthMethods>>;

		vi.mocked(authApi.getAuthMethods).mockResolvedValue(authMethods);

		const result = await load({ fetch: vi.fn() } as never);

		expect(result).toEqual({ onboardingStep: 'account' });
		expect(result).not.toHaveProperty('bootstrapToken');
	});
});
