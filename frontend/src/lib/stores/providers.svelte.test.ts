/**
 * Tests for provider metadata capability lookups.
 *
 * @module $lib/stores/providers.svelte.test
 */

import { afterEach, describe, expect, it } from 'vitest';
import { hasProviderCapability, setProviders } from './providers.svelte';

const ENABLE_DISABLE_CAPABILITY = 'enable_disable_user';

describe('Provider capability metadata', () => {
	afterEach(() => {
		setProviders([]);
	});

	it('uses built-in capabilities when provider metadata is absent', () => {
		setProviders([]);

		expect(hasProviderCapability('jellyfin', ENABLE_DISABLE_CAPABILITY)).toBe(true);
		expect(hasProviderCapability('plex', ENABLE_DISABLE_CAPABILITY)).toBe(false);
		expect(hasProviderCapability('unknown', ENABLE_DISABLE_CAPABILITY)).toBe(false);
	});

	it('uses loaded provider metadata over built-in capabilities', () => {
		setProviders([
			{
				server_type: 'jellyfin',
				display_name: 'Jellyfin',
				color: '#00a4dc',
				icon_svg: '',
				capabilities: ['create_user'],
				supported_permissions: []
			}
		]);

		expect(hasProviderCapability('jellyfin', ENABLE_DISABLE_CAPABILITY)).toBe(false);
	});
});
