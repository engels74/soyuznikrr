import { env } from '$env/dynamic/private';
import { env as publicEnv } from '$env/dynamic/public';
import type { RequestHandler } from './$types';

const INTERNAL_API_URL = env.INTERNAL_API_URL ?? publicEnv.PUBLIC_API_URL ?? 'http://localhost:8000';

// Headers to strip from proxied requests (hop-by-hop + browser-only)
const STRIP_REQUEST_HEADERS = new Set([
	'host',
	'origin',
	'referer',
	'connection',
	'keep-alive',
	'transfer-encoding',
	'upgrade'
]);

const handler: RequestHandler = async ({ request, url, params }) => {
	const path = params.path;
	const upstream = `${INTERNAL_API_URL}/api/${path}${url.search}`;

	// Forward headers, stripping hop-by-hop and Origin/Referer
	const headers = new Headers();
	for (const [key, value] of request.headers) {
		if (!STRIP_REQUEST_HEADERS.has(key.toLowerCase())) {
			headers.set(key, value);
		}
	}

	const hasBody = !['GET', 'HEAD'].includes(request.method);

	try {
		const response = await fetch(upstream, {
			method: request.method,
			headers,
			body: hasBody ? request.body : undefined,
			// @ts-expect-error -- Bun supports duplex streaming
			duplex: hasBody ? 'half' : undefined,
			redirect: 'manual'
		});

		// Forward response with streaming body (supports SSE)
		return new Response(response.body, {
			status: response.status,
			statusText: response.statusText,
			headers: response.headers
		});
	} catch {
		return new Response(JSON.stringify({ detail: 'Backend unavailable' }), {
			status: 502,
			headers: { 'content-type': 'application/json' }
		});
	}
};

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
export const OPTIONS = handler;
