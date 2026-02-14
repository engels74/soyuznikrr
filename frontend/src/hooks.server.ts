import type { Handle } from '@sveltejs/kit';
import { redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { env as publicEnv } from '$env/dynamic/public';

const API_BASE_URL = publicEnv.PUBLIC_API_URL ?? '';

const PUBLIC_PATHS = ['/login', '/setup', '/join'];

function isPublicPath(pathname: string): boolean {
	return PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export const handle: Handle = async ({ event, resolve }) => {
	// Try to get user info from the access token cookie
	const accessToken = event.cookies.get('zondarr_access_token');
	const skipAuth = ['true', '1', 'yes'].includes((env.DEV_SKIP_AUTH ?? '').toLowerCase());

	if (skipAuth && !accessToken) {
		// Dev mode: skip the API call entirely and use a synthetic admin user
		event.locals.user = {
			id: '00000000-0000-0000-0000-000000000000',
			username: 'dev-admin',
			email: null,
			auth_method: 'dev-skip'
		};
	} else if (accessToken) {
		const controller = new AbortController();
		const timeout = setTimeout(() => controller.abort(), 2000);
		try {
			const response = await event.fetch(`${API_BASE_URL}/api/auth/me`, {
				headers: { Cookie: `zondarr_access_token=${accessToken}` },
				signal: controller.signal
			});
			if (response.ok) {
				const user: App.Locals['user'] = await response.json();
				event.locals.user = user;
			} else {
				event.locals.user = null;
			}
		} catch {
			event.locals.user = null;
		} finally {
			clearTimeout(timeout);
		}
	} else {
		event.locals.user = null;
	}

	const { pathname } = event.url;

	// Redirect authenticated users away from auth pages
	if (event.locals.user && (pathname === '/login' || pathname === '/setup')) {
		redirect(302, '/dashboard');
	}

	// Protect non-public routes
	if (!event.locals.user && !isPublicPath(pathname) && pathname !== '/') {
		redirect(302, '/login');
	}

	return resolve(event, {
		filterSerializedResponseHeaders(name) {
			return name === 'content-type' || name === 'content-length';
		}
	});
};
