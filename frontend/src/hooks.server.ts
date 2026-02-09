import type { Handle } from '@sveltejs/kit';
import { redirect } from '@sveltejs/kit';

const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

const PUBLIC_PATHS = ['/login', '/setup', '/join'];

function isPublicPath(pathname: string): boolean {
	return PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export const handle: Handle = async ({ event, resolve }) => {
	// Try to get user info from the access token cookie
	const accessToken = event.cookies.get('zondarr_access_token');

	if (accessToken) {
		try {
			const response = await event.fetch(`${API_BASE_URL}/api/auth/me`, {
				headers: {
					Cookie: `zondarr_access_token=${accessToken}`
				}
			});
			if (response.ok) {
				const user = await response.json();
				event.locals.user = user;
			} else {
				event.locals.user = null;
			}
		} catch {
			event.locals.user = null;
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

	return resolve(event);
};
